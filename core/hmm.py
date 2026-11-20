from __future__ import annotations

import numpy as np

from .grid import GridMap
from .search import Cell


class BeliefTracker:
    def __init__(self, grid: GridMap, sigma: float, eps: float):
        self.grid = grid
        self.sigma = sigma
        self.eps = eps
        self.T = self._build_transition(grid)
        self.belief = np.full(grid.n, 1.0 / grid.n)
        self.last_obs: int | None = None

    @staticmethod
    def _build_transition(grid: GridMap) -> np.ndarray:
        T = np.zeros((grid.n, grid.n))
        for i, nbs in enumerate(grid.neighbors):
            if nbs:
                T[i, nbs] = 1.0 / len(nbs)
            else: 
                T[i, i] = 1.0
        return T

    def reset(self, hunter: Cell) -> None:
        self.belief = np.full(self.grid.n, 1.0 / self.grid.n)
        self.last_obs = None
        self.exclude(hunter)

    def predict(self) -> None:
        self.belief = self.belief @ self.T
        self._normalise()

    def likelihood(self, obs: int, hunter: Cell) -> np.ndarray:
        d = self.grid.dist[self.grid.index[hunter]]
        return np.exp(-((obs - d) ** 2) / (2.0 * self.sigma ** 2)) + self.eps

    def update(self, obs: int, hunter: Cell) -> None:
        self.last_obs = obs
        self.belief = self.belief * self.likelihood(obs, hunter)
        self._normalise()

    def exclude(self, cell: Cell) -> None:
        self.belief[self.grid.index[cell]] = 0.0
        self._normalise()

    def collapse(self, cell: Cell) -> None:
        self.belief = np.zeros(self.grid.n)
        self.belief[self.grid.index[cell]] = 1.0

    def most_likely(self, hunter: Cell) -> Cell:
        best = self.belief.max()
        candidates = np.flatnonzero(self.belief >= best - 1e-12)
        if len(candidates) > 1:
            d = self.grid.dist[self.grid.index[hunter], candidates]
            candidates = candidates[d == d.min()]
        return self.grid.cells[int(candidates[0])]

    def probability(self, cell: Cell) -> float:
        return float(self.belief[self.grid.index[cell]])

    def as_grid(self) -> np.ndarray:
        out = np.zeros((self.grid.size, self.grid.size))
        for i, (r, c) in enumerate(self.grid.cells):
            out[r, c] = self.belief[i]
        return out

    def _normalise(self) -> None:
        total = self.belief.sum()
        if not np.isfinite(total) or total <= 1e-300:
            self.belief = np.full(self.grid.n, 1.0 / self.grid.n)
        else:
            self.belief /= total
