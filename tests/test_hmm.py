import random

import numpy as np

from config import DIFFICULTIES, LIKELIHOOD_EPS, SENSOR_SIGMA
from core.csp import generate_level
from core.grid import GridEnvironment, GridMap
from core.hmm import BeliefTracker


def _setup(seed=0, difficulty=DIFFICULTIES[1]):
    rng = random.Random(seed)
    level = generate_level(difficulty.size, difficulty.wall_count,
                           difficulty.min_spawn_distance, rng)
    grid = GridMap(level.walls)
    env = GridEnvironment(grid, level.hunter, level.ghost, rng, SENSOR_SIGMA)
    tracker = BeliefTracker(grid, SENSOR_SIGMA, LIKELIHOOD_EPS)
    tracker.reset(env.hunter)
    return grid, env, tracker


def test_transition_matrix_rows_sum_to_one_without_self_loops():
    grid, _, tracker = _setup()
    assert np.allclose(tracker.T.sum(axis=1), 1.0)
    assert np.allclose(np.diag(tracker.T), 0.0)
    for i, nbs in enumerate(grid.neighbors):
        assert set(np.flatnonzero(tracker.T[i])) == set(nbs)


def test_belief_stays_normalised_through_every_step():
    grid, env, tracker = _setup(1)
    assert np.isclose(tracker.belief.sum(), 1.0)
    assert tracker.probability(env.hunter) == 0.0
    for _ in range(50):
        tracker.predict()
        assert np.isclose(tracker.belief.sum(), 1.0)
        tracker.update(env.sense(), env.hunter)
        assert np.isclose(tracker.belief.sum(), 1.0)
        tracker.exclude(env.hunter)
        assert np.isclose(tracker.belief.sum(), 1.0)
        assert (tracker.belief >= 0).all()


def test_collapse_is_one_hot():
    grid, env, tracker = _setup(2)
    tracker.collapse(env.ghost)
    assert tracker.probability(env.ghost) == 1.0
    assert tracker.most_likely(env.hunter) == env.ghost


def test_predict_spreads_to_neighbours_only():
    grid, env, tracker = _setup(3)
    tracker.collapse(env.ghost)
    tracker.predict()
    support = {grid.cells[i] for i in np.flatnonzero(tracker.belief)}
    nbs = {grid.cells[j] for j in grid.neighbors[grid.index[env.ghost]]}
    assert support == nbs


def test_filter_tracks_the_ghost_better_than_chance():
    """Over a long random walk, the true ghost cell should carry far more
    probability than a uniform guess would give it."""
    grid, env, tracker = _setup(4)
    ratios = []
    for _ in range(300):
        env.step(None, ghost_tick=True)
        tracker.predict()
        tracker.update(env.sense(), env.hunter)
        if env.ghost != env.hunter:
            tracker.exclude(env.hunter)
        ratios.append(tracker.probability(env.ghost) * grid.n)
    assert np.mean(ratios[50:]) > 3.0
