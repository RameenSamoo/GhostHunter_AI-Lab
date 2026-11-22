"""SQLite persistence layer for hunters and high scores.

All SQL in the project lives in this file. The rest of the game talks only to
``HighScoreTable`` (players, entries, qualifies, add), so the UI never touches
the database directly.

Schema (normalized)

    players                      games                      results
    ───────────────────────      ───────────────────────    ──────────────────────────────
    player_id  TEXT PK 'P-n'     id         INTEGER PK      id         INTEGER PK
    name       TEXT UNIQUE       mode       TEXT            game_id    INTEGER FK -> games.id
    created    TEXT              difficulty TEXT            hunter     TEXT 'player' | 'ai'
    games      INTEGER           played_on  TEXT            player_id  TEXT FK -> players
                                                            name, score, time, moves
    meta (key, value): the last hunter used, and whether the old JSON was imported.

A game is saved only when the hunter's score qualifies for the Top 5. Every saved
game is kept as history; a leaderboard is the Top-5 query over that history. VS
games also store Sir Nadeem's result as a second ``results`` row for the same game.

Every query is parameterized (``?`` placeholders); no SQL is built from user input.

The first time a database is created, the old ``highscores.json`` (if present) is
imported once. The JSON file itself is never modified or deleted.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

from config import AI_NAME, DIFFICULTIES, HIGHSCORE_SLOTS, MODE_SOLO, MODES
from .scoring import ScoreBreakdown, ScoreEntry, sanitize_name

SCHEMA_VERSION = 2

_mode_list = ", ".join(f"'{m}'" for m in MODES)
_difficulty_list = ", ".join(f"'{d.key}'" for d in DIFFICULTIES)

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS players (
    player_id   TEXT    PRIMARY KEY,
    name        TEXT    NOT NULL COLLATE NOCASE UNIQUE,
    created     TEXT,
    games       INTEGER NOT NULL DEFAULT 0 CHECK (games >= 0)
);

CREATE TABLE IF NOT EXISTS meta (
    key         TEXT    PRIMARY KEY,
    value       TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS games (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    mode        TEXT    NOT NULL CHECK (mode IN ({_mode_list})),
    difficulty  TEXT    NOT NULL CHECK (difficulty IN ({_difficulty_list})),
    played_on   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS results (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id     INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    hunter      TEXT    NOT NULL CHECK (hunter IN ('player', 'ai')),
    player_id   TEXT    REFERENCES players(player_id),
    name        TEXT    NOT NULL,
    score       INTEGER NOT NULL,
    time        REAL    NOT NULL CHECK (time >= 0),
    moves       INTEGER NOT NULL CHECK (moves >= 0),
    UNIQUE (game_id, hunter),
    CHECK ((hunter = 'player' AND player_id IS NOT NULL) OR (hunter = 'ai' AND player_id IS NULL))
);

CREATE INDEX IF NOT EXISTS idx_games_mode_difficulty ON games (mode, difficulty);
CREATE INDEX IF NOT EXISTS idx_results_game ON results (game_id);
CREATE INDEX IF NOT EXISTS idx_results_player ON results (player_id);
"""

# Top-N leaderboard for one mode + difficulty.
# Ranked by the human's score (higher first), then faster time, then the
# earlier saved game - the same order the game has always used.
LEADERBOARD_SQL = """
SELECT  p.name, p.player_id, p.score, p.time, p.moves, g.played_on,
        a.score AS ai_score, a.time AS ai_time, a.moves AS ai_moves,
        g.id    AS game_id
FROM    games g
JOIN    results p ON p.game_id = g.id AND p.hunter = 'player'
LEFT JOIN results a ON a.game_id = g.id AND a.hunter = 'ai'
WHERE   g.mode = ? AND g.difficulty = ?
ORDER BY p.score DESC, p.time ASC, g.id ASC
LIMIT   ?
"""

_RESULT_INSERT = ("INSERT INTO results (game_id, hunter, player_id, name, score, time, moves) "
                  "VALUES (?, ?, ?, ?, ?, ?, ?)")


def connect(path: Path) -> sqlite3.Connection:
    """Open (or create) the database, enable foreign keys, apply the schema."""
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    with conn:
        conn.executescript(SCHEMA)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    return conn


