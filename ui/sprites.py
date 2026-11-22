"""Procedural pixel-art sprites.

Characters are defined as 16x16 character maps plus a palette; tiles and
icons are drawn procedurally from a fixed seed. Everything is rendered at
native 16x16, saved to assets/ as PNG, and scaled up with nearest-neighbour
filtering so it keeps the crisp pixel-art look at any cell size.
"""

from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import pygame

# --------------------------------------------------------------------------
# Character maps
# --------------------------------------------------------------------------
HUNTER_MAP = (
    "................",
    "......kkkk......",
    ".....khhhhk.....",
    ".....khhhhk.....",
    "....kbbbbbbk....",
    "...khhhhhhhhk...",
    "....kssssssk....",
    "....ksessesk....",
    ".....kssssk.....",
    "...kcCccccCck...",
    "..kccCccccCcck..",
    "..kskCccccCksk..",
    "....kcccccck.l..",
    "....kppkppk.lLl.",
    "....kppkppk.lyl.",
    "....kwwkwwk.lll.",
)
HUNTER_PALETTE = {
    "k": (14, 12, 18, 255),     # outline
    "h": (58, 40, 28, 255),     # hat
    "b": (150, 110, 50, 255),   # hat band (brass)
    "s": (222, 178, 136, 255),  # skin
    "e": (20, 14, 14, 255),     # eyes
    "c": (44, 58, 70, 255),     # coat
    "C": (78, 98, 118, 255),    # coat lapel highlight
    "p": (30, 32, 42, 255),     # trousers
    "w": (26, 18, 14, 255),     # boots
    "l": (120, 88, 36, 255),    # lantern frame
    "L": (255, 206, 90, 255),   # lantern glow
    "y": (255, 244, 190, 255),  # lantern core
}

# Sir Nadeem: same figure, violet coat, silver hat band, violet lantern.
AI_HUNTER_PALETTE = dict(HUNTER_PALETTE, **{
    "h": (30, 22, 42, 255),
    "b": (196, 198, 212, 255),
    "c": (66, 38, 96, 255),
    "C": (128, 86, 178, 255),
    "p": (28, 24, 40, 255),
    "l": (110, 90, 150, 255),
    "L": (200, 150, 255, 255),
    "y": (240, 225, 255, 255),
})

GHOST_MAP = (
    "................",
    ".....kkkkkk.....",
    "....kgggggGk....",
    "...kggggggGGk...",
    "..kgggggggggGk..",
    "..kggEEggEEgGk..",
    "..kggEEggEEggk..",
    "..kgggggggggGk..",
    "..kgggggmmggGk..",
    "..kggggmmmmgGk..",
    "..kgggggmmgggk..",
    "..kgggggggggGk..",
    "..kgggggggggGk..",
    "..kggggggggggk..",
    "..kgk.kggk.kgk..",
    "...k...kk...k...",
)
GHOST_PALETTE = {
    "k": (40, 150, 170, 210),
    "g": (150, 250, 240, 175),
    "G": (80, 190, 205, 175),
    "E": (6, 16, 26, 235),
    "m": (8, 30, 40, 215),
}

for _name, _rows in (("HUNTER_MAP", HUNTER_MAP), ("GHOST_MAP", GHOST_MAP)):
    assert len(_rows) == 16 and all(len(r) == 16 for r in _rows), f"{_name} must be 16x16"


