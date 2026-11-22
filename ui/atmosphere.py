"""Shared horror atmosphere: drifting fog, vignette and floating motes."""

from __future__ import annotations

import math
import random

import numpy as np
import pygame

from config import SCREEN_H, SCREEN_W
from .sprites import radial_gradient


class Atmosphere:
    def __init__(self, seed: int = 7):
        rng = random.Random(seed)
        self.fog = self._make_fog_texture(rng)
        self.fog_x = 0.0
        self.motes = [
            [rng.uniform(0, SCREEN_W), rng.uniform(0, SCREEN_H), rng.uniform(4, 14), rng.uniform(0, 6.28)]
            for _ in range(40)
        ]
        self.vignette = self._make_vignette()
        self.t = 0.0

    @staticmethod
    def _make_fog_texture(rng: random.Random) -> pygame.Surface:
        """One screen-sized fog texture that wraps horizontally, so drifting
        fog costs a single blit per frame instead of one per blob."""
        tex = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        for _ in range(14):
            radius = rng.randint(150, 260)
            blob = radial_gradient(radius, (120, 130, 150), rng.randint(16, 30), falloff=1.6)
            x, y = rng.uniform(0, SCREEN_W), rng.uniform(-radius, SCREEN_H - radius)
            for dx in (-SCREEN_W, 0, SCREEN_W):          # wrap around the seam
                tex.blit(blob, (x + dx - radius, y), special_flags=pygame.BLEND_RGBA_MAX)
        return tex.convert_alpha() if pygame.display.get_surface() is not None else tex

    @staticmethod
    def _make_vignette() -> pygame.Surface:
        """Smooth elliptical darkening toward the screen edges."""
        yy, xx = np.mgrid[0:SCREEN_H, 0:SCREEN_W]
        d = np.hypot((xx - SCREEN_W / 2) / (SCREEN_W / 2), (yy - SCREEN_H / 2) / (SCREEN_H / 2))
        alpha = np.clip((d - 0.75) / 0.70, 0.0, 1.0) ** 1.8 * 170
        rgba = np.zeros((SCREEN_H, SCREEN_W, 4), dtype=np.uint8)
        rgba[..., 3] = alpha.astype(np.uint8)
        surf = pygame.image.frombuffer(rgba.tobytes(), (SCREEN_W, SCREEN_H), "RGBA").copy()
        # Match the display's pixel format, or every blit pays a conversion.
        return surf.convert_alpha() if pygame.display.get_surface() is not None else surf

    def update(self, dt: float) -> None:
        self.t += dt
        self.fog_x = (self.fog_x + 14 * dt) % SCREEN_W
        for m in self.motes:
            m[1] -= m[2] * dt
            m[0] += math.sin(self.t * 0.7 + m[3]) * 6 * dt
            if m[1] < -10:
                m[1] = SCREEN_H + 10

    def draw_fog(self, surface: pygame.Surface, clip: pygame.Rect | None = None) -> None:
        area = pygame.Rect(clip) if clip else surface.get_rect()
        x = int(self.fog_x)
        y = int(math.sin(self.t * 0.25) * 12)
        prev = surface.get_clip()
        surface.set_clip(area)
        # Two blits cover the wrap seam; clipping keeps the cost to `area`.
        surface.blit(self.fog, (x - SCREEN_W, y))
        surface.blit(self.fog, (x, y))
        surface.set_clip(prev)

    def draw_motes(self, surface: pygame.Surface) -> None:
        for x, y, _, ph in self.motes:
            k = 0.45 + 0.35 * math.sin(self.t * 2 + ph)
            surface.fill((int(150 * k), int(240 * k), int(230 * k)), (int(x), int(y), 3, 3),
                         special_flags=pygame.BLEND_RGB_ADD)

    def draw_vignette(self, surface: pygame.Surface) -> None:
        surface.blit(self.vignette, (0, 0))
