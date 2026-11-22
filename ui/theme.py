"""Colours and fonts for the gothic look."""

from __future__ import annotations

import pygame

# Palette
BG = (8, 9, 13)
PANEL = (18, 20, 28)
PANEL_EDGE = (52, 58, 74)
PANEL_EDGE_HI = (96, 108, 132)
TEXT = (214, 218, 228)
TEXT_DIM = (130, 138, 156)
TEXT_FAINT = (80, 86, 102)
CYAN = (90, 240, 230)
CYAN_DIM = (40, 120, 130)
AMBER = (255, 190, 80)
AMBER_DIM = (130, 90, 40)
RED = (230, 60, 60)
VIOLET = (190, 130, 255)        # Sir Nadeem
VIOLET_DIM = (95, 65, 135)
GREEN = (90, 220, 140)
GOLD = (224, 182, 86)
SILVER = (188, 196, 210)
BRONZE = (176, 120, 74)
BRASS = (145, 118, 76)
MINIMAP_WALL = (58, 64, 80)
MINIMAP_FLOOR = (22, 25, 33)

# Heat ramp: cold spectral blue -> emerald -> amber -> hot red
HEAT_STOPS = (
    (0.00, (20, 60, 160)),
    (0.35, (20, 200, 140)),
    (0.70, (255, 180, 50)),
    (1.00, (255, 40, 40)),
)

_FONT_CACHE: dict[tuple[str, int, bool], pygame.font.Font] = {}

_FAMILIES = {
    "title": ["chiller", "georgia", "garamond", "palatinolinotype", "timesnewroman", "dejavuserif"],
    "serif": ["bookantiqua", "garamond", "palatinolinotype", "georgia", "timesnewroman", "dejavuserif"],
    "mono": ["cascadiamono", "consolas", "lucidaconsole", "couriernew", "dejavusansmono"],
    "sans": ["segoeui", "calibri", "verdana", "arial", "dejavusans"],
}


def font(kind: str, size: int, bold: bool = False) -> pygame.font.Font:
    key = (kind, size, bold)
    if key not in _FONT_CACHE:
        path = None
        for name in _FAMILIES[kind]:
            path = pygame.font.match_font(name, bold=bold)
            if path:
                break
        f = pygame.font.Font(path, size)  # path=None -> pygame default font
        if path is None:
            f.set_bold(bold)
        _FONT_CACHE[key] = f
    return _FONT_CACHE[key]


def heat_colour(t: float) -> tuple[int, int, int]:
    t = min(1.0, max(0.0, t))
    for (t0, c0), (t1, c1) in zip(HEAT_STOPS, HEAT_STOPS[1:]):
        if t <= t1:
            k = (t - t0) / (t1 - t0)
            return tuple(int(a + (b - a) * k) for a, b in zip(c0, c1))
    return HEAT_STOPS[-1][1]
