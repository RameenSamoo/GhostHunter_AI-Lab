"""Real-time rules: catch resolution, counters, abilities, timers."""

import random

from config import DIFFICULTIES, HINT_PENALTY, RADAR_USES
from core.agents import Action, HunterAgent, KeyboardAgent, Percept
from core.csp import CSPStats, Level
from core.session import GameSession

BEGINNER = DIFFICULTIES[0]


class Scripted(HunterAgent):
    """Returns queued actions, one per frame."""

    def __init__(self, actions=()):
        self.queue = list(actions)

    def act(self, percept: Percept, dt: float):
        return self.queue.pop(0) if self.queue else None


def open_level(hunter, ghost, size=8):
    walls = [[False] * size for _ in range(size)]
    return Level(walls, hunter, ghost, CSPStats())


def corridor_level(hunter, ghost):
    """1-wide horizontal corridor on row 0; everything else is wall."""
    walls = [[r != 0 for _ in range(8)] for r in range(8)]
    return Level(walls, hunter, ghost, CSPStats())


def make_session(level, agent=None, seed=0):
    return GameSession(BEGINNER, random.Random(seed), agent or Scripted(), level=level)


def test_swap_does_not_catch():
    # Corridor: hunter (0,3) -> right, ghost (0,4) can only go left or right.
    for seed in range(40):
        s = make_session(corridor_level((0, 3), (0, 4)), Scripted([Action.RIGHT]), seed)
        s.ghost_timer = BEGINNER.ghost_interval          # force a ghost tick this frame
        s.update(0.016)
        if s.env.ghost == (0, 3):                        # they swapped
            assert not s.caught
            return
    raise AssertionError("no swap occurred in 40 seeds")


def test_hunter_landing_on_ghost_catches():
    s = make_session(open_level((0, 0), (0, 1)), Scripted([Action.RIGHT]))
    s.update(0.016)                                      # no ghost tick yet
    assert s.caught and s.score is not None and s.moves == 1


def test_ghost_avoids_stationary_hunter_in_dead_end():
    # Dead end: ghost at (0,7) has only neighbour (0,6), where the hunter stands.
    s = make_session(corridor_level((0, 6), (0, 7)))
    s.ghost_timer = BEGINNER.ghost_interval
    s.update(0.016)
    assert not s.caught and s.env.ghost == (0, 7) and s.moves == 0


def test_ghost_avoids_stationary_hunter_when_other_moves_exist():
    # Corridor: ghost at (0,5) has neighbours (0,4) [hunter] and (0,6) [open].
    for seed in range(20):
        s = make_session(corridor_level((0, 4), (0, 5)), seed=seed)
        s.ghost_timer = BEGINNER.ghost_interval
        s.update(0.016)
        assert not s.caught and s.env.ghost == (0, 6)


def test_walls_block_without_counting_a_move():
    s = make_session(corridor_level((0, 0), (0, 7)), Scripted([Action.UP, Action.DOWN, Action.LEFT]))
    for _ in range(3):
        s.update(0.016)
    assert s.env.hunter == (0, 0) and s.moves == 0


def test_radar_charges_cooldown_and_penalty():
    s = make_session(open_level((0, 0), (7, 7)))
    assert s.use_radar() and s.radar_charges == RADAR_USES - 1
    assert s.belief.probability(s.env.ghost) == 1.0     # sighting collapses belief
    assert not s.use_radar()                            # on cooldown
    for _ in range(int(5.1 / 0.05)):
        s.update(0.05)
        if s.caught:
            return
    assert s.use_radar() and s.use_radar() is False     # cooldown again
    s.radar_cooldown = 0
    assert s.use_radar()
    s.radar_cooldown = 0
    assert not s.use_radar()                            # out of charges


def test_hint_unlimited_with_cooldown():
    s = make_session(open_level((0, 0), (7, 7)))
    assert s.use_hint() and s.hint_result.found
    assert s.hint_result.path[0] == s.env.hunter
    assert not s.use_hint()
    s.hint_cooldown = 0
    assert s.use_hint() and s.hint_uses == 2
    s._on_catch(s.primary)
    assert s.score.hint_penalty == 2 * HINT_PENALTY


def test_ghost_moves_on_its_own_clock():
    s = make_session(open_level((0, 0), (7, 7)))
    start = s.env.ghost
    s.update(BEGINNER.ghost_interval * 0.5)
    assert s.env.ghost == start
    s.update(BEGINNER.ghost_interval * 0.6)
    assert s.env.ghost != start


def test_flicker_happens_within_interval():
    s = make_session(open_level((0, 0), (7, 7)))
    seen = False
    t = 0.0
    while t < BEGINNER.flicker_max + 0.5 and not s.caught:
        s.update(0.02)
        t += 0.02
        seen |= s.ghost_visible_on_grid
    assert seen or s.caught


def test_keyboard_agent_auto_repeat_rate():
    agent = KeyboardAgent()
    p = Percept((0, 0), None, None, 0.0)
    agent.key_down(Action.RIGHT)
    moves = 0
    dt = 1 / 120
    for _ in range(int(1.2 / dt)):                      # hold for 1.2 s
        if agent.act(p, dt):
            moves += 1
    # 1 immediate + repeats during the remaining 1.0 s at 6/s
    assert 6 <= moves <= 8
    agent.key_up(Action.RIGHT)
    assert agent.act(p, dt) is None
