"""One level of play, simulated in real time.

``GameSession`` owns the environment, every timer and cooldown, and one
``HunterState`` per hunter. It knows nothing about Pygame: the UI feeds it
frame times and reads its state back, which also makes it fully testable.

Hunters
    * Solo / turn-based: one hunter (the human, or Sir Nadeem on his turn).
    * VS-simultaneous: two hunters on the same maze, same ghost. Index 0 is
      the human (priority in movement conflicts, owns radar and hint).

A hunter that catches the ghost is removed from the board; the ghost keeps
moving until every hunter has caught it.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from config import (FLICKER_DURATION, HINT_COOLDOWN, HINT_DURATION,
                    LIKELIHOOD_EPS, PLAYER_NAME, RADAR_COOLDOWN,
                    RADAR_DURATION, RADAR_USES, SENSOR_SIGMA, Difficulty)
from .agents import HunterAgent, Percept
from .csp import Level, generate_level
from .grid import GridEnvironment, GridMap
from .hmm import BeliefTracker
from .scoring import ScoreBreakdown, compute_score
from .search import AStarResult, Cell, a_star


@dataclass
class HunterState:
    index: int
    name: str
    agent: HunterAgent
    is_ai: bool
    belief: BeliefTracker           
    moves: int = 0
    radar_uses: int = 0
    hint_uses: int = 0
    caught: bool = False
    catch_time: float | None = None
    score: ScoreBreakdown | None = None
    pending_ghost_moved: bool = False
    pending_reading: bool = False

    def time(self, elapsed: float) -> float:
        return self.catch_time if self.caught else elapsed


class GameSession:
    def __init__(self, difficulty: Difficulty, rng: random.Random,
                 agent: HunterAgent | None = None, level: Level | None = None,
                 agents: list[HunterAgent] | None = None, names: list[str] | None = None):
        self.difficulty = difficulty
        self.rng = rng
        agents = agents if agents is not None else [agent]
        if len(agents) not in (1, 2) or any(a is None for a in agents):
            raise ValueError("a session needs one or two agents")

        self.level = level or generate_level(difficulty.size, difficulty.wall_count,
                                             difficulty.min_spawn_distance, rng,
                                             with_partner=len(agents) == 2)
        starts = [self.level.hunter] if len(agents) == 1 else [self.level.hunter, self.level.partner]
        if any(s is None for s in starts):
            raise ValueError("level has no partner spawn for a two-hunter session")

        self.grid = GridMap(self.level.walls)
        self.env = GridEnvironment(self.grid, list(starts), self.level.ghost, rng, SENSOR_SIGMA)

        names = names or [getattr(a, "name", PLAYER_NAME) for a in agents]
        self.hunters: list[HunterState] = []
        for i, (ag, name) in enumerate(zip(agents, names)):
            belief = BeliefTracker(self.grid, SENSOR_SIGMA, LIKELIHOOD_EPS)
            belief.reset(starts[i])
            self.hunters.append(HunterState(i, name, ag, ag.is_ai, belief))
            ag.reset(self.grid)

        self.elapsed = 0.0
        self.caught = False          

        # Timers
        self.ghost_timer = 0.0
        self.flicker_countdown = self._next_flicker_gap()
        self.flicker_remaining = 0.0
        self.radar_remaining = 0.0
        self.radar_cooldown = 0.0
        self.hint_remaining = 0.0
        self.hint_cooldown = 0.0

        # Hint path state (human only)
        self.hint_result: AStarResult | None = None
        self.hint_target: Cell | None = None

        # Sound / visual cues consumed by the UI.
        self.events: list[str] = []

    # primary hunter
    @property
    def primary(self) -> HunterState:
        return self.hunters[0]

    @property
    def belief(self) -> BeliefTracker:
        return self.primary.belief

    @property
    def moves(self) -> int:
        return self.primary.moves

    @property
    def radar_uses(self) -> int:
        return self.primary.radar_uses

    @property
    def hint_uses(self) -> int:
        return self.primary.hint_uses

    @property
    def score(self) -> ScoreBreakdown | None:
        return self.primary.score

    @property
    def abilities_enabled(self) -> bool:
        return not self.primary.is_ai and not self.primary.caught

    # state
    @property
    def ghost_visible_on_grid(self) -> bool:
        return self.flicker_remaining > 0.0

    @property
    def ghost_visible_on_minimap(self) -> bool:
        return self.radar_remaining > 0.0

    @property
    def radar_charges(self) -> int:
        return RADAR_USES - self.primary.radar_uses

    @property
    def can_use_radar(self) -> bool:
        return self.abilities_enabled and self.radar_charges > 0 and self.radar_cooldown <= 0.0

    @property
    def can_use_hint(self) -> bool:
        return self.abilities_enabled and self.hint_cooldown <= 0.0

    @property
    def hint_active(self) -> bool:
        return self.hint_remaining > 0.0

    def active(self) -> list[bool]:
        return [not h.caught for h in self.hunters]

    def percept(self, i: int = 0) -> Percept:
        h = self.hunters[i]
        sees_radar = i == 0 and not h.is_ai and self.ghost_visible_on_minimap
        sighting = self.env.ghost if (self.ghost_visible_on_grid or sees_radar) else None
        others = tuple(self.env.hunters[j] for j, o in enumerate(self.hunters) if j != i and not o.caught)
        p = Percept(self.env.hunters[i], h.belief.last_obs, sighting, self.elapsed,
                    h.pending_reading, h.pending_ghost_moved, others)
        h.pending_reading = False
        h.pending_ghost_moved = False
        return p

    # abilities
    def use_radar(self) -> bool:
        if not self.can_use_radar:
            return False
        self.primary.radar_uses += 1
        self.radar_remaining = RADAR_DURATION
        self.radar_cooldown = RADAR_COOLDOWN       
        self.primary.belief.collapse(self.env.ghost)
        if self.hint_active:
            self._refresh_hint()
        self.events.append("radar")
        return True

    def use_hint(self) -> bool:
        if not self.can_use_hint:
            return False
        self.primary.hint_uses += 1
        self.hint_remaining = HINT_DURATION
        self.hint_cooldown = HINT_COOLDOWN
        self._refresh_hint()
        self.events.append("hint")
        return True

    def _refresh_hint(self) -> None:
        hunter = self.env.hunters[0]
        self.hint_target = self.primary.belief.most_likely(hunter)
        self.hint_result = a_star(self.grid.walls, hunter, self.hint_target)

    # main step
    def update(self, dt: float) -> None:
        if self.caught:
            return

        # 1. Clocks
        self.elapsed += dt
        self.radar_cooldown = max(0.0, self.radar_cooldown - dt)
        self.hint_cooldown = max(0.0, self.hint_cooldown - dt)
        self.radar_remaining = max(0.0, self.radar_remaining - dt)
        self.hint_remaining = max(0.0, self.hint_remaining - dt)
        self._update_flicker(dt)

        # 2. Agent actions and ghost clock
        active = self.active()
        actions = [h.agent.act(self.percept(i), dt) if active[i] else None
                   for i, h in enumerate(self.hunters)]
        self.ghost_timer += dt
        ghost_tick = self.ghost_timer >= self.difficulty.ghost_interval
        if ghost_tick:
            self.ghost_timer = min(self.ghost_timer - self.difficulty.ghost_interval,
                                   self.difficulty.ghost_interval)

        # 3. Simultaneous move resolution
        result = self.env.step([a.delta if a else None for a in actions], ghost_tick, active)
        for i, h in enumerate(self.hunters):
            if result.moved[i]:
                h.moves += 1
                self.events.append("ai_step" if h.is_ai else "step")
        for i, h in enumerate(self.hunters):
            if result.caught[i]:
                self._on_catch(h)

        # 4. HMM forward filter for every hunter still hunting
        sighted = self.ghost_visible_on_grid
        for i, h in enumerate(self.hunters):
            if h.caught:
                continue
            if result.ghost_moved:
                h.belief.predict()
                h.pending_ghost_moved = True
            if result.ghost_moved or result.moved[i]:
                h.belief.update(self.env.sense(i), self.env.hunters[i])
                h.pending_reading = True
            h.belief.exclude(self.env.hunters[i])

            # 5. Perfect observation while the ghost is visible to this hunter
            radar_view = i == 0 and not h.is_ai and self.ghost_visible_on_minimap
            if sighted or radar_view:
                h.belief.collapse(self.env.ghost)

        if self.hint_active and self.abilities_enabled and (
                result.ghost_moved or result.moved[0] or sighted or self.ghost_visible_on_minimap):
            self._refresh_hint()

        if all(h.caught for h in self.hunters):
            self.caught = True
            self.flicker_remaining = 0.0
            self.radar_remaining = 0.0
            self.hint_remaining = 0.0

    def _update_flicker(self, dt: float) -> None:
        if self.flicker_remaining > 0.0:
            self.flicker_remaining = max(0.0, self.flicker_remaining - dt)
            return
        self.flicker_countdown -= dt
        if self.flicker_countdown <= 0.0:
            self.flicker_remaining = FLICKER_DURATION
            self.flicker_countdown = self._next_flicker_gap()
            self.events.append("flicker")

    def _next_flicker_gap(self) -> float:
        return self.rng.uniform(self.difficulty.flicker_min, self.difficulty.flicker_max)

    def _on_catch(self, h: HunterState) -> None:
        h.caught = True
        h.catch_time = self.elapsed
        h.score = compute_score(self.elapsed, h.moves, self.difficulty.multiplier,
                                h.radar_uses, h.hint_uses)
        if h.index == 0:
            self.radar_remaining = 0.0
            self.hint_remaining = 0.0
        self.events.append("ai_catch" if h.is_ai else "catch")
