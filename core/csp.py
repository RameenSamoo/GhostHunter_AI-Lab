"""Level generation as a Constraint Satisfaction Problem.

Variables
    * X(r,c) for every cell, domain {WALL, FLOOR}
    * H (hunter spawn) and G (ghost spawn), domain = FLOOR cells
Constraints
    C1  exactly round(density * N^2) cells are WALL
    C2  all FLOOR cells form a single connected component (checked with BFS)
    C3  X(H) = FLOOR and X(G) = FLOOR
    C4  H != G
    C5  Manhattan(H, G) >= floor(N / 2)
VS-simultaneous mode adds the AI hunter's spawn P (domain = FLOOR cells):
    C6  P is orthogonally adjacent to H (they start side by side)
    C7  P != G and Manhattan(P, G) >= floor(N / 2)

Solving strategy
----------------
Stage 1 - walls (C1, C2): cells are visited in a random order. Each one is
    tentatively assigned WALL, then C2 is checked immediately. If the
    assignment breaks connectivity it is undone and that cell stays FLOOR.
    This is constraint checking with undo, so every partial assignment is
    always consistent with C2.
Stage 2 - spawns (C3..C7): backtracking search with forward checking.
    For each candidate value of H (and, in VS mode, of P), the domain of G is
    pruned to cells that satisfy the remaining constraints. An empty domain
    triggers a backtrack to the next value. P's values are tried in a fixed
    order (below, above, right, left of H), so with H = (3,3) the AI starts at
    (4,3) whenever that cell is valid.
If either stage fails (very rare), the whole level is regenerated.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .search import Cell, is_connected, manhattan


@dataclass
class CSPStats:
    attempts: int = 0            
    wall_assignments: int = 0    
    wall_undos: int = 0          
    spawn_backtracks: int = 0    
    log: list[str] = field(default_factory=list)


@dataclass
class Level:
    walls: list[list[bool]]
    hunter: Cell
    ghost: Cell
    stats: CSPStats
    partner: Cell | None = None      


class GenerationError(RuntimeError):
    pass


PARTNER_OFFSETS: tuple[Cell, ...] = ((1, 0), (-1, 0), (0, 1), (0, -1))


def generate_level(size: int, wall_count: int, min_spawn_distance: int,
                   rng: random.Random, max_attempts: int = 100,
                   with_partner: bool = False) -> Level:
    stats = CSPStats()
    for _ in range(max_attempts):
        stats.attempts += 1
        walls = _place_walls(size, wall_count, rng, stats)
        if walls is None:
            stats.log.append("wall stage could not reach target count; regenerating")
            continue
        spawns = _assign_spawns(walls, min_spawn_distance, rng, stats, with_partner)
        if spawns is None:
            stats.log.append("no valid spawn assignment; regenerating")
            continue
        hunter, ghost, partner = spawns
        return Level(walls, hunter, ghost, stats, partner)
    raise GenerationError(f"could not generate a {size}x{size} level in {max_attempts} attempts")


def _place_walls(size: int, wall_count: int, rng: random.Random,
                 stats: CSPStats) -> list[list[bool]] | None:
    walls = [[False] * size for _ in range(size)]
    order = [(r, c) for r in range(size) for c in range(size)]
    rng.shuffle(order)

    placed = 0
    for r, c in order:
        if placed == wall_count:
            break
        walls[r][c] = True
        stats.wall_assignments += 1
        if is_connected(walls):
            placed += 1
        else:
            walls[r][c] = False
            stats.wall_undos += 1

    return walls if placed == wall_count else None


def _assign_spawns(walls: list[list[bool]], min_distance: int, rng: random.Random,
                   stats: CSPStats, with_partner: bool = False) -> tuple[Cell, Cell, Cell | None] | None:
    size = len(walls)
    floors = [(r, c) for r in range(size) for c in range(size) if not walls[r][c]]

    hunter_domain = floors[:]
    rng.shuffle(hunter_domain)
    for hunter in hunter_domain:
        if with_partner:
            partner_domain = [(hunter[0] + dr, hunter[1] + dc) for dr, dc in PARTNER_OFFSETS]
            partner_domain = [p for p in partner_domain                                   # C6
                              if 0 <= p[0] < size and 0 <= p[1] < size and not walls[p[0]][p[1]]]
        else:
            partner_domain = [None]

        for partner in partner_domain:
            ghost_domain = [g for g in floors
                            if g != hunter and manhattan(hunter, g) >= min_distance        
                            and (partner is None
                                 or (g != partner and manhattan(partner, g) >= min_distance))]  
            if ghost_domain:
                return hunter, rng.choice(ghost_domain), partner
            stats.spawn_backtracks += 1
    return None
