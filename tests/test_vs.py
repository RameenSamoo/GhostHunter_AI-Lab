"""VS-AI rules"""

import random
from datetime import date

import pytest

from config import AI_NAME, DIFFICULTIES, MODE_SIMULTANEOUS, MODE_SOLO, MODE_TURNS
from core.agents import Action, HunterAgent, KeyboardAgent, Percept
from core.ai_agent import AIHunterAgent
from core.csp import PARTNER_OFFSETS, CSPStats, Level, generate_level
from core.grid import GridEnvironment, GridMap
from core.match import TurnMatch, decide_winner, simultaneous_session
from core.scoring import compute_score
from core.search import is_connected, manhattan
from core.session import GameSession

BEGINNER = DIFFICULTIES[0]


class Idle(HunterAgent):
    def act(self, p, dt):
        return None


class Scripted(HunterAgent):
    def __init__(self, actions=()):
        self.queue = list(actions)

    def act(self, p, dt):
        return self.queue.pop(0) if self.queue else None


class ScriptedAI(Scripted):
    """Scripted moves, but flagged as the AI hunter."""
    is_ai = True


def open_env(hunters, ghost=(7, 7), size=8):
    grid = GridMap([[False] * size for _ in range(size)])
    return GridEnvironment(grid, list(hunters), ghost, random.Random(0), 1.5)


# --------------------------------------------------------------------- blocking
def test_cannot_step_onto_other_hunter():
    env = open_env([(3, 3), (4, 3)])
    res = env.step([Action.DOWN.delta, None], ghost_tick=False)
    assert env.hunters == [(3, 3), (4, 3)] and res.moved == [False, False]


def test_cannot_swap_places():
    env = open_env([(3, 3), (4, 3)])
    env.step([Action.DOWN.delta, Action.UP.delta], ghost_tick=False)
    assert env.hunters == [(3, 3), (4, 3)]


def test_cannot_follow_into_cell_being_vacated():
    # Rule is evaluated against start-of-frame positions.
    env = open_env([(3, 3), (4, 3)])
    env.step([Action.DOWN.delta, Action.DOWN.delta], ghost_tick=False)
    assert env.hunters == [(3, 3), (5, 3)]


def test_same_empty_cell_goes_to_human():
    env = open_env([(3, 3), (3, 5)])
    res = env.step([Action.RIGHT.delta, Action.LEFT.delta], ghost_tick=False)
    assert env.hunters == [(3, 4), (3, 5)] and res.moved == [True, False]


def test_removed_hunter_no_longer_blocks():
    env = open_env([(3, 3), (4, 3)])
    env.step([Action.DOWN.delta, None], ghost_tick=False, active=[True, False])
    assert env.hunters[0] == (4, 3)


# ---------------------------------------------------------------- partner spawn
@pytest.mark.parametrize("difficulty", DIFFICULTIES, ids=lambda d: d.key)
@pytest.mark.parametrize("seed", range(5))
def test_partner_spawn_constraints(difficulty, seed):
    lvl = generate_level(difficulty.size, difficulty.wall_count, difficulty.min_spawn_distance,
                         random.Random(seed), with_partner=True)
    h, p, g = lvl.hunter, lvl.partner, lvl.ghost
    assert is_connected(lvl.walls)
    assert not lvl.walls[p[0]][p[1]]                                  # floor
    assert manhattan(h, p) == 1                                       # C6 side by side
    assert p != g and manhattan(p, g) >= difficulty.min_spawn_distance  # C7
    assert manhattan(h, g) >= difficulty.min_spawn_distance           # C5 still holds
    # Preference order: the first valid neighbour in (below, above, right, left).
    for dr, dc in PARTNER_OFFSETS:
        cand = (h[0] + dr, h[1] + dc)
        if cand == p:
            break
        r, c = cand
        valid = (0 <= r < difficulty.size and 0 <= c < difficulty.size and not lvl.walls[r][c]
                 and cand != g and manhattan(cand, g) >= difficulty.min_spawn_distance)
        assert not valid, "an earlier-preferred neighbour was valid"


def test_solo_level_has_no_partner():
    d = DIFFICULTIES[1]
    assert generate_level(d.size, d.wall_count, d.min_spawn_distance, random.Random(1)).partner is None


# -------------------------------------------------------------------- the agent
@pytest.mark.parametrize("difficulty", DIFFICULTIES, ids=lambda d: d.key)
def test_sir_nadeem_catches_the_ghost(difficulty):
    for seed in range(3):
        s = GameSession(difficulty, random.Random(seed), agents=[AIHunterAgent()])
        while not s.caught and s.elapsed < 120:
            s.update(1 / 60)
        assert s.caught
        assert s.primary.radar_uses == 0 and s.primary.hint_uses == 0


def test_ai_never_faster_than_a_held_key():
    grid = GridMap([[False] * 16 for _ in range(16)])
    for dt in (1 / 30, 1 / 60, 1 / 144):
        kb = KeyboardAgent()
        kb.key_down(Action.RIGHT)
        kt, t = [], 0.0
        for _ in range(int(5 / dt)):
            t += dt
            if kb.act(Percept((0, 0), None, None, t), dt):
                kt.append(t)
        kb_gap = min(b - a for a, b in zip(kt[1:], kt[2:]))

        ai = AIHunterAgent()
        ai.reset(grid)
        pos, t, times = (0, 0), 0.0, []
        for _ in range(int(6 / dt)):
            t += dt
            blocked = 1.0 < t < 1.2 or 2.0 < t < 2.0 + dt * 1.5
            others = tuple(c for c in ((pos[0], pos[1] + 1), (pos[0] + 1, pos[1]))
                           if c[0] < 16 and c[1] < 16) if blocked else ()
            a = ai.act(Percept(pos, None, (15, 15), t, others=others), dt)
            if a:
                pos = (pos[0] + a.delta[0], pos[1] + a.delta[1])
                assert pos not in others
                times.append(t)
            if pos == (15, 15):
                break
        assert min(b - a for a, b in zip(times, times[1:])) >= kb_gap - 1e-9


