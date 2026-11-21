"""VS-AI match logic shared by both versus modes.

* ``TurnMatch``      - turn-based: the human and Sir Nadeem each play the SAME
                       level (same walls, same hunter and ghost start cells),
                       one after the other. Every turn gets its own random
                       stream, so the ghost walks a fresh random path.
* ``simultaneous_session`` - both hunters on one maze, one shared ghost.
* ``decide_winner``  - higher final score wins.
"""

from __future__ import annotations

import random

from config import (AI_NAME, PLAYER_NAME, RESULT_AI_WINS, RESULT_PLAYER_WINS,
                    RESULT_TIE, Difficulty)
from .agents import HunterAgent
from .csp import generate_level
from .scoring import ScoreBreakdown
from .session import GameSession, HunterState


def decide_winner(player: ScoreBreakdown, ai: ScoreBreakdown) -> str:
    """'player', 'ai' or 'tie', by final score."""
    if player.final > ai.final:
        return "player"
    if ai.final > player.final:
        return "ai"
    return "tie"


RESULT_MESSAGES = {"player": RESULT_PLAYER_WINS, "ai": RESULT_AI_WINS, "tie": RESULT_TIE}


def simultaneous_session(difficulty: Difficulty, rng: random.Random,
                         player: HunterAgent, ai: HunterAgent) -> GameSession:
    """Human is hunter 0 (priority in conflicts, owns radar/hint), AI is hunter 1."""
    return GameSession(difficulty, rng, agents=[player, ai], names=[PLAYER_NAME, AI_NAME])


class TurnMatch:
    def __init__(self, difficulty: Difficulty, rng: random.Random,
                 player: HunterAgent, ai: HunterAgent, ai_first: bool):
        self.difficulty = difficulty
        self.rng = rng
        self.agents = {"player": player, "ai": ai}
        self.order = ["ai", "player"] if ai_first else ["player", "ai"]
        self.level = generate_level(difficulty.size, difficulty.wall_count,
                                    difficulty.min_spawn_distance, rng)
        self.results: dict[str, HunterState] = {}
        self.turn = 0
        self.session = self._new_session()

    @property
    def current(self) -> str:
        """'player' or 'ai': whose turn it is."""
        return self.order[self.turn]

    @property
    def is_last_turn(self) -> bool:
        return self.turn == len(self.order) - 1

    @property
    def target(self) -> ScoreBreakdown | None:
        """Score set by whoever played the first turn (shown during the second)."""
        if self.turn == 0:
            return None
        return self.results[self.order[0]].score

    def _new_session(self) -> GameSession:
        who = self.current
        # Fresh random stream per turn: same level, new ghost path / noise / flickers.
        turn_rng = random.Random(self.rng.getrandbits(64))
        return GameSession(self.difficulty, turn_rng, agents=[self.agents[who]],
                           names=[AI_NAME if who == "ai" else PLAYER_NAME], level=self.level)

    def advance(self) -> bool:
        """Record the finished turn. Returns True if another turn follows."""
        if not self.session.caught:
            raise RuntimeError("turn not finished")
        self.results[self.current] = self.session.primary
        if self.is_last_turn:
            return False
        self.turn += 1
        self.session = self._new_session()
        return True

    @property
    def finished(self) -> bool:
        return len(self.results) == len(self.order)
