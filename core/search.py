"""
* BFS  - connectivity checking (CSP) and true walking distances (sensor model).
* A*   - shortest path for the player's hint, using the Manhattan heuristic.
"""

from __future__ import annotations

import heapq
from collections import deque
from itertools import count
from typing import Iterable, Sequence

Cell = tuple[int, int]

# up, down, left, right.
DIRECTIONS: tuple[Cell, ...] = ((-1, 0), (1, 0), (0, -1), (0, 1))


def in_bounds(size: int, cell: Cell) -> bool:
    r, c = cell
    return 0 <= r < size and 0 <= c < size


def open_neighbors(walls: Sequence[Sequence[bool]], cell: Cell) -> list[Cell]:
    size = len(walls)
    r, c = cell
    result = []
    for dr, dc in DIRECTIONS:
        nr, nc = r + dr, c + dc
        if 0 <= nr < size and 0 <= nc < size and not walls[nr][nc]:
            result.append((nr, nc))
    return result


def manhattan(a: Cell, b: Cell) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def bfs_distances(walls: Sequence[Sequence[bool]], start: Cell) -> dict[Cell, int]:
    dist = {start: 0}
    frontier = deque([start])
    while frontier:
        cell = frontier.popleft()
        for nxt in open_neighbors(walls, cell):
            if nxt not in dist:
                dist[nxt] = dist[cell] + 1
                frontier.append(nxt)
    return dist


def is_connected(walls: Sequence[Sequence[bool]]) -> bool:
    size = len(walls)
    open_cells = [(r, c) for r in range(size) for c in range(size) if not walls[r][c]]
    if not open_cells:
        return False
    reached = bfs_distances(walls, open_cells[0])
    return len(reached) == len(open_cells)


class AStarResult:
    __slots__ = ("path", "nodes_expanded")

    def __init__(self, path: list[Cell], nodes_expanded: int):
        self.path = path
        self.nodes_expanded = nodes_expanded

    @property
    def cost(self) -> int:
        return max(0, len(self.path) - 1)

    @property
    def found(self) -> bool:
        return bool(self.path)


def a_star(walls: Sequence[Sequence[bool]], start: Cell, goal: Cell) -> AStarResult:
    if start == goal:
        return AStarResult([start], 0)

    tie = count()
    g_cost = {start: 0}
    parent: dict[Cell, Cell] = {}
    h0 = manhattan(start, goal)
    open_heap = [(h0, h0, next(tie), start)]
    closed: set[Cell] = set()
    expanded = 0

    while open_heap:
        _, _, _, cell = heapq.heappop(open_heap)
        if cell in closed:
            continue
        closed.add(cell)
        expanded += 1
        if cell == goal:
            return AStarResult(_reconstruct(parent, goal), expanded)
        for nxt in open_neighbors(walls, cell):
            new_g = g_cost[cell] + 1
            if nxt in closed or new_g >= g_cost.get(nxt, 1 << 30):
                continue
            g_cost[nxt] = new_g
            parent[nxt] = cell
            h = manhattan(nxt, goal)
            heapq.heappush(open_heap, (new_g + h, h, next(tie), nxt))

    return AStarResult([], expanded)


def _reconstruct(parent: dict[Cell, Cell], goal: Cell) -> list[Cell]:
    path = [goal]
    while path[-1] in parent:
        path.append(parent[path[-1]])
    path.reverse()
    return path


def is_valid_path(walls: Sequence[Sequence[bool]], path: Iterable[Cell]) -> bool:
    cells = list(path)
    for cell in cells:
        if walls[cell[0]][cell[1]]:
            return False
    return all(manhattan(a, b) == 1 for a, b in zip(cells, cells[1:]))
