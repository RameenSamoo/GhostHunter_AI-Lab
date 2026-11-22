"""SQLite storage: the same leaderboard rules as the JSON version, plus hunters (P-n IDs),
history, transactions, constraints, parameterized queries and the one-time JSON import."""

import json
import sqlite3
from datetime import date

import pytest

from config import AI_NAME, MODE_SIMULTANEOUS, MODE_SOLO, MODE_TURNS
from core.database import HighScoreTable, connect
from core.scoring import compute_score


@pytest.fixture
def table(tmp_path):
    t = HighScoreTable(tmp_path / "test.db")
    yield t
    t.close()


# ------------------------------------------------- leaderboard rules (unchanged)
def test_ranking_and_persistence(tmp_path):
    path = tmp_path / "test.db"
    table = HighScoreTable(path)
    for i, score in enumerate([500, 900, 100, 700, 300]):
        assert table.add("beginner", f"P{i}", score, 10.0 + i, 5, on=date(2026, 11, 15))
    assert [e.score for e in table.entries("beginner")] == [900, 700, 500, 300, 100]

    assert not table.qualifies("beginner", 100)          # must beat 5th place
    assert table.qualifies("beginner", 101)
    assert table.add("beginner", "NEW", 800, 9.0, 3) == 2
    assert [e.score for e in table.entries("beginner")] == [900, 800, 700, 500, 300]
    table.close()

    reloaded = HighScoreTable(path)                        # survives closing/reopening
    assert [e.name for e in reloaded.entries("beginner")] == ["P1", "NEW", "P3", "P0", "P4"]
    assert reloaded.entries("beginner")[0].date == "2026-11-15"
    reloaded.close()


def test_non_qualifying_score_writes_nothing(table):
    for i in range(5):
        table.add("beginner", f"P{i}", 1000 + i, 10.0, 5)
    players_before = table.conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
    assert table.add("beginner", "LOW", 999, 10.0, 5) is None
    assert table.history_count("beginner", MODE_SOLO) == 5
    assert table.conn.execute("SELECT COUNT(*) FROM players").fetchone()[0] == players_before


def test_negative_scores_only_when_board_not_full(table):
    assert table.qualifies("expert", -400)
    for i in range(5):
        table.add("expert", f"N{i}", -1000 - i, 50.0, 10)
    assert not table.qualifies("expert", -5)
    assert table.qualifies("expert", 0)


def test_ties_broken_by_faster_time_then_earlier_game(table):
    table.add("expert", "SLOW", 1000, 40.0, 10)
    table.add("expert", "FAST", 1000, 20.0, 10)
    table.add("expert", "FAST2", 1000, 20.0, 10)
    assert [e.name for e in table.entries("expert")] == ["FAST", "FAST2", "SLOW"]


def test_name_is_sanitized(table):
    table.add("beginner", "Abdullah_#1 !", 500, 5.0, 5)
    assert table.entries("beginner")[0].name == "Abdullah1"
    table.add("beginner", "   ", 400, 5.0, 5)
    assert table.entries("beginner")[1].name == "HUNTER"


def test_history_is_kept_but_only_top_5_shown(table):
    for i in range(8):
        table.add("beginner", f"P{i}", 100 * (i + 1), 10.0, 5)   # each beats the 5th place
    assert table.history_count("beginner", MODE_SOLO) == 8
    assert [e.score for e in table.entries("beginner")] == [800, 700, 600, 500, 400]


# ---------------------------------------------------------------- hunters
def test_hunter_ids_are_sequential_and_names_case_insensitive(table):
    assert table.get_or_create_player("Ali") == ("P-1", "Ali")
    assert table.get_or_create_player("Sara") == ("P-2", "Sara")
    assert table.get_or_create_player("  ali ") == ("P-1", "Ali")       # same hunter, original spelling kept
    assert table.get_or_create_player("") == ("P-3", "HUNTER")


def test_get_player_and_last_player(table):
    assert table.get_player("P-9") is None
    assert table.last_player_id == "P-1"                                  # default before anyone exists
    table.get_or_create_player("Ali")
    table.get_or_create_player("Sara")
    assert table.last_player_id == "P-2"
    table.last_player_id = "P-1"
    assert table.last_player_id == "P-1"
    p = table.get_player("P-1")
    assert (p["player_id"], p["name"], p["games"]) == ("P-1", "Ali", 0)
    assert p["created"] == date.today().isoformat()


def test_saving_a_score_counts_the_game_and_stores_the_id(table):
    pid, name = table.get_or_create_player("Ali")
    table.add("beginner", name, 5000, 9.0, 12, player_id=pid)
    table.add("beginner", name, 6000, 9.0, 12, player_id=pid)
    assert table.get_player(pid)["games"] == 2
    row = table.entries("beginner")[0]
    assert (row.name, row.player_id, row.score) == ("Ali", "P-1", 6000)


def test_add_without_an_id_finds_or_creates_the_hunter(table):
    table.add("beginner", "Zed", 100, 5.0, 5)
    table.add("beginner", "zed", 200, 5.0, 5)
    assert table.conn.execute("SELECT COUNT(*) FROM players").fetchone()[0] == 1
    assert table.get_player("P-1")["games"] == 2