class HighScoreTable:
    """Hunters plus Top-5 leaderboards per mode and difficulty, backed by SQLite.

    Qualification: any score while a leaderboard has fewer than 5 entries;
    once full, the score must be non-negative and beat the current 5th place.
    """

    def __init__(self, path: Path, legacy_json: Path | None = None):
        self.path = Path(path)
        try:
            self.conn = connect(self.path)
            # Touch every table/column the game uses: an unreadable or old-layout file raises here.
            self.conn.execute("SELECT player_id, name, created, games FROM players LIMIT 1").fetchall()
            self.conn.execute("SELECT game_id, player_id FROM results LIMIT 1").fetchall()
            self.conn.execute("SELECT COUNT(*) FROM games").fetchone()
        except sqlite3.DatabaseError:
            # Not a usable database (e.g. damaged): keep it aside for inspection
            # and start a fresh one rather than crash.
            self._set_aside_damaged_file()
            self.conn = connect(self.path)
        self._import_legacy_json_once(legacy_json)

    def _set_aside_damaged_file(self) -> None:
        try:
            if getattr(self, "conn", None) is not None:
                self.conn.close()
        except sqlite3.Error:
            pass
        backup = self.path.with_name(self.path.name + ".damaged")
        if backup.exists():
            backup.unlink()
        self.path.replace(backup)

    def close(self) -> None:
        self.conn.close()

    def save(self) -> None:
        """Kept for API compatibility: every write is already committed."""
        self.conn.commit()

    # ------------------------------------------------------------------- meta
    def _get_meta(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def _set_meta(self, key: str, value: str) -> None:
        self.conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))

    @property
    def last_player_id(self) -> str:
        return self._get_meta("last_player_id") or "P-1"

    @last_player_id.setter
    def last_player_id(self, player_id: str) -> None:
        with self.conn:
            self._set_meta("last_player_id", player_id)

    # ---------------------------------------------------------------- players
    def get_player(self, player_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT player_id, name, created, games FROM players WHERE player_id = ?",
            (player_id,)).fetchone()
        return dict(row) if row else None

    def _find_player_by_name(self, name: str) -> sqlite3.Row | None:
        wanted = name.lower()
        for row in self.conn.execute("SELECT player_id, name FROM players ORDER BY rowid"):
            if row["name"].lower() == wanted:
                return row
        return None

    def _next_player_id(self) -> str:
        idx = self.conn.execute("SELECT COUNT(*) FROM players").fetchone()[0] + 1
        while self.conn.execute("SELECT 1 FROM players WHERE player_id = ?", (f"P-{idx}",)).fetchone():
            idx += 1
        return f"P-{idx}"

    def _resolve_player(self, name: str) -> tuple[str, str]:
        """Existing hunter with this name (case-insensitive) or a new P-n. No commit."""
        clean = sanitize_name(name).strip() or "HUNTER"
        found = self._find_player_by_name(clean)
        if found:
            pid, resolved = found["player_id"], found["name"]
        else:
            pid, resolved = self._next_player_id(), clean
            self.conn.execute("INSERT INTO players (player_id, name, created, games) VALUES (?, ?, ?, 0)",
                              (pid, resolved, date.today().isoformat()))
        self._set_meta("last_player_id", pid)
        return pid, resolved

    def get_or_create_player(self, name: str) -> tuple[str, str]:
        with self.conn:
            return self._resolve_player(name)

    # ------------------------------------------------------------------ reads
    def entries(self, difficulty_key: str, mode: str = MODE_SOLO) -> list[ScoreEntry]:
        rows = self.conn.execute(LEADERBOARD_SQL, (mode, difficulty_key, HIGHSCORE_SLOTS)).fetchall()
        return [ScoreEntry(name=r["name"], score=r["score"], time=r["time"], moves=r["moves"],
                           date=r["played_on"], player_id=r["player_id"], ai_score=r["ai_score"],
                           ai_time=r["ai_time"], ai_moves=r["ai_moves"]) for r in rows]

    def qualifies(self, difficulty_key: str, score: int, mode: str = MODE_SOLO) -> bool:
        rows = self.entries(difficulty_key, mode)
        if len(rows) < HIGHSCORE_SLOTS:
            return True
        return score >= 0 and score > rows[-1].score

    def history_count(self, difficulty_key: str | None = None, mode: str | None = None) -> int:
        """How many saved games exist (including ones no longer in the Top 5)."""
        sql, params = "SELECT COUNT(*) FROM games WHERE 1 = 1", []
        if mode is not None:
            sql += " AND mode = ?"
            params.append(mode)
        if difficulty_key is not None:
            sql += " AND difficulty = ?"
            params.append(difficulty_key)
        return self.conn.execute(sql, params).fetchone()[0]

    # ----------------------------------------------------------------- writes
    def add(self, difficulty_key: str, name: str, score: int, seconds: float,
            moves: int, on: date | None = None, mode: str = MODE_SOLO,
            ai: ScoreBreakdown | None = None, player_id: str | None = None) -> int | None:
        """Save a game; returns its 1-based leaderboard rank, or None if it
        didn't qualify (in which case nothing is written)."""
        if not self.qualifies(difficulty_key, score, mode):
            return None
        played_on = (on or date.today()).isoformat()

        with self.conn:      # one transaction: hunter, game and results, or nothing
            known = self.get_player(player_id) if player_id else None
            if known:
                pid, player_name = known["player_id"], sanitize_name(name).strip() or "HUNTER"
                self._set_meta("last_player_id", pid)
            else:
                pid, player_name = self._resolve_player(name)
            self.conn.execute("UPDATE players SET games = games + 1 WHERE player_id = ?", (pid,))

            cur = self.conn.execute(
                "INSERT INTO games (mode, difficulty, played_on) VALUES (?, ?, ?)",
                (mode, difficulty_key, played_on))
            game_id = cur.lastrowid
            self.conn.execute(_RESULT_INSERT,
                              (game_id, "player", pid, player_name, int(score), round(seconds, 1), int(moves)))
            if ai is not None:
                self.conn.execute(_RESULT_INSERT,
                                  (game_id, "ai", None, AI_NAME, int(ai.final), round(ai.seconds, 1), int(ai.moves)))

        ranked = self.conn.execute(LEADERBOARD_SQL, (mode, difficulty_key, HIGHSCORE_SLOTS)).fetchall()
        return next((i + 1 for i, r in enumerate(ranked) if r["game_id"] == game_id), None)

    # ------------------------------------------------------- one-time JSON import
    def _import_legacy_json_once(self, legacy_json: Path | None) -> None:
        """Copy hunters and Top-5 scores from the old highscores.json into this
        database, once. The JSON file is only read, never changed."""
        if self._get_meta("legacy_json_checked"):
            return
        try:
            if legacy_json is not None and Path(legacy_json).exists():
                data = json.loads(Path(legacy_json).read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    with self.conn:
                        self._import_legacy_data(data)
        except (OSError, ValueError, TypeError, AttributeError, sqlite3.Error):
            pass          # unreadable / unexpected file: start with an empty database
        with self.conn:
            self._set_meta("legacy_json_checked", "1")

    def _import_legacy_data(self, data: dict) -> None:
        if any(d.key in data for d in DIFFICULTIES):          # oldest format: solo tables only
            data = {MODE_SOLO: data}
        alias: dict[str, str] = {}                              # legacy id -> id actually stored
        for pid, p in (data.get("_players") or {}).items():
            name = sanitize_name(str(p.get("name", ""))).strip() or "HUNTER"
            found = self._find_player_by_name(name)
            if found:
                alias[pid] = found["player_id"]
                continue
            games = p.get("games", 0)
            self.conn.execute("INSERT INTO players (player_id, name, created, games) VALUES (?, ?, ?, ?)",
                              (pid, name, p.get("created"), games if isinstance(games, int) and games >= 0 else 0))
            alias[pid] = pid

        for mode in MODES:
            for diff in DIFFICULTIES:
                rows = (data.get(mode) or {}).get(diff.key) or []
                for row in rows[:HIGHSCORE_SLOTS]:
                    parsed = self._parse_legacy_row(row)
                    if parsed is None:
                        continue
                    name, score, secs, moves, played_on, legacy_pid, ai = parsed
                    pid = alias.get(legacy_pid) if legacy_pid else None
                    if pid is None:
                        found = self._find_player_by_name(name)
                        if found:
                            pid = found["player_id"]
                        else:
                            pid = self._next_player_id()
                            self.conn.execute(
                                "INSERT INTO players (player_id, name, created, games) VALUES (?, ?, ?, 0)",
                                (pid, name, None))
                    cur = self.conn.execute("INSERT INTO games (mode, difficulty, played_on) VALUES (?, ?, ?)",
                                            (mode, diff.key, played_on))
                    self.conn.execute(_RESULT_INSERT, (cur.lastrowid, "player", pid, name, score, secs, moves))
                    if ai is not None:
                        self.conn.execute(_RESULT_INSERT, (cur.lastrowid, "ai", None, AI_NAME, *ai))

        last = alias.get(data.get("_last_player_id"))
        if last:
            self._set_meta("last_player_id", last)

    @staticmethod
    def _parse_legacy_row(row) -> tuple | None:
        """Validate one old JSON score row; None if it can't be imported."""
        try:
            name = sanitize_name(str(row["name"])).strip() or "HUNTER"
            score, secs, moves = int(row["score"]), round(float(row["time"]), 1), int(row["moves"])
            if secs < 0 or moves < 0:
                return None
            played_on = str(row.get("date") or date.today().isoformat())
            legacy_pid = row.get("player_id")
            ai = None
            if row.get("ai_score") is not None:
                ai = (int(row["ai_score"]), round(float(row["ai_time"]), 1), int(row["ai_moves"]))
                if ai[1] < 0 or ai[2] < 0:
                    ai = None
            return name, score, secs, moves, played_on, legacy_pid, ai
        except (KeyError, TypeError, ValueError, AttributeError):
            return None