def render_map(rows: tuple[str, ...], palette: dict[str, tuple[int, int, int, int]]) -> pygame.Surface:
    surf = pygame.Surface((len(rows[0]), len(rows)), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in palette:
                surf.set_at((x, y), palette[ch])
    return surf


# --------------------------------------------------------------------------
# Procedural tiles
# --------------------------------------------------------------------------
def _clamp(v: float) -> int:
    return max(0, min(255, int(v)))


def make_wall_tile(seed: int) -> pygame.Surface:
    """Dark slate stone blocks in a running-bond pattern."""
    rng = random.Random(seed)
    surf = pygame.Surface((16, 16))
    mortar = (12, 13, 17)
    surf.fill(mortar)
    rows = [(0, 5), (5, 5), (10, 6)]
    for i, (y0, h) in enumerate(rows):
        offset = 0 if i % 2 == 0 else 4
        x = -offset
        while x < 16:
            w = rng.choice((7, 8, 8, 9))
            base = rng.randint(52, 70)
            tint = rng.randint(-4, 6)
            for yy in range(y0, min(16, y0 + h - 1)):
                for xx in range(max(0, x), min(16, x + w - 1)):
                    n = rng.randint(-7, 7)
                    shade = base + n
                    if yy == y0:            # top highlight
                        shade += 16
                    elif yy == y0 + h - 2:  # bottom shadow
                        shade -= 14
                    surf.set_at((xx, yy), (_clamp(shade - 4), _clamp(shade + tint), _clamp(shade + 10)))
            x += w
    # A few cracks and moss flecks
    for _ in range(rng.randint(1, 3)):
        cx, cy = rng.randrange(16), rng.randrange(16)
        for _ in range(rng.randint(2, 4)):
            if 0 <= cx < 16 and 0 <= cy < 16:
                surf.set_at((cx, cy), (22, 24, 30))
            cx += rng.choice((-1, 0, 1))
            cy += 1
    for _ in range(rng.randint(0, 2)):
        surf.set_at((rng.randrange(16), rng.randrange(16)), (40, 62, 50))
    return surf


def make_floor_tile(seed: int) -> pygame.Surface:
    """Worn dark cobblestones."""
    rng = random.Random(seed)
    surf = pygame.Surface((16, 16))
    surf.fill((16, 17, 22))
    # Jittered 3x3 grid of stones, each a rounded blob.
    centres = [(4 + 6 * gx + rng.randint(-1, 1), 3 + 5 * gy + rng.randint(-1, 1))
               for gx in range(3) for gy in range(4)]
    for cx, cy in centres:
        base = rng.randint(30, 40)
        rx, ry = rng.uniform(2.2, 3.2), rng.uniform(1.8, 2.5)
        for y in range(16):
            for x in range(16):
                dx, dy = (x - cx) / rx, (y - cy) / ry
                if dx * dx + dy * dy <= 1.0:
                    shade = base + rng.randint(-3, 3) + (4 if dy < -0.3 else 0) - (5 if dy > 0.5 else 0)
                    surf.set_at((x, y), (_clamp(shade - 2), _clamp(shade), _clamp(shade + 6)))
    return surf


# --------------------------------------------------------------------------
# Icons
# --------------------------------------------------------------------------
def make_radar_icon() -> pygame.Surface:
    surf = pygame.Surface((16, 16), pygame.SRCALPHA)
    cyan = (90, 240, 230, 255)
    dim = (40, 120, 130, 255)
    pygame.draw.circle(surf, dim, (8, 8), 7, 1)
    pygame.draw.circle(surf, dim, (8, 8), 4, 1)
    pygame.draw.line(surf, cyan, (8, 8), (13, 3))
    surf.set_at((8, 8), cyan)
    surf.set_at((11, 10), cyan)
    surf.set_at((12, 10), cyan)
    return surf


def make_hint_icon() -> pygame.Surface:
    surf = pygame.Surface((16, 16), pygame.SRCALPHA)
    gold = (255, 200, 90, 255)
    for x, y in ((2, 13), (4, 11), (6, 11), (8, 9), (8, 7), (10, 5)):
        surf.set_at((x, y), gold)
        surf.set_at((x + 1, y), gold)
    pygame.draw.polygon(surf, gold, [(10, 1), (14, 5), (10, 5)])
    return surf


def make_heart_icon() -> pygame.Surface:
    rows = (
        "................",
        "................",
        "...rrr....rrr...",
        "..rRRRr..rRRRr..",
        ".rRRRRRrrRRRRRr.",
        ".rRRRRRRRRRRRRr.",
        ".rRRRRRRRRRRRRr.",
        "..rRRRRRRRRRRr..",
        "...rRRRRRRRRr...",
        "....rRRRRRRr....",
        ".....rRRRRr.....",
        "......rRRr......",
        ".......rr.......",
        "................",
        "................",
        "................",
    )
    return render_map(rows, {"r": (90, 10, 20, 255), "R": (200, 30, 50, 255)})


# --------------------------------------------------------------------------
# Atlas with scaling cache
# --------------------------------------------------------------------------
class SpriteAtlas:
    TILE_VARIANTS = 6

    def __init__(self, assets_dir: Path, force_save: bool = False):
        self.base: dict[str, pygame.Surface] = {
            "hunter": render_map(HUNTER_MAP, HUNTER_PALETTE),
            "ai_hunter": render_map(HUNTER_MAP, AI_HUNTER_PALETTE),
            "ghost": render_map(GHOST_MAP, GHOST_PALETTE),
            "radar_icon": make_radar_icon(),
            "hint_icon": make_hint_icon(),
            "heart_icon": make_heart_icon(),
        }
        for i in range(self.TILE_VARIANTS):
            self.base[f"wall_{i}"] = make_wall_tile(1000 + i)
            self.base[f"floor_{i}"] = make_floor_tile(2000 + i)
        self._cache: dict[tuple[str, int], pygame.Surface] = {}
        self._save(assets_dir, force_save)

    def _save(self, assets_dir: Path, force: bool) -> None:
        try:
            assets_dir.mkdir(parents=True, exist_ok=True)
            for name, surf in self.base.items():
                path = assets_dir / f"{name}.png"
                if force or not path.exists():
                    pygame.image.save(pygame.transform.scale(surf, (64, 64)), str(path))
        except (OSError, pygame.error):
            pass  # Saving is a convenience; the game never reads these back.

    def get(self, name: str, size: int) -> pygame.Surface:
        key = (name, size)
        if key not in self._cache:
            surf = pygame.transform.scale(self.base[name], (size, size))
            # Convert once the display exists for much faster blits.
            if pygame.display.get_surface() is not None:
                surf = surf.convert_alpha()
            self._cache[key] = surf
        return self._cache[key]

    def tile(self, kind: str, cell: tuple[int, int], size: int) -> pygame.Surface:
        """Deterministic variant per cell so the floor doesn't look tiled."""
        r, c = cell
        variant = (r * 73856093 ^ c * 19349663) % self.TILE_VARIANTS
        return self.get(f"{kind}_{variant}", size)


def radial_gradient(radius: int, colour: tuple[int, int, int], peak_alpha: int,
                    falloff: float = 2.0) -> pygame.Surface:
    """Soft round light (torchlight, ghost aura, fog, darkness holes).

    Colour is premultiplied by intensity, so the surface works both with
    normal alpha blits and with additive blending (BLEND_RGB_ADD, which
    ignores alpha). The alpha channel carries the same falloff, which is
    what BLEND_RGBA_SUB uses to punch light holes into darkness.
    """
    radius = max(2, int(radius))
    size = radius * 2
    yy, xx = np.mgrid[0:size, 0:size]
    d = np.hypot(xx - radius + 0.5, yy - radius + 0.5) / radius
    k = np.clip(1.0 - d, 0.0, 1.0) ** falloff * (peak_alpha / 255.0)
    rgba = np.empty((size, size, 4), dtype=np.uint8)
    for i in range(3):
        rgba[..., i] = (colour[i] * k).astype(np.uint8)
    rgba[..., 3] = (255 * k).astype(np.uint8)
    surf = pygame.image.frombuffer(rgba.tobytes(), (size, size), "RGBA").copy()
    return surf.convert_alpha() if pygame.display.get_surface() is not None else surf