def test_ai_percept_has_no_ghost_position_except_flicker():
    s = simultaneous_session(BEGINNER, random.Random(3), Idle(), AIHunterAgent())
    assert s.percept(1).sighting is None
    s.use_radar()                                   # the human's radar
    assert s.percept(0).sighting == s.env.ghost     # human sees it on the minimap
    assert s.percept(1).sighting is None            # Sir Nadeem gets no benefit
    s.flicker_remaining = 0.3                       # visible to everyone on the grid
    assert s.percept(1).sighting == s.env.ghost


def test_radar_does_not_change_ai_belief():
    s = simultaneous_session(BEGINNER, random.Random(4), Idle(), AIHunterAgent())
    before = s.hunters[1].belief.belief.copy()
    s.use_radar()
    assert (s.hunters[1].belief.belief == before).all()
    assert s.hunters[0].belief.probability(s.env.ghost) == 1.0


def test_ai_cannot_use_abilities_on_its_turn():
    s = GameSession(BEGINNER, random.Random(0), agents=[AIHunterAgent()])
    assert not s.use_radar() and not s.use_hint()


# ---------------------------------------------------------------- simultaneous
def test_simultaneous_spawns_side_by_side():
    s = simultaneous_session(DIFFICULTIES[2], random.Random(9), Idle(), AIHunterAgent())
    assert manhattan(s.env.hunters[0], s.env.hunters[1]) == 1
    assert s.hunters[1].name == AI_NAME and s.hunters[1].is_ai


def test_game_continues_after_ai_catch_until_human_catches():
    # Open 8x8. Human at (0,0), Sir Nadeem at (4,3), ghost right next to him at (4,4).
    walls = [[False] * 8 for _ in range(8)]
    level = Level(walls, (0, 0), (4, 4), CSPStats(), partner=(4, 3))
    human, ai = Scripted(), ScriptedAI([Action.RIGHT])
    s = GameSession(BEGINNER, random.Random(0), agents=[human, ai], names=["You", AI_NAME], level=level)

    s.update(0.016)                                 # AI steps onto the ghost (no ghost tick yet)
    assert s.hunters[1].caught and not s.hunters[0].caught
    assert not s.caught                             # game continues for the human
    assert "ai_catch" in s.events

    ghost_before = s.env.ghost
    s.ghost_timer = BEGINNER.ghost_interval         # force a ghost tick
    s.update(0.016)
    assert s.env.ghost != ghost_before              # the ghost keeps wandering

    # The human now lands on the ghost: session over, both results recorded.
    gr, gc = s.env.ghost
    s.env.hunters[0] = (gr, gc - 1) if gc > 0 else (gr, gc + 1)
    human.queue = [Action.RIGHT if gc > 0 else Action.LEFT]
    s.ghost_timer = -999                            # ghost holds still this frame
    s.update(0.016)
    assert s.hunters[0].caught and s.caught
    assert s.hunters[1].catch_time < s.hunters[0].catch_time
    assert s.hunters[1].score is not None and s.hunters[0].score is not None


def test_human_catch_first_then_ai_finishes():
    s = simultaneous_session(BEGINNER, random.Random(11), Idle(), AIHunterAgent())
    s._on_catch(s.hunters[0])
    assert not s.caught
    while not s.caught and s.elapsed < 120:
        s.update(1 / 60)
    assert s.caught and s.hunters[1].caught


# ------------------------------------------------------------------- turn-based
@pytest.mark.parametrize("ai_first", [False, True])
def test_turn_match_same_level_and_target(ai_first):
    m = TurnMatch(DIFFICULTIES[1], random.Random(2), Idle(), AIHunterAgent(), ai_first)
    first = m.current
    assert first == ("ai" if ai_first else "player")
    assert m.target is None
    s1 = m.session
    start = (s1.env.hunters[0], s1.env.ghost)
    s1._on_catch(s1.primary)
    s1.caught = True
    assert m.advance() is True
    s2 = m.session
    assert s2 is not s1 and s2.level is s1.level
    assert (s2.env.hunters[0], s2.env.ghost) == start
    assert m.target is s1.primary.score
    assert s2.primary.is_ai == (not ai_first)
    s2._on_catch(s2.primary)
    s2.caught = True
    assert m.advance() is False and m.finished
    assert set(m.results) == {"player", "ai"}


def test_decide_winner():
    a = compute_score(10, 10, 1.0, 0, 0)
    b = compute_score(20, 10, 1.0, 0, 0)
    assert decide_winner(a, b) == "player"
    assert decide_winner(b, a) == "ai"
    assert decide_winner(a, a) == "tie"
    with_hints = compute_score(10, 10, 1.0, 0, 1)     # hints reduce the human's score
    assert decide_winner(with_hints, a) == "ai"
