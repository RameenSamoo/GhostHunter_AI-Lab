from __future__ import annotations

import random
from dataclasses import dataclass

import numpy as np

from .search import Cell, bfs_distances, open_neighbors


class GridMap:
    """Immutable level layout with everything the AI needs precomputed."""

    def __init__(self, walls: list[list[bool]]):
        self.size = len(walls)
        self.walls: tuple[tuple[bool, ...], ...] = tuple(tuple(row) for row in walls)

        # Walkable cells get dense indices 0..n-1 (HMM state space).
        self.cells: list[Cell] = [
            (r, c) for r in range(self.size) for c in range(self.size) if not self.walls[r][c]
        ]
        self.index: dict[Cell, int] = {cell: i for i, cell in enumerate(self.cells)}
        self.n = len(self.cells)

        self.neighbors: list[list[int]] = [
            [self.index[nb] for nb in open_neighbors(self.walls, cell)] for cell in self.cells
        ]

        # All-pairs walking distance: one BFS per walkable cell.
        self.dist = np.full((self.n, self.n), -1, dtype=np.int32)
        for i, cell in enumerate(self.cells):
            for other, d in bfs_distances(self.walls, cell).items():
                self.dist[i, self.index[other]] = d
        self.max_distance = int(self.dist.max()) if self.n else 0

    def is_wall(self, cell: Cell) -> bool:
        return self.walls[cell[0]][cell[1]]

    def is_walkable(self, cell: Cell) -> bool:
        r, c = cell
        return 0 <= r < self.size and 0 <= c < self.size and not self.walls[r][c]

    def distance(self, a: Cell, b: Cell) -> int:
        return int(self.dist[self.index[a], self.index[b]])


@dataclass
class StepResult:
    moved: list[bool]       # per hunter: did it actually change cell this frame
    ghost_moved: bool
    caught: list[bool]      # per hunter: is it on the ghost's cell after the moves

    @property
    def hunter_moved(self) -> bool:
        return self.moved[0]


class GridEnvironment:
    """Dynamic world state plus the ghost and sensor models.

    Supports one or more hunters. Index 0 has priority in movement conflicts
    (in VS mode that is the human player).
    """

    def __init__(self, grid: GridMap, hunters: Cell | list[Cell], ghost: Cell,
                 rng: random.Random, sigma: float):
        self.grid = grid
        self.hunters: list[Cell] = list(hunters) if isinstance(hunters, list) else [hunters]
        self.ghost = ghost
        self.rng = rng
        self.sigma = sigma

    # Convenience for the single-hunter case.
    @property
    def hunter(self) -> Cell:
        return self.hunters[0]

    @hunter.setter
    def hunter(self, cell: Cell) -> None:
        self.hunters[0] = cell

    # -- Ghost model -------------------------------------------------------
    def ghost_next_cell(self) -> Cell:
        """The ghost always moves: uniform choice among open neighbours."""
        options = self.grid.neighbors[self.grid.index[self.ghost]]
        return self.grid.cells[self.rng.choice(options)]

    # -- Sensor model ------------------------------------------------------
    def sense(self, i: int = 0) -> int:
        """Reading for hunter i: max(0, round(d_BFS(hunter_i, ghost) + N(0, sigma^2)))."""
        true_d = self.grid.distance(self.hunters[i], self.ghost)
        return max(0, round(true_d + self.rng.gauss(0.0, self.sigma)))

    # -- Transition --------------------------------------------------------
    def step(self, deltas, ghost_tick: bool, active: list[bool] | None = None) -> StepResult:
        """Apply this frame's hunter moves and ghost move *simultaneously*.

        ``deltas`` is one (dr, dc)/None per hunter (a single value is accepted
        for one hunter). ``active`` marks hunters still on the board; a hunter
        that has caught the ghost is removed and no longer blocks anyone.

        Rules, all evaluated against the positions at the *start* of the frame:
          * walls and the grid edge block a move;
          * a hunter cannot step onto a cell another active hunter stands on
            (so two hunters can never swap places);
          * if two hunters step into the same empty cell, the lower index wins
            (the human player) and the other is blocked;
          * a blocked move leaves the hunter where it is and is not a move.
        A hunter catches the ghost if both end the frame on the same cell, so a
        hunter and the ghost passing each other is never a catch.
        """
        n = len(self.hunters)
        if deltas is None or isinstance(deltas, tuple):
            deltas = [deltas] + [None] * (n - 1)
        active = active if active is not None else [True] * n

        start = list(self.hunters)
        occupied = {start[j] for j in range(n) if active[j]}
        claimed: set[Cell] = set()
        new = list(start)
        moved = [False] * n
        for i in range(n):                       # index order = priority
            d = deltas[i]
            if not active[i] or d is None:
                continue
            target = (start[i][0] + d[0], start[i][1] + d[1])
            if not self.grid.is_walkable(target):
                continue
            if target in occupied or target in claimed:
                continue
            new[i] = target
            moved[i] = True
            claimed.add(target)

        new_ghost = self.ghost_next_cell() if ghost_tick else self.ghost
        self.hunters = new
        self.ghost = new_ghost
        caught = [active[i] and new[i] == new_ghost for i in range(n)]
        return StepResult(moved, ghost_tick, caught)
