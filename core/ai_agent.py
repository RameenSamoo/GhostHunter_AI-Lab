"""Sir Nadeem: the autonomous AI hunter.

Agent type: goal-based agent with an internal model of the world.

Every frame it runs the agent cycle  perceive -> update model -> choose goal -> plan -> act:

1. Perceive  - the same Percept the human gets: own cell, own noisy
               walking-distance reading, a sighting only while the ghost
               visibly flickers, and where the other hunter stands.
2. Model     - its own HMM forward filter (core/hmm.py): predict on every
               ghost tick, Bayes update on every new reading, rule out its own
               cell (it would have caught the ghost there), collapse onto the
               ghost when it flickers into view.
3. Goal      - the most probable ghost cell (argmax of its belief).
4. Plan      - A* with the Manhattan heuristic from its cell to the goal,
               treating the other hunter's cell as blocked. It re-plans before
               every step, because the belief changes every tick.
5. Act       - take the first step of the plan, at most MOVE_REPEAT_RATE
               steps per second: exactly the human's top speed.

What it does NOT get: the ghost's true position (outside flickers), the
human's radar reveals, hints, or any speed advantage. It never uses the
radar or the hint, because both cost points and it already plans with A*.
"""

from __future__ import annotations

from config import AI_NAME, LIKELIHOOD_EPS, MOVE_REPEAT_RATE, SENSOR_SIGMA
from .agents import Action, HunterAgent, Percept
from .grid import GridMap
from .hmm import BeliefTracker
from .search import AStarResult, Cell, a_star

_ACTION_BY_DELTA = {a.delta: a for a in Action}


class AIHunterAgent(HunterAgent):
    name = AI_NAME
    is_ai = True

    def __init__(self, sigma: float = SENSOR_SIGMA, eps: float = LIKELIHOOD_EPS,
                 move_rate: float = MOVE_REPEAT_RATE):
        self.sigma = sigma
        self.eps = eps
        self.step_interval = 1.0 / move_rate
        self.grid: GridMap | None = None
        self.belief: BeliefTracker | None = None
        self.goal: Cell | None = None
        self.plan: AStarResult | None = None
        self._cooldown = 0.0
        self._started = False

    def reset(self, grid: GridMap) -> None:
        self.grid = grid
        self.belief = BeliefTracker(grid, self.sigma, self.eps)
        self.goal = None
        self.plan = None
        self._cooldown = 0.0
        self._started = False

    # cycle
    def act(self, percept: Percept, dt: float) -> Action | None:
        self._update_model(percept)

        # Speed limit: same top speed as a human holding an arrow key.
        self._cooldown -= dt
        if self._cooldown > 1e-9:            
            return None

        self.goal = self.belief.most_likely(percept.hunter)
        self.plan = self._plan(percept.hunter, self.goal, percept.others)
        if self.plan is None or len(self.plan.path) < 2:
            return None
        nxt = self.plan.path[1]
        if nxt in percept.others:
            return None                       
        if self._cooldown <= -dt + 1e-9:      
            self._cooldown = 0.0
        self._cooldown += self.step_interval
        return _ACTION_BY_DELTA[(nxt[0] - percept.hunter[0], nxt[1] - percept.hunter[1])]

    def _update_model(self, p: Percept) -> None:
        if not self._started:
            self.belief.reset(p.hunter)       
            self._started = True
        if p.ghost_moved:
            self.belief.predict()
        if p.new_reading and p.reading is not None:
            self.belief.update(p.reading, p.hunter)
        self.belief.exclude(p.hunter)         
        if p.sighting is not None:
            self.belief.collapse(p.sighting)  

    def _plan(self, start: Cell, goal: Cell, others: tuple[Cell, ...]) -> AStarResult | None:
        if others:
            walls = [list(row) for row in self.grid.walls]
            for r, c in others:
                walls[r][c] = True
            gr, gc = goal
            walls[gr][gc] = self.grid.walls[gr][gc]
            result = a_star(walls, start, goal)
            if result.found:
                return result
        result = a_star(self.grid.walls, start, goal)
        return result if result.found else None
