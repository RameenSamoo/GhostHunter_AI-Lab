"""Score calculation and the high-score entry record.

Storage lives in core/database.py (SQLite).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from config import (BASE_SCORE, HINT_PENALTY, MOVE_PENALTY, NAME_MAX_LEN,
                    RADAR_PENALTY, TIME_PENALTY_PER_SECOND)


@dataclass(frozen=True)
class ScoreBreakdown:
    seconds: float
    moves: int
    base: float
    multiplier: float
    scaled: float
    radar_uses: int
    radar_penalty: int
    hint_uses: int
    hint_penalty: int
    final: int


def compute_score(seconds: float, moves: int, multiplier: float, radar_uses: int, hint_uses: int) -> ScoreBreakdown:
    seconds = round(seconds, 1)
    base = max(0.0, BASE_SCORE - TIME_PENALTY_PER_SECOND * seconds - MOVE_PENALTY * moves)
    scaled = base * multiplier
    radar_penalty = RADAR_PENALTY * radar_uses
    hint_penalty = HINT_PENALTY * hint_uses
    final = math.floor(scaled - radar_penalty - hint_penalty + 0.5)  # round half up
    return ScoreBreakdown(seconds, moves, base, multiplier, scaled,
                          radar_uses, radar_penalty, hint_uses, hint_penalty, final)


def sanitize_name(raw: str) -> str:
    cleaned = "".join(ch for ch in raw if ch.isalnum() or ch == " ")
    return cleaned[:NAME_MAX_LEN]


@dataclass
class ScoreEntry:
    name: str
    score: int
    time: float
    moves: int
    date: str
    player_id: str = "P-1"
    ai_score: int | None = None      
    ai_time: float | None = None
    ai_moves: int | None = None
