"""Agents (PEAS: A, with Actions and Percepts).

The game loop only ever talks to a ``HunterAgent``: it hands over a
``Percept`` and receives an ``Action`` (or None). The keyboard player is one
agent; the autonomous AI hunter planned for the next stage will be another,
plugged in without touching the game loop.

PEAS summary
    Performance : final score (fast catch, few moves, few radar/hint uses)
    Environment : GridEnvironment (walls, hunter, invisible random-walk ghost)
    Actuators   : move UP / DOWN / LEFT / RIGHT
    Sensors     : own position, noisy walking-distance reading, occasional sighting,
                  position of the other hunter (VS mode)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from config import MOVE_REPEAT_DELAY, MOVE_REPEAT_RATE
from .grid import GridMap
from .search import Cell


class Action(Enum):
    UP = (-1, 0)
    DOWN = (1, 0)
    LEFT = (0, -1)
    RIGHT = (0, 1)

    @property
    def delta(self) -> Cell:
        return self.value


@dataclass(frozen=True)
class Percept:
    """Everything a hunter is allowed to know this frame.

    The ghost's true position is only ever included as ``sighting`` while the
    ghost is visibly flickering on the grid (or, for the human, during radar).
    """
    hunter: Cell                       # the hunter always knows where it is
    reading: int | None                # latest noisy walking-distance reading
    sighting: Cell | None              # ghost cell if currently visible, else None
    elapsed: float                     # seconds since the level started
    new_reading: bool = False          # a fresh reading arrived since the last percept
    ghost_moved: bool = False          # the ghost ticked since the last percept
    others: tuple[Cell, ...] = ()      # cells of the other hunters still on the board


class HunterAgent(ABC):
    is_ai: bool = False

    def reset(self, grid: GridMap) -> None:
        """Called at the start of every level. The map layout is known."""

    @abstractmethod
    def act(self, percept: Percept, dt: float) -> Action | None:
        """Return the move to make this frame, or None to stand still."""


class KeyboardAgent(HunterAgent):
    """Human player: arrow keys with auto-repeat.

    A key press moves immediately. If the key is still held after
    MOVE_REPEAT_DELAY, it repeats at MOVE_REPEAT_RATE cells per second. When
    several arrows are held, the most recently pressed one wins.
    """

    def __init__(self) -> None:
        self._held: list[Action] = []
        self._pending: Action | None = None
        self._repeat_timer = 0.0

    def reset(self, grid: GridMap | None = None) -> None:
        self._held.clear()
        self._pending = None
        self._repeat_timer = 0.0

    def key_down(self, action: Action) -> None:
        if action in self._held:
            self._held.remove(action)
        self._held.append(action)
        self._pending = action
        self._repeat_timer = MOVE_REPEAT_DELAY

    def key_up(self, action: Action) -> None:
        if action in self._held:
            self._held.remove(action)
            if self._held:
                # Fall back to the previously held key, continuing the repeat.
                self._repeat_timer = min(self._repeat_timer, 1.0 / MOVE_REPEAT_RATE)

    def act(self, percept: Percept, dt: float) -> Action | None:
        if self._pending is not None:
            action, self._pending = self._pending, None
            return action
        if not self._held:
            return None
        self._repeat_timer -= dt
        if self._repeat_timer <= 1e-9:   # tolerance absorbs float rounding of dt sums
            self._repeat_timer += 1.0 / MOVE_REPEAT_RATE
            if self._repeat_timer <= 0.0:  # long frame hitch: don't burst-move
                self._repeat_timer = 1.0 / MOVE_REPEAT_RATE
            return self._held[-1]
        return None
