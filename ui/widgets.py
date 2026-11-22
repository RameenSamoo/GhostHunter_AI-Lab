"""Reusable UI pieces: text helpers, panels and buttons."""

from __future__ import annotations

from typing import Callable

import pygame

from . import theme

_PANEL_CACHE: dict[tuple[tuple[int, int], int], pygame.Surface] = {}


def draw_text(surface: pygame.Surface, text: str, fnt: pygame.font.Font, colour, pos,
              anchor: str = "topleft", alpha: int = 255) -> pygame.Rect:
    img = fnt.render(text, True, colour)
    if alpha < 255:
        img.set_alpha(alpha)
    rect = img.get_rect(**{anchor: pos})
    surface.blit(img, rect)
    return rect


def draw_glow_text(surface: pygame.Surface, text: str, fnt: pygame.font.Font, colour, glow,
                   pos, anchor: str = "center", radius: int = 3, glow_alpha: int = 60) -> pygame.Rect:
    """Text with a soft coloured halo (several offset translucent copies)."""
    halo = fnt.render(text, True, glow)
    halo.set_alpha(glow_alpha)
    base_rect = halo.get_rect(**{anchor: pos})
    for dx in range(-radius, radius + 1, max(1, radius // 2)):
        for dy in range(-radius, radius + 1, max(1, radius // 2)):
            if dx or dy:
                surface.blit(halo, base_rect.move(dx, dy))
    return draw_text(surface, text, fnt, colour, pos, anchor)


def draw_panel(surface: pygame.Surface, rect: pygame.Rect, alpha: int = 235,
               edge=theme.PANEL_EDGE, title: str | None = None, ornate: bool = False) -> None:
    """Dark stone panel with a bevelled border and optional gothic corner brackets."""
    rect = pygame.Rect(rect)
    if alpha >= 255 and not ornate:
        surface.fill(theme.PANEL, rect)
    else:
        key = (rect.size, alpha, ornate)
        bg = _PANEL_CACHE.get(key)
        if bg is None:
            bg = pygame.Surface(rect.size, pygame.SRCALPHA)
            if ornate:
                # Subtle top-to-bottom slate depth gradient
                for row in range(rect.height):
                    k = row / max(1, rect.height - 1)
                    r = int(28 - 13 * k)
                    g = int(32 - 14 * k)
                    b = int(44 - 18 * k)
                    pygame.draw.line(bg, (r, g, b, alpha), (0, row), (rect.width - 1, row))
            else:
                bg.fill((*theme.PANEL, alpha))
            _PANEL_CACHE[key] = bg
        surface.blit(bg, rect)
    pygame.draw.rect(surface, edge, rect, 2, border_radius=4)
    inner = rect.inflate(-8, -8)
    pygame.draw.rect(surface, (36, 40, 52), inner, 1, border_radius=3)
    if ornate:
        b_col = theme.BRASS if edge == theme.PANEL_EDGE else edge
        pygame.draw.rect(surface, (66, 56, 44) if edge == theme.PANEL_EDGE else edge, inner, 1, border_radius=3)
        arm = min(24, rect.width // 5, rect.height // 5)
        for (x, y), (dx, dy) in (
            (rect.topleft, (1, 1)),
            ((rect.right - 1, rect.top), (-1, 1)),
            ((rect.left, rect.bottom - 1), (1, -1)),
            ((rect.right - 1, rect.bottom - 1), (-1, -1)),
        ):
            pygame.draw.line(surface, b_col, (x, y), (x + dx * arm, y), 3)
            pygame.draw.line(surface, b_col, (x, y), (x, y + dy * arm), 3)
            pygame.draw.circle(surface, b_col, (x + dx * 7, y + dy * 7), 2)
        if title is None and rect.width >= 120:
            mx, my = rect.centerx, rect.top
            pts = [(mx, my - 6), (mx + 9, my), (mx, my + 6), (mx - 9, my)]
            pygame.draw.polygon(surface, (28, 32, 44), pts)
            pygame.draw.polygon(surface, b_col, pts, 2)
    else:
        for x, y in (rect.topleft, rect.topright, rect.bottomleft, rect.bottomright):
            cx = x + (5 if x == rect.left else -6)
            cy = y + (5 if y == rect.top else -6)
            pygame.draw.circle(surface, theme.PANEL_EDGE_HI, (cx, cy), 2)
    if title:
        draw_text(surface, title.upper(), theme.font("sans", 13, True), theme.TEXT_DIM,
                  (rect.x + 12, rect.y + 8))


def draw_ornate_divider(surface: pygame.Surface, x1: int, x2: int, y: int,
                        line_col=theme.PANEL_EDGE, crest_col=theme.BRASS) -> None:
    """Horizontal gothic hairline with a small centered diamond crest."""
    mid = (x1 + x2) // 2
    pygame.draw.line(surface, line_col, (x1, y), (mid - 10, y), 1)
    pygame.draw.line(surface, line_col, (mid + 10, y), (x2, y), 1)
    pts = [(mid, y - 4), (mid + 5, y), (mid, y + 4), (mid - 5, y)]
    pygame.draw.polygon(surface, crest_col, pts)


def draw_keycap(surface: pygame.Surface, label: str, pos: tuple[int, int],
                accent=theme.AMBER, min_w: int = 34, anchor: str = "topleft") -> pygame.Rect:
    """Tactile dark keycap badge with subtle bevel."""
    fnt = theme.font("mono", 14, True)
    txt = fnt.render(label, True, accent)
    w = max(min_w, txt.get_width() + 16)
    h = 28
    rect = pygame.Rect(0, 0, w, h)
    setattr(rect, anchor, pos)
    pygame.draw.rect(surface, (28, 31, 42), rect, border_radius=5)
    pygame.draw.rect(surface, (14, 16, 22), rect.move(0, 2), border_radius=5)
    pygame.draw.rect(surface, (28, 31, 42), rect, border_radius=5)
    pygame.draw.rect(surface, theme.PANEL_EDGE_HI, rect, 1, border_radius=5)
    surface.blit(txt, txt.get_rect(center=rect.center))
    return rect


def draw_threat_skulls(surface: pygame.Surface, cx: int, y: int, level: int,
                       total: int = 4, accent=theme.AMBER) -> None:
    """Draws 1..total minimal gothic skull icons to indicate threat level."""
    gap = 24
    x0 = cx - ((total - 1) * gap) // 2
    for i in range(total):
        sx = x0 + i * gap
        lit = i < level
        col = accent if lit else (42, 46, 58)
        eye = (12, 14, 20) if lit else (22, 24, 32)
        pygame.draw.circle(surface, col, (sx, y), 6)
        pygame.draw.rect(surface, col, (sx - 4, y + 3, 8, 5), border_radius=2)
        pygame.draw.circle(surface, eye, (sx - 2, y - 1), 1)
        pygame.draw.circle(surface, eye, (sx + 2, y - 1), 1)


def draw_mini_maze(surface: pygame.Surface, rect: pygame.Rect, grid_size: int, accent) -> None:
    """Draws a clean miniature maze preview icon scaled to grid_size."""
    rect = pygame.Rect(rect)
    pygame.draw.rect(surface, (12, 14, 20), rect, border_radius=4)
    pygame.draw.rect(surface, theme.PANEL_EDGE, rect, 1, border_radius=4)
    cells = 5 if grid_size <= 8 else (7 if grid_size <= 12 else (9 if grid_size <= 18 else 11))
    pad = 5
    step = (rect.width - 2 * pad) / cells
    for r in range(cells):
        for c in range(cells):
            # Deterministic maze-like pattern
            is_wall = ((r * 7 + c * 13 + grid_size) % 5 == 0) and not (r == 0 and c == 0)
            cr = pygame.Rect(int(rect.x + pad + c * step), int(rect.y + pad + r * step),
                             max(2, int(step) - 1), max(2, int(step) - 1))
            if is_wall:
                pygame.draw.rect(surface, accent, cr)
            else:
                pygame.draw.rect(surface, (26, 30, 40), cr)


def draw_bar(surface: pygame.Surface, rect: pygame.Rect, frac: float, colour,
             back=(28, 31, 42)) -> None:
    rect = pygame.Rect(rect)
    pygame.draw.rect(surface, back, rect, border_radius=3)
    if frac > 0:
        fill = rect.copy()
        fill.width = max(2, int(rect.width * min(1.0, frac)))
        pygame.draw.rect(surface, colour, fill, border_radius=3)
    pygame.draw.rect(surface, theme.PANEL_EDGE, rect, 1, border_radius=3)


class Button:
    def __init__(self, rect, label: str, on_click: Callable[[], None],
                 font_size: int = 26, accent=theme.CYAN, enabled: bool = True):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.on_click = on_click
        self.font_size = font_size
        self.accent = accent
        self.enabled = enabled
        self.focused = False   # keyboard focus

    def hovered(self) -> bool:
        return self.enabled and self.rect.collidepoint(pygame.mouse.get_pos())

    def handle_event(self, event: pygame.event.Event) -> bool:
        if (self.enabled and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                and self.rect.collidepoint(event.pos)):
            self.on_click()
            return True
        return False

    def draw(self, surface: pygame.Surface, t: float = 0.0) -> None:
        active = self.enabled and (self.hovered() or self.focused)
        base = (24, 27, 38) if not active else (34, 40, 54)
        pygame.draw.rect(surface, base, self.rect, border_radius=5)
        edge = self.accent if active else (theme.BRASS if self.enabled else (36, 39, 50))
        pygame.draw.rect(surface, edge, self.rect, 2, border_radius=5)
        if self.enabled:
            inner = self.rect.inflate(-6, -6)
            pygame.draw.rect(surface, (42, 46, 60) if not active else self.accent, inner, 1, border_radius=3)
            for (x, y), (dx, dy) in ((self.rect.topleft, (1, 1)), ((self.rect.right - 1, self.rect.top), (-1, 1)),
                                      ((self.rect.left, self.rect.bottom - 1), (1, -1)), ((self.rect.right - 1, self.rect.bottom - 1), (-1, -1))):
                pygame.draw.circle(surface, edge, (x + dx * 5, y + dy * 5), 2)
        if active:
            glow = pygame.Surface(self.rect.inflate(16, 16).size, pygame.SRCALPHA)
            pygame.draw.rect(glow, (*self.accent, 40), glow.get_rect(), 6, border_radius=10)
            surface.blit(glow, self.rect.inflate(16, 16))
        colour = theme.TEXT if self.enabled else theme.TEXT_FAINT
        if active:
            colour = self.accent
        draw_text(surface, self.label, theme.font("serif", self.font_size, True), colour,
                  self.rect.center, "center")


class ButtonGroup:
    """Buttons navigable with mouse, arrow keys and Enter."""

    def __init__(self, buttons: list[Button], horizontal: bool = False):
        self.buttons = buttons
        self.horizontal = horizontal
        self.index = -1

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            for i, b in enumerate(self.buttons):
                if b.enabled and b.rect.collidepoint(event.pos):
                    self._focus(i)
        if event.type == pygame.KEYDOWN:
            prev_keys = (pygame.K_LEFT,) if self.horizontal else (pygame.K_UP,)
            next_keys = (pygame.K_RIGHT,) if self.horizontal else (pygame.K_DOWN,)
            if event.key in prev_keys + next_keys:
                step = -1 if event.key in prev_keys else 1
                self._move(step)
                return True
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and 0 <= self.index < len(self.buttons):
                b = self.buttons[self.index]
                if b.enabled:
                    b.on_click()
                    return True
        return any(b.handle_event(event) for b in self.buttons)

    def _move(self, step: int) -> None:
        n = len(self.buttons)
        i = self.index if self.index >= 0 else (-1 if step > 0 else 0)
        for _ in range(n):
            i = (i + step) % n
            if self.buttons[i].enabled:
                self._focus(i)
                return

    def _focus(self, i: int) -> None:
        self.index = i
        for j, b in enumerate(self.buttons):
            b.focused = j == i

    def draw(self, surface: pygame.Surface, t: float = 0.0) -> None:
        for b in self.buttons:
            b.draw(surface, t)
