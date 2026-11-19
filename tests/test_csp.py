import random

import pytest

from config import DIFFICULTIES
from core.csp import generate_level
from core.search import is_connected, manhattan


@pytest.mark.parametrize("difficulty", DIFFICULTIES, ids=lambda d: d.key)
@pytest.mark.parametrize("seed", range(5))
def test_generated_level_satisfies_every_constraint(difficulty, seed):
    level = generate_level(difficulty.size, difficulty.wall_count,
                           difficulty.min_spawn_distance, random.Random(seed))
    walls = level.walls

    assert len(walls) == difficulty.size and all(len(r) == difficulty.size for r in walls)
    assert sum(map(sum, walls)) == difficulty.wall_count              # C1
    assert is_connected(walls)                                        # C2
    assert not walls[level.hunter[0]][level.hunter[1]]                # C3
    assert not walls[level.ghost[0]][level.ghost[1]]                  # C3
    assert level.hunter != level.ghost                                # C4
    assert manhattan(level.hunter, level.ghost) >= difficulty.min_spawn_distance  # C5


def test_same_seed_gives_same_level():
    d = DIFFICULTIES[2]
    a = generate_level(d.size, d.wall_count, d.min_spawn_distance, random.Random(42))
    b = generate_level(d.size, d.wall_count, d.min_spawn_distance, random.Random(42))
    assert a.walls == b.walls and a.hunter == b.hunter and a.ghost == b.ghost


def test_stats_are_recorded():
    d = DIFFICULTIES[3]
    level = generate_level(d.size, d.wall_count, d.min_spawn_distance, random.Random(1))
    s = level.stats
    assert s.attempts >= 1
    assert s.wall_assignments - s.wall_undos == d.wall_count
