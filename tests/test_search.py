import random

import numpy as np

from config import DIFFICULTIES
from core.csp import generate_level
from core.grid import GridMap
from core.search import a_star, bfs_distances, is_connected, is_valid_path


def _grid(seed=0, difficulty=DIFFICULTIES[3]):
    level = generate_level(difficulty.size, difficulty.wall_count,
                           difficulty.min_spawn_distance, random.Random(seed))
    return GridMap(level.walls)


def test_a_star_is_optimal_and_valid():
    rng = random.Random(7)
    for seed in range(3):
        grid = _grid(seed)
        for _ in range(60):
            a, b = rng.choice(grid.cells), rng.choice(grid.cells)
            res = a_star(grid.walls, a, b)
            assert res.found
            assert res.path[0] == a and res.path[-1] == b
            assert is_valid_path(grid.walls, res.path)
            assert res.cost == grid.distance(a, b)


def test_a_star_expands_no_more_than_bfs_reach():
    grid = _grid(3)
    a, b = grid.cells[0], grid.cells[-1]
    assert a_star(grid.walls, a, b).nodes_expanded <= grid.n


def test_a_star_unreachable_goal():
    walls = [[False, True, False],
             [False, True, False],
             [False, True, False]]
    res = a_star(walls, (0, 0), (0, 2))
    assert not res.found and res.path == []


def test_distance_matrix_symmetric_and_complete():
    grid = _grid(1)
    assert (grid.dist >= 0).all()
    assert np.array_equal(grid.dist, grid.dist.T)
    assert (np.diag(grid.dist) == 0).all()


def test_bfs_and_connectivity_basics():
    walls = [[False, False], [True, False]]
    d = bfs_distances(walls, (0, 0))
    assert d == {(0, 0): 0, (0, 1): 1, (1, 1): 2}
    assert is_connected(walls)
    assert not is_connected([[False, True], [True, False]])