def test_hunters_survive_reopening(tmp_path):
    path = tmp_path / "test.db"
    t = HighScoreTable(path)
    t.get_or_create_player("Ali")
    t.close()
    t2 = HighScoreTable(path)
    assert t2.get_player("P-1")["name"] == "Ali"
    t2.close()


# ---------------------------------------------------------------- VS modes
def test_modes_have_separate_boards_with_ai_column(table):
    ai = compute_score(5.0, 20, 1.0, 0, 0)
    table.add("beginner", "ABD", 9000, 7.0, 30, on=date(2026, 11, 15), mode=MODE_SIMULTANEOUS, ai=ai)
    table.add("beginner", "ABD", 8000, 9.0, 30, mode=MODE_TURNS, ai=ai)
    table.add("beginner", "ABD", 7000, 9.0, 30)
    assert [e.score for e in table.entries("beginner", MODE_SIMULTANEOUS)] == [9000]
    assert [e.score for e in table.entries("beginner", MODE_TURNS)] == [8000]
    assert [e.score for e in table.entries("beginner", MODE_SOLO)] == [7000]
    row = table.entries("beginner", MODE_SIMULTANEOUS)[0]
    assert (row.ai_score, row.ai_time, row.ai_moves) == (ai.final, 5.0, 20)
    assert table.entries("beginner")[0].ai_score is None


def test_vs_game_stores_two_result_rows(table):
    ai = compute_score(5.0, 20, 1.0, 0, 0)
    table.add("intermediate", "ABD", 9000, 7.0, 30, mode=MODE_TURNS, ai=ai)
    rows = table.conn.execute(
        "SELECT hunter, player_id, name, score FROM results ORDER BY hunter DESC").fetchall()
    assert [tuple(r) for r in rows] == [("player", "P-1", "ABD", 9000), ("ai", None, AI_NAME, ai.final)]


# ------------------------------------------------------------- integrity
def test_schema_constraints_reject_bad_data(table):
    with pytest.raises(sqlite3.IntegrityError):
        table.conn.execute("INSERT INTO games (mode, difficulty, played_on) VALUES ('arcade', 'beginner', 'x')")
    with pytest.raises(sqlite3.IntegrityError):
        table.conn.execute("INSERT INTO games (mode, difficulty, played_on) VALUES ('solo', 'insane', 'x')")
    with pytest.raises(sqlite3.IntegrityError):    # foreign key: result for a game that doesn't exist
        table.conn.execute("INSERT INTO results (game_id, hunter, player_id, name, score, time, moves) "
                           "VALUES (999, 'player', NULL, 'X', 1, 1.0, 1)")


def test_player_result_must_reference_a_real_hunter(table):
    table.add("beginner", "ABD", 9000, 7.0, 30)
    game_id = table.conn.execute("SELECT id FROM games").fetchone()[0]
    with pytest.raises(sqlite3.IntegrityError):    # unknown hunter id
        table.conn.execute("INSERT INTO results (game_id, hunter, player_id, name, score, time, moves) "
                           "VALUES (?, 'ai', 'P-99', 'X', 1, 1.0, 1)", (game_id,))
    with pytest.raises(sqlite3.IntegrityError):    # a 'player' row without a hunter id
        table.conn.execute("INSERT INTO results (game_id, hunter, player_id, name, score, time, moves) "
                           "VALUES (?, 'player', NULL, 'X', 1, 1.0, 1)", (game_id,))


def test_hunter_names_are_unique_ignoring_case(table):
    table.get_or_create_player("Ali")
    with pytest.raises(sqlite3.IntegrityError):
        table.conn.execute("INSERT INTO players (player_id, name) VALUES ('P-77', 'ALI')")


def test_one_result_per_hunter_per_game(table):
    table.add("beginner", "ABD", 9000, 7.0, 30)
    game_id = table.conn.execute("SELECT id FROM games").fetchone()[0]
    with pytest.raises(sqlite3.IntegrityError):
        table.conn.execute("INSERT INTO results (game_id, hunter, player_id, name, score, time, moves) "
                           "VALUES (?, 'player', 'P-1', 'DUP', 1, 1.0, 1)", (game_id,))


def test_failed_write_rolls_back_the_whole_game(table):
    # Make the results insert fail: neither the games row nor the new hunter may be left behind.
    bad_ai = compute_score(5.0, 20, 1.0, 0, 0)
    object.__setattr__(bad_ai, "moves", -1)          # violates CHECK (moves >= 0)
    with pytest.raises(sqlite3.IntegrityError):
        table.add("beginner", "ABD", 9000, 7.0, 30, mode=MODE_TURNS, ai=bad_ai)
    assert table.history_count() == 0
    assert table.conn.execute("SELECT COUNT(*) FROM results").fetchone()[0] == 0
    assert table.conn.execute("SELECT COUNT(*) FROM players").fetchone()[0] == 0


def test_damaged_file_is_set_aside_and_replaced(tmp_path):
    path = tmp_path / "test.db"
    path.write_bytes(b"this is not a database" * 100)
    table = HighScoreTable(path)
    assert table.entries("beginner") == []
    table.add("beginner", "NEW", 100, 1.0, 1)
    assert (tmp_path / "test.db.damaged").exists()
    table.close()


def test_old_layout_database_is_set_aside_not_crashed_on(tmp_path):
    path = tmp_path / "test.db"
    old = sqlite3.connect(path)
    old.executescript("CREATE TABLE games (id INTEGER PRIMARY KEY, mode TEXT, difficulty TEXT, played_on TEXT);"
                      "CREATE TABLE results (id INTEGER PRIMARY KEY, game_id INTEGER, hunter TEXT, name TEXT,"
                      " score INTEGER, time REAL, moves INTEGER);")
    old.close()
    table = HighScoreTable(path)
    assert table.add("beginner", "NEW", 100, 1.0, 1) == 1
    assert (tmp_path / "test.db.damaged").exists()
    table.close()


def test_schema_version_and_foreign_keys_enabled(tmp_path):
    conn = connect(tmp_path / "test.db")
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    conn.close()


# ----------------------------------------------------- one-time JSON import
LEGACY = {
    "_players": {"P-1": {"player_id": "P-1", "name": "Abdullah", "created": "2026-11-15", "games": 3},
                 "P-2": {"player_id": "P-2", "name": "Sara", "created": "2026-11-16", "games": 1}},
    "_last_player_id": "P-2",
    "solo": {"beginner": [
        {"name": "Abdullah", "score": 9000, "time": 8.2, "moves": 14, "date": "2026-11-15", "player_id": "P-1",
         "ai_score": None, "ai_time": None, "ai_moves": None},
        {"name": "Sara", "score": 7000, "time": 9.0, "moves": 20, "date": "2026-11-16", "player_id": "P-2",
         "ai_score": None, "ai_time": None, "ai_moves": None}],
        "intermediate": [], "professional": [], "expert": []},
    "turns": {"beginner": [
        {"name": "Abdullah", "score": 8000, "time": 9.0, "moves": 30, "date": "2026-11-15", "player_id": "P-1",
         "ai_score": 8800, "ai_time": 7.5, "ai_moves": 25}]},
}


def test_legacy_json_is_imported_once(tmp_path):
    js = tmp_path / "highscores.json"
    js.write_text(json.dumps(LEGACY))
    before = js.read_text()

    t = HighScoreTable(tmp_path / "test.db", legacy_json=js)
    assert [(e.name, e.player_id, e.score) for e in t.entries("beginner")] == [
        ("Abdullah", "P-1", 9000), ("Sara", "P-2", 7000)]
    row = t.entries("beginner", MODE_TURNS)[0]
    assert (row.ai_score, row.ai_time, row.ai_moves) == (8800, 7.5, 25)
    assert t.get_player("P-1")["games"] == 3 and t.get_player("P-2")["name"] == "Sara"
    assert t.get_player("P-1")["created"] == "2026-11-15"
    assert t.last_player_id == "P-2"
    t.add("beginner", "New", 100, 1.0, 1)
    t.close()

    t2 = HighScoreTable(tmp_path / "test.db", legacy_json=js)      # reopening must not import again
    assert t2.history_count("beginner", MODE_SOLO) == 3
    assert t2.conn.execute("SELECT COUNT(*) FROM players").fetchone()[0] == 3
    t2.close()
    assert js.read_text() == before                                 # the JSON file is never touched


def test_legacy_without_player_ids_or_in_the_oldest_format(tmp_path):
    js = tmp_path / "highscores.json"
    js.write_text('{"beginner": [{"name": "OLD", "score": 5000, "time": 10.0, "moves": 9, '
                  '"date": "2026-11-01"}]}')
    t = HighScoreTable(tmp_path / "test.db", legacy_json=js)
    e = t.entries("beginner", MODE_SOLO)[0]
    assert (e.name, e.player_id) == ("OLD", "P-1")
    assert t.entries("beginner", MODE_SIMULTANEOUS) == []
    t.close()


def test_bad_legacy_rows_are_skipped_and_bad_files_ignored(tmp_path):
    js = tmp_path / "highscores.json"
    js.write_text(json.dumps({"solo": {"beginner": [
        {"name": "Good", "score": 100, "time": 5.0, "moves": 5, "date": "2026-11-01"},
        {"name": "BadTime", "score": 100, "time": -1, "moves": 5},
        {"score": 5}, "not a row"]}}))
    t = HighScoreTable(tmp_path / "a.db", legacy_json=js)
    assert [e.name for e in t.entries("beginner")] == ["Good"]
    t.close()

    broken = tmp_path / "broken.json"
    broken.write_text("{not json")
    t = HighScoreTable(tmp_path / "b.db", legacy_json=broken)
    assert t.entries("beginner") == [] and t.history_count() == 0
    t.close()


def test_missing_legacy_file_is_fine(tmp_path):
    t = HighScoreTable(tmp_path / "test.db", legacy_json=tmp_path / "nope.json")
    assert t.entries("beginner") == []
    t.close()
