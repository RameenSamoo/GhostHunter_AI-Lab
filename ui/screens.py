"""Menu, difficulty selection, instructions and high-score screens."""

from __future__ import annotations

import math

import pygame

from config import (AI_NAME, DIFFICULTIES, FLICKER_DURATION, HINT_COOLDOWN,
                    HINT_DURATION, HINT_PENALTY, MODE_LABELS, MODE_SIMULTANEOUS,
                    MODE_SOLO, MODE_TURNS, MODES, MOVE_REPEAT_RATE,
                    RADAR_COOLDOWN, RADAR_DURATION, RADAR_PENALTY, RADAR_USES,
                    SCREEN_H, SCREEN_W, SENSOR_SIGMA)
from . import theme
from .app import Screen
from .sprites import radial_gradient
from .widgets import (Button, ButtonGroup, draw_glow_text, draw_keycap,
                      draw_mini_maze, draw_ornate_divider, draw_panel, draw_text,
                      draw_threat_skulls)

TIER_COLOURS = {
    "beginner": theme.GREEN,
    "intermediate": theme.CYAN,
    "professional": theme.AMBER,
    "expert": theme.RED,
}


def back_button(on_click) -> Button:
    return Button((40, SCREEN_H - 84, 180, 50), "Back", on_click, font_size=22)


# ==========================================================================
# Home screen
# ==========================================================================
class MenuScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        cx = SCREEN_W // 2
        self.buttons = ButtonGroup([
            Button((cx - 155, 298, 310, 54), "Play", self._play, 26),
            Button((cx - 155, 366, 310, 54), "Hunter Profile", lambda: app.go("players"), 26),
            Button((cx - 155, 434, 310, 54), "Instructions", lambda: app.go("guide"), 26),
            Button((cx - 155, 502, 310, 54), "High Scores", lambda: app.go("scores"), 26),
        ])
        self.aura = radial_gradient(160, (60, 220, 210), 140, 1.4)
        self.lantern = radial_gradient(180, (255, 170, 60), 145, 1.4)
        self.t = 0.0

    def _play(self):
        """Ask new/current first, unless a hunter was already chosen during this launch."""
        if self.app.profile_chosen:
            self.app.go("mode")
        else:
            self.app.go("players", next_screen="mode")

    def handle_event(self, event):
        self.buttons.handle_event(event)

    def update(self, dt):
        self.t += dt

    def draw(self, surface):
        self.app.draw_menu_backdrop(surface)
        t = self.t
        cx = SCREEN_W // 2

        # Corner gothic torch sconces with flickering ember glow
        flick = 0.75 + 0.25 * math.sin(t * 9.0) * math.sin(t * 2.3)
        for sx in (68, SCREEN_W - 68):
            sy = 62
            pygame.draw.line(surface, theme.BRASS, (sx, sy + 6), (sx, sy + 28), 3)
            pygame.draw.polygon(surface, (45, 40, 36), [(sx - 10, sy + 6), (sx + 10, sy + 6), (sx + 5, sy + 16), (sx - 5, sy + 16)])
            pygame.draw.circle(surface, theme.AMBER, (sx, sy), int(5 + 2 * flick))
            pygame.draw.circle(surface, (255, 230, 160), (sx, sy + 1), 2)

        # Right side: floating ghost + expanding spectral radar pulse rings + Sir Nadeem silhouette
        gy = 250 + math.sin(t * 1.4) * 14
        gx, gcy = 1045, int(gy + 58)
        surface.blit(self.aura, (gx - 160, gcy - 160), special_flags=pygame.BLEND_RGB_ADD)
        for p_idx in range(2):
            phase = (t * 0.45 + p_idx * 0.5) % 1.0
            rad = int(42 + phase * 82)
            ring = pygame.Surface((rad * 2 + 4, rad * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(ring, (*theme.CYAN, int(75 * (1.0 - phase))), (rad + 2, rad + 2), rad, 1)
            surface.blit(ring, (gx - rad - 2, gcy - rad - 2))
        ghost = self.app.atlas.get("ghost", 116).copy()
        ghost.set_alpha(int(170 + 60 * flick))
        surface.blit(ghost, (gx - 58, gy))

        # Sir Nadeem (AI Hunter) on a violet-rimmed pedestal below the ghost
        ax, ay = 1045, 455
        ai_ped = pygame.Rect(ax - 52, ay + 92, 104, 16)
        pygame.draw.ellipse(surface, (18, 20, 28), ai_ped)
        pygame.draw.ellipse(surface, theme.VIOLET_DIM, ai_ped, 1)
        surface.blit(self.app.atlas.get("ai_hunter", 96), (ax - 48, ay))

        # Left side: Human Hunter on a stone/brass pedestal with warm lantern glow
        hx, hy = 235, 375
        surface.blit(self.lantern, (hx - 180, hy + 64 - 180), special_flags=pygame.BLEND_RGB_ADD)
        pedestal = pygame.Rect(hx - 62, hy + 122, 124, 18)
        pygame.draw.ellipse(surface, (18, 20, 28), pedestal)
        pygame.draw.ellipse(surface, theme.BRASS, pedestal, 1)
        surface.blit(self.app.atlas.get("hunter", 128), (hx - 64, hy))

        # Engraved Title (no "2D") + ornate divider + tagline
        title_alpha = 255 if (int(t * 7) % 29) else 160
        title_font = theme.font("title", 74, True)
        draw_glow_text(surface, "GHOST HUNTER", title_font, (228, 245, 245), theme.CYAN,
                       (cx, 112), radius=4, glow_alpha=42 if title_alpha == 255 else 18)
        draw_ornate_divider(surface, cx - 260, cx + 260, 168, theme.BRASS, theme.AMBER)
        draw_text(surface, "Track the unseen.  Trust the heat.", theme.font("serif", 19), theme.TEXT_DIM,
                  (cx, 196), "center")

        # Ornate gothic panel framing the menu buttons
        menu_panel = pygame.Rect(cx - 190, 270, 380, 316)
        draw_panel(surface, menu_panel, 225, theme.PANEL_EDGE, ornate=True)
        self.buttons.draw(surface, t)

        # Active Hunter Pill
        active_label = f"Hunter: {self.app.active_player_name or 'Unassigned'}  [{self.app.active_player_id}]"
        pill = pygame.Rect(cx - 165, SCREEN_H - 96, 330, 34)
        pygame.draw.rect(surface, (16, 18, 26), pill, border_radius=17)
        pygame.draw.rect(surface, theme.BRASS, pill, 1, border_radius=17)
        draw_text(surface, active_label, theme.font("mono", 14, True), theme.CYAN, pill.center, "center")
        draw_text(surface, "Close the window to exit", theme.font("sans", 13), theme.TEXT_FAINT,
                  (cx, SCREEN_H - 36), "center")


# ==========================================================================
# Card-picker base (mode and first-player screens)
# ==========================================================================
class CardPickerScreen(Screen):
    """A row of large cards chosen by mouse, number keys, or arrows + Enter."""

    TITLE = ""
    SUBTITLE = ""
    CARD_W, CARD_H, GAP, TOP = 360, 330, 30, 200
    back_to = "menu"

    def __init__(self, app):
        super().__init__(app)
        n = len(self.cards_spec())
        total = n * self.CARD_W + (n - 1) * self.GAP
        x0 = (SCREEN_W - total) // 2
        self.cards = [pygame.Rect(x0 + i * (self.CARD_W + self.GAP), self.TOP, self.CARD_W, self.CARD_H)
                      for i in range(n)]
        self.focus = -1
        self.hover_t = [0.0] * n
        self.t = 0.0
        self.back = back_button(lambda: self.app.go(self.back_to))

    def cards_spec(self) -> list[tuple[str, tuple, list[str]]]:
        """(title, accent colour, description lines) per card."""
        raise NotImplementedError

    def choose(self, i: int) -> None:
        raise NotImplementedError

    def enter(self, **_):
        self.focus = -1
        self.hover_t = [0.0] * len(self.cards)

    def update(self, dt):
        self.t += dt
        for i in range(len(self.cards)):
            target = 1.0 if i == self.focus else 0.0
            self.hover_t[i] += (target - self.hover_t[i]) * min(1.0, dt * 14)

    def handle_event(self, event):
        n = len(self.cards)
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.app.go(self.back_to)
            elif pygame.K_1 <= event.key < pygame.K_1 + n:
                self.choose(event.key - pygame.K_1)
            elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                step = -1 if event.key == pygame.K_LEFT else 1
                self.focus = (self.focus + step) % n if self.focus >= 0 else (0 if step > 0 else n - 1)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and self.focus >= 0:
                self.choose(self.focus)
        elif event.type == pygame.MOUSEMOTION:
            for i, r in enumerate(self.cards):
                if r.collidepoint(event.pos):
                    self.focus = i
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, r in enumerate(self.cards):
                if r.collidepoint(event.pos):
                    self.choose(i)
                    return
        self.back.handle_event(event)

    def draw(self, surface):
        self.app.draw_menu_backdrop(surface)
        draw_glow_text(surface, self.TITLE, theme.font("title", 60, True), (225, 245, 245),
                       theme.CYAN, (SCREEN_W // 2, 95), radius=3, glow_alpha=45)
        draw_text(surface, self.SUBTITLE, theme.font("sans", 16), theme.TEXT_DIM,
                  (SCREEN_W // 2, 148), "center")
        for i, (rect, (title, accent, lines)) in enumerate(zip(self.cards, self.cards_spec())):
            ht = self.hover_t[i]
            focused = i == self.focus
            card = rect.move(0, int(-8 * ht))
            edge = accent if focused else theme.PANEL_EDGE
            draw_panel(surface, card, 240, edge, ornate=True)
            if ht > 0.02:
                glow = pygame.Surface(card.inflate(16, 16).size, pygame.SRCALPHA)
                pygame.draw.rect(glow, (*accent, int(26 * ht)), glow.get_rect(), 6, border_radius=10)
                surface.blit(glow, card.inflate(16, 16))
            draw_text(surface, f"0{i + 1}", theme.font("mono", 14, True), theme.TEXT_FAINT, (card.x + 18, card.y + 16))
            title_lines = title.split("\n")
            for j, tl in enumerate(title_lines):
                draw_text(surface, tl, theme.font("serif", 30, True), accent,
                          (card.centerx, card.y + 54 + j * 36), "center")
            ty = card.y + 54 + len(title_lines) * 36 + 8
            draw_ornate_divider(surface, card.x + 26, card.right - 26, ty, theme.PANEL_EDGE, accent)
            for j, line in enumerate(lines):
                draw_text(surface, line, theme.font("sans", 17), theme.TEXT,
                          (card.centerx, ty + 30 + j * 28), "center")
            self.draw_card_art(surface, i, card)
        self.back.draw(surface)

    def draw_card_art(self, surface, i, card) -> None:
        """Small sprites at the bottom of each card."""


# ==========================================================================
# Mode selection
# ==========================================================================
class ModeScreen(CardPickerScreen):
    TITLE = "CHOOSE YOUR MODE"
    SUBTITLE = "Click a card or press 1 - 3"
    back_to = "menu"

    def cards_spec(self):
        return [
            ("Solo", theme.GREEN, ["Hunt the ghost alone.", "The classic game."]),
            ("VS AI\nSimultaneous", theme.VIOLET,
             [f"You and {AI_NAME} hunt", "the same ghost at the", "same time, side by side."]),
            ("VS AI\nTurn-based", theme.AMBER,
             ["Same maze, same start.", "You take turns; the second", "player sees the target."]),
        ]

    def choose(self, i: int) -> None:
        mode = MODES[i]
        self.app.game_mode = mode
        if mode == MODE_TURNS:
            self.app.go("first")
        else:
            self.app.go("difficulty", return_to="mode")

    def draw_card_art(self, surface, i, card):
        atlas = self.app.atlas
        y = card.bottom - 76
        if i == 0:
            surface.blit(atlas.get("hunter", 56), (card.centerx - 28, y))
        else:
            surface.blit(atlas.get("hunter", 56), (card.centerx - 62, y))
            surface.blit(atlas.get("ai_hunter", 56), (card.centerx + 6, y))


class FirstScreen(CardPickerScreen):
    TITLE = "WHO GOES FIRST?"
    SUBTITLE = "The second player sees the score to beat. Press 1 or 2"
    CARD_W, CARD_H = 420, 300
    back_to = "mode"

    def cards_spec(self):
        return [
            ("You go first", theme.AMBER, [f"Set the target score", f"for {AI_NAME} to beat."]),
            (f"{AI_NAME}\ngoes first", theme.VIOLET, ["He sets the target.", "You try to beat it."]),
        ]

    def choose(self, i: int) -> None:
        self.app.ai_first = i == 1
        self.app.go("difficulty", return_to="first")

    def draw_card_art(self, surface, i, card):
        sprite = "hunter" if i == 0 else "ai_hunter"
        surface.blit(self.app.atlas.get(sprite, 64), (card.centerx - 32, card.bottom - 84))


# ==========================================================================
# Difficulty selection
# ==========================================================================
class DifficultyScreen(Screen):
    CARD_W, CARD_H, GAP = 272, 392, 26

    def __init__(self, app):
        super().__init__(app)
        self.return_to = "menu"
        total = 4 * self.CARD_W + 3 * self.GAP
        x0 = (SCREEN_W - total) // 2
        self.cards = [pygame.Rect(x0 + i * (self.CARD_W + self.GAP), 182, self.CARD_W, self.CARD_H)
                      for i in range(4)]
        self.focus = -1
        self.hover_t = [0.0] * 4
        self.t = 0.0
        self.back = back_button(self._back)

    def enter(self, return_to: str = "menu", **_):
        self.return_to = return_to
        self.focus = -1
        self.hover_t = [0.0] * 4

    def update(self, dt):
        self.t += dt
        for i in range(4):
            target = 1.0 if i == self.focus else 0.0
            self.hover_t[i] += (target - self.hover_t[i]) * min(1.0, dt * 14)

    def _back(self):
        self.app.go(self.return_to)

    def _choose(self, i: int):
        self.app.go("game", difficulty=DIFFICULTIES[i])

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._back()
            elif pygame.K_1 <= event.key <= pygame.K_4:
                self._choose(event.key - pygame.K_1)
            elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                step = -1 if event.key == pygame.K_LEFT else 1
                self.focus = (self.focus + step) % 4 if self.focus >= 0 else (0 if step > 0 else 3)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and self.focus >= 0:
                self._choose(self.focus)
        elif event.type == pygame.MOUSEMOTION:
            for i, r in enumerate(self.cards):
                if r.collidepoint(event.pos):
                    self.focus = i
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, r in enumerate(self.cards):
                if r.collidepoint(event.pos):
                    self._choose(i)
                    return
        self.back.handle_event(event)

    def draw(self, surface):
        self.app.draw_menu_backdrop(surface)
        draw_glow_text(surface, "CHOOSE YOUR HUNT", theme.font("title", 60, True), (225, 245, 245),
                       theme.CYAN, (SCREEN_W // 2, 95), radius=3, glow_alpha=45)
        mode = self.app.game_mode
        label = MODE_LABELS[mode]
        if mode == MODE_TURNS:
            label += f"  ·  {AI_NAME + ' goes' if self.app.ai_first else 'You go'} first"
        draw_text(surface, f"{label}   ·   click a card or press 1 - 4", theme.font("sans", 16),
                  theme.TEXT_DIM, (SCREEN_W // 2, 148), "center")

        for i, (rect, d) in enumerate(zip(self.cards, DIFFICULTIES)):
            accent = TIER_COLOURS[d.key]
            ht = self.hover_t[i]
            focused = i == self.focus
            card = rect.move(0, int(-8 * ht))
            draw_panel(surface, card, 240, accent if focused else theme.PANEL_EDGE, ornate=True)
            if ht > 0.02:
                glow = pygame.Surface(card.inflate(16, 16).size, pygame.SRCALPHA)
                pygame.draw.rect(glow, (*accent, int(26 * ht)), glow.get_rect(), 6, border_radius=10)
                surface.blit(glow, card.inflate(16, 16))
            cx = card.centerx
            draw_text(surface, f"0{i + 1}", theme.font("mono", 15, True), theme.TEXT_FAINT, (card.x + 18, card.y + 16))
            draw_text(surface, d.name.upper(), theme.font("title", 24, True), accent, (cx, card.y + 46), "center")
            draw_threat_skulls(surface, cx, card.y + 80, i + 1, 4, accent)

            # Prominent grid size display (no irrelevant icon circles)
            draw_text(surface, f"{d.size} × {d.size}", theme.font("title", 48, True), theme.TEXT,
                      (cx, card.y + 136), "center")
            draw_text(surface, "MAZE GRID", theme.font("mono", 13, True), theme.TEXT_DIM,
                      (cx, card.y + 174), "center")

            draw_ornate_divider(surface, card.x + 24, card.right - 24, card.y + 198, theme.PANEL_EDGE, accent)

            rows = [
                ("Ghost tick", f"{d.ghost_interval:.1f}s", 1.1 - d.ghost_interval / 1.2),
                ("Wall density", f"{int(d.wall_density * 100)}%", d.wall_density / 0.25),
                ("AI speed", f"{d.ai_speed:.2f} c/s", d.ai_speed / 7.0),
            ]
            bar_w = card.width - 48
            for j, (label, value, frac) in enumerate(rows):
                y = card.y + 216 + j * 38
                draw_text(surface, label, theme.font("sans", 17), theme.TEXT_DIM, (card.x + 24, y))
                draw_text(surface, value, theme.font("mono", 17, True), theme.TEXT, (card.right - 24, y), "topright")
                bar_r = pygame.Rect(card.x + 24, y + 25, bar_w, 5)
                pygame.draw.rect(surface, (28, 32, 44), bar_r, border_radius=2)
                fill_w = max(4, int(bar_w * min(1.0, max(0.08, frac))))
                pygame.draw.rect(surface, accent, (bar_r.x, bar_r.y, fill_w, 5), border_radius=2)

            # Bottom score multiplier pill
            pill = pygame.Rect(cx - 90, card.bottom - 52, 180, 34)
            pygame.draw.rect(surface, (16, 18, 26), pill, border_radius=17)
            pygame.draw.rect(surface, accent if focused else theme.PANEL_EDGE, pill, 1, border_radius=17)
            draw_text(surface, f"× {d.multiplier:.1f}  SCORE", theme.font("mono", 16, True), accent,
                      pill.center, "center")

        self.back.draw(surface)
        hint = "Esc  Back" if self.return_to == "menu" else "Esc  Return to your game"
        draw_text(surface, hint, theme.font("sans", 14), theme.TEXT_FAINT, (240, SCREEN_H - 66))


# ==========================================================================
# Instructions / Field guide
# ==========================================================================
class GuideScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.back = back_button(lambda: app.go("menu"))
        self.t = 0.0

    def update(self, dt):
        self.t += dt

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.app.go("menu")
        self.back.handle_event(event)

    def draw(self, surface):
        self.app.draw_menu_backdrop(surface)
        draw_glow_text(surface, "FIELD GUIDE", theme.font("title", 58, True), (225, 245, 245),
                       theme.CYAN, (SCREEN_W // 2, 58), radius=3, glow_alpha=35)

        sections = [
            ("Controls", theme.AMBER, [
                ("ARROWS", f"Move one cell. Hold to run (~{MOVE_REPEAT_RATE:.0f} cells/s)."),
                ("SPACE", "Spirit Radar: reveal the ghost on the minimap."),
                ("H", "A* hint: show the shortest path to the hottest cell."),
                ("P", "Pause. Everything freezes until you resume."),
                ("R", "New maze and ghost on the same difficulty."),
                ("", "Walls block you and cost no moves."),
            ]),
            ("The Ghost", theme.CYAN, [
                ("", "It is invisible and moves one cell every tick,"),
                ("", "at random, whether you move or not."),
                ("", f"Now and then it flickers into view for {FLICKER_DURATION} s."),
                ("", "You catch it by ending up on its cell."),
                ("", "Passing through each other does not count."),
            ]),
            ("Heat Signature", theme.RED, [
                ("", "Your PKE meter measures walking distance to the"),
                ("", f"ghost through corridors, with noise (σ = {SENSOR_SIGMA})."),
                ("", "Every reading updates a Bayesian (HMM) belief:"),
                ("", "warmer floor = more likely the ghost is there."),
                ("", "The heartbeat quickens as readings drop."),
            ]),
            ("Tools & Scoring", theme.GREEN, [
                ("Radar", f"{RADAR_USES} uses, {RADAR_DURATION:.0f} s, {RADAR_COOLDOWN:.0f} s cooldown, −{RADAR_PENALTY}"),
                ("Hint", f"Unlimited, {HINT_DURATION:.0f} s, {HINT_COOLDOWN:.0f} s cooldown, −{HINT_PENALTY}"),
                ("Base", "max(0, 10000 − 50 × seconds − 20 × moves)"),
                ("Scaled", "Base × difficulty multiplier"),
                ("Final", f"Scaled − {RADAR_PENALTY} × radars − {HINT_PENALTY} × hints"),
                ("", "Top 5 per difficulty enter the hall of hunters."),
            ]),
        ]
        w, h = 575, 266
        positions = [(50, 106), (655, 106), (50, 386), (655, 386)]
        for idx, ((title, accent, lines), (x, y)) in enumerate(zip(sections, positions)):
            rect = pygame.Rect(x, y, w, h)
            draw_panel(surface, rect, 235, ornate=True)
            draw_text(surface, title, theme.font("serif", 25, True), accent, (x + 24, y + 16))
            draw_ornate_divider(surface, x + 22, x + w - 22, y + 50, theme.PANEL_EDGE, accent)

            for i, (key, text) in enumerate(lines):
                ly = y + 66 + i * 31
                if idx == 0 and key:
                    draw_keycap(surface, key, (x + 24, ly - 3), accent, min_w=72)
                    draw_text(surface, text, theme.font("sans", 16), theme.TEXT, (x + 114, ly + 1))
                elif idx == 3 and key in ("Radar", "Hint"):
                    icon_name = "radar_icon" if key == "Radar" else "hint_icon"
                    surface.blit(self.app.atlas.get(icon_name, 22), (x + 24, ly - 1))
                    draw_text(surface, key, theme.font("mono", 16, True), accent, (x + 54, ly))
                    draw_text(surface, text, theme.font("sans", 16), theme.TEXT, (x + 132, ly))
                elif key:
                    draw_text(surface, key, theme.font("mono", 16, True), accent, (x + 24, ly))
                    draw_text(surface, text, theme.font("sans", 16), theme.TEXT, (x + 132, ly))
                else:
                    draw_text(surface, text, theme.font("sans", 16), theme.TEXT, (x + 24, ly))

            # Extra visual elements per panel
            if idx == 1:
                ghost = self.app.atlas.get("ghost", 48).copy()
                ghost.set_alpha(int(155 + 65 * math.sin(self.t * 3.0)))
                gy = y + h - 68 + int(math.sin(self.t * 2.2) * 5)
                surface.blit(ghost, (x + w - 76, gy))
            elif idx == 2:
                bar = pygame.Rect(x + 24, y + h - 38, w - 48, 14)
                segs = 40
                sw = bar.width / segs
                for k in range(segs):
                    col = theme.heat_colour(k / (segs - 1))
                    pygame.draw.rect(surface, col, (int(bar.x + k * sw), bar.y, int(sw) + 1, bar.height))
                pygame.draw.rect(surface, theme.PANEL_EDGE_HI, bar, 1, border_radius=3)
                draw_text(surface, "COLD", theme.font("mono", 11, True), theme.TEXT_DIM, (bar.x, bar.y - 16))
                draw_text(surface, "HOT (NEAR GHOST)", theme.font("mono", 11, True), theme.RED, (bar.right, bar.y - 16), "topright")

        self.back.rect.topleft = (SCREEN_W - 220, SCREEN_H - 62)
        self.back.rect.size = (180, 44)
        self.back.draw(surface)


# ==========================================================================
# High scores
# ==========================================================================
MODE_TAB_LABELS = {MODE_SOLO: "Solo", MODE_SIMULTANEOUS: "VS · Simultaneous", MODE_TURNS: "VS · Turn-based"}


class ScoresScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.tab = 0
        self.mode_tab = 0
        tab_w, gap = 230, 16
        x0 = (SCREEN_W - (4 * tab_w + 3 * gap)) // 2
        self.tabs = [
            Button((x0 + i * (tab_w + gap), 172, tab_w, 44), f"{d.name}", lambda i=i: self._set_tab(i),
                   20, TIER_COLOURS[d.key])
            for i, d in enumerate(DIFFICULTIES)
        ]
        mode_w = 300
        mx0 = (SCREEN_W - (3 * mode_w + 2 * gap)) // 2
        mode_colours = (theme.GREEN, theme.VIOLET, theme.AMBER)
        self.mode_tabs = [
            Button((mx0 + i * (mode_w + gap), 116, mode_w, 44), MODE_TAB_LABELS[m],
                   lambda i=i: self._set_mode(i), 20, mode_colours[i])
            for i, m in enumerate(MODES)
        ]
        self.back = back_button(lambda: app.go("menu"))

    def enter(self, tab: str | None = None, mode: str | None = None, **_):
        if tab:
            self.tab = [d.key for d in DIFFICULTIES].index(tab)
        if mode:
            self.mode_tab = MODES.index(mode)

    def _set_tab(self, i):
        self.tab = i

    def _set_mode(self, i):
        self.mode_tab = i

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.app.go("menu")
            elif event.key == pygame.K_LEFT:
                self.tab = (self.tab - 1) % 4
            elif event.key == pygame.K_RIGHT:
                self.tab = (self.tab + 1) % 4
            elif event.key == pygame.K_UP:
                self.mode_tab = (self.mode_tab - 1) % len(MODES)
            elif event.key == pygame.K_DOWN:
                self.mode_tab = (self.mode_tab + 1) % len(MODES)
            elif pygame.K_1 <= event.key <= pygame.K_4:
                self.tab = event.key - pygame.K_1
        for b in self.tabs + self.mode_tabs:
            b.handle_event(event)
        self.back.handle_event(event)

    def draw(self, surface):
        self.app.draw_menu_backdrop(surface)
        draw_glow_text(surface, "HALL OF HUNTERS", theme.font("title", 56, True), (225, 245, 245),
                       theme.CYAN, (SCREEN_W // 2, 62), radius=3, glow_alpha=45)
        for group, active_idx in ((self.mode_tabs, self.mode_tab), (self.tabs, self.tab)):
            for i, b in enumerate(group):
                active = i == active_idx
                hovered = b.hovered()
                col = b.accent if active else (theme.TEXT if hovered else theme.TEXT_DIM)
                draw_text(surface, b.label, theme.font("serif", 19, active), col, b.rect.center, "center")
                if active:
                    y_line = b.rect.bottom - 4
                    pygame.draw.line(surface, b.accent, (b.rect.x + 18, y_line), (b.rect.right - 18, y_line), 2)
                    mx = b.rect.centerx
                    pygame.draw.polygon(surface, b.accent, [(mx, y_line - 4), (mx + 4, y_line), (mx, y_line + 4), (mx - 4, y_line)])
                elif hovered:
                    y_line = b.rect.bottom - 4
                    pygame.draw.line(surface, theme.PANEL_EDGE_HI, (b.rect.x + 28, y_line), (b.rect.right - 28, y_line), 1)

        mode = MODES[self.mode_tab]
        vs = mode != MODE_SOLO
        d = DIFFICULTIES[self.tab]
        accent = TIER_COLOURS[d.key]
        panel = pygame.Rect(140, 232, SCREEN_W - 280, 384)
        draw_panel(surface, panel, 240, accent, ornate=True)
        if vs:
            cols = [("RANK", 44, "topleft"), ("ID", 118, "topleft"), ("NAME", 210, "topleft"), ("SCORE", 490, "topright"),
                    (AI_NAME.upper(), 630, "topright"), ("TIME", 730, "topright"),
                    ("MOVES", 820, "topright"), ("DATE", 965, "topright")]
        else:
            cols = [("RANK", 44, "topleft"), ("ID", 130, "topleft"), ("NAME", 240, "topleft"), ("SCORE", 570, "topright"),
                    ("TIME", 710, "topright"), ("MOVES", 830, "topright"), ("DATE", 960, "topright")]
        hy = panel.y + 22
        for label, x, anchor in cols:
            colour = theme.VIOLET if label == AI_NAME.upper() else theme.TEXT_DIM
            draw_text(surface, label, theme.font("sans", 14, True), colour, (panel.x + x, hy), anchor)
        draw_ornate_divider(surface, panel.x + 28, panel.right - 28, hy + 28, theme.PANEL_EDGE, accent)

        entries = self.app.highscores.entries(d.key, mode)
        if not entries:
            draw_text(surface, "No hunts recorded yet.", theme.font("serif", 26), theme.TEXT_FAINT,
                      panel.center, "center")
        medal = [theme.GOLD, theme.SILVER, theme.BRONZE, theme.TEXT, theme.TEXT]
        for i, e in enumerate(entries):
            row_rect = pygame.Rect(panel.x + 26, hy + 42 + i * 58, panel.width - 52, 48)
            pid = getattr(e, 'player_id', 'P-1')
            is_active = bool(self.app.active_player_name and pid == self.app.active_player_id)
            row_bg = (26, 30, 42) if i % 2 == 0 else (21, 24, 34)
            pygame.draw.rect(surface, row_bg, row_rect, border_radius=5)
            pygame.draw.rect(surface, theme.CYAN_DIM if is_active else (34, 38, 50), row_rect, 1, border_radius=5)

            y = row_rect.centery - 12
            colour = medal[i]
            if i < 3:
                pygame.draw.circle(surface, colour, (panel.x + 48, row_rect.centery), 14, 1)
            values = {"RANK": f"#{i + 1}", "ID": pid, "NAME": e.name, "SCORE": f"{e.score:,}",
                      "TIME": f"{e.time:.1f}s", "MOVES": str(e.moves), "DATE": e.date,
                      AI_NAME.upper(): "—" if e.ai_score is None else f"{e.ai_score:,}"}
            fonts = {"RANK": ("serif", 22), "ID": ("mono", 18), "NAME": ("serif", 22 if vs else 24), "SCORE": ("mono", 24),
                     "TIME": ("mono", 20), "MOVES": ("mono", 20), "DATE": ("mono", 18),
                     AI_NAME.upper(): ("mono", 22)}
            for label, x, anchor in cols:
                f, size = fonts[label]
                if label in ("RANK", "SCORE"):
                    c = colour
                elif label == "ID":
                    c = theme.CYAN
                elif label == AI_NAME.upper():
                    c = theme.VIOLET
                else:
                    c = theme.TEXT
                pos_x = panel.x + (48 if label == "RANK" and i < 3 else x)
                anc = "center" if (label == "RANK" and i < 3) else anchor
                pos_y = row_rect.centery if anc == "center" else y
                draw_text(surface, values[label], theme.font(f, size, label != "DATE"), c, (pos_x, pos_y), anc)

        self.back.draw(surface)
        draw_text(surface, "← → difficulty   ·   ↑ ↓ mode", theme.font("sans", 14), theme.TEXT_FAINT,
                  (SCREEN_W // 2, SCREEN_H - 50), "center")


# ==========================================================================
# Player Selection / Verification Screen
# ==========================================================================
class PlayerSelectScreen(Screen):
    """Authenticate with existing Player ID + Name, or create a brand new player."""

    def __init__(self, app):
        super().__init__(app)
        self.back = back_button(lambda: self._on_back())
        cx = SCREEN_W // 2
        self.btn_new = Button((cx - 170, 240, 340, 58), "Create New Player", self._start_new, 24, theme.GREEN)
        self.btn_login = Button((cx - 170, 320, 340, 58), "Login Existing Player", self._start_login, 24, theme.CYAN)
        self.group = ButtonGroup([self.btn_new, self.btn_login])  # Up/Down + Enter, like the other screens
        self.next_screen: str | None = None   # where to go after a hunter is selected (None = main menu)

        self.mode = "menu"  # "menu", "new", "login"
        self.login_step = 0  # 0: enter ID, 1: enter Name
        self.input_id = ""
        self.input_name = ""
        self.new_name = ""
        self.error_msg = ""

    def _on_back(self):
        if self.mode != "menu":
            self.mode = "menu"
            self.error_msg = ""
            pygame.key.stop_text_input()
        else:
            self.app.go("menu")

    def _finish(self):
        """A hunter is now selected: remember that for this launch and move on."""
        self.app.profile_chosen = True
        pygame.key.stop_text_input()
        self.app.go(self.next_screen or "menu")

    def _start_new(self):
        self.mode = "new"
        self.new_name = ""
        self.error_msg = ""
        pygame.key.start_text_input()

    def _start_login(self):
        self.mode = "login"
        self.login_step = 0
        self.input_id = ""
        self.input_name = ""
        self.error_msg = ""
        pygame.key.start_text_input()

    def enter(self, next_screen: str | None = None, **_):
        self.next_screen = next_screen
        self.mode = "menu"
        self.error_msg = ""
        self.group._focus(-1)

    def handle_event(self, event):
        from core.scoring import sanitize_name
        from config import NAME_MAX_LEN

        if self.mode == "new":
            if event.type == pygame.TEXTINPUT:
                self.new_name = sanitize_name(self.new_name + event.text)[:NAME_MAX_LEN]
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_BACKSPACE:
                    self.new_name = self.new_name[:-1]
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    clean = self.new_name.strip()
                    if clean:
                        pid, rname = self.app.highscores.get_or_create_player(clean)
                        self.app.active_player_id = pid
                        self.app.active_player_name = rname
                        self._finish()
                elif event.key == pygame.K_ESCAPE:
                    self._on_back()
            return

        if self.mode == "login":
            if event.type == pygame.TEXTINPUT:
                if self.login_step == 0:
                    # Player ID like P-1
                    ch = event.text.upper()
                    if ch in "P0123456789-":
                        self.input_id = (self.input_id + ch)[:10]
                else:
                    self.input_name = sanitize_name(self.input_name + event.text)[:NAME_MAX_LEN]
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_BACKSPACE:
                    if self.login_step == 0:
                        self.input_id = self.input_id[:-1]
                    else:
                        self.input_name = self.input_name[:-1]
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    if self.login_step == 0:
                        pid = self.input_id.strip()
                        if not pid.startswith("P-") and pid.isdigit():
                            pid = f"P-{pid}"
                        self.input_id = pid
                        pdata = self.app.highscores.get_player(self.input_id)
                        if not pdata:
                            self.error_msg = f"Player ID '{self.input_id}' not found! Try again."
                        else:
                            self.error_msg = ""
                            self.login_step = 1  # now ask for matching name
                    else:
                        pdata = self.app.highscores.get_player(self.input_id)
                        if pdata and pdata.get("name", "").strip().lower() == self.input_name.strip().lower():
                            # Authenticated!
                            self.app.active_player_id = self.input_id
                            self.app.active_player_name = pdata["name"]
                            self.app.highscores.last_player_id = self.input_id
                            self.app.highscores.save()
                            self._finish()
                        else:
                            self.error_msg = "Player ID and Name do not match! Try again."
                elif event.key == pygame.K_ESCAPE:
                    self._on_back()
            return

        # Main mode
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._on_back()
        self.group.handle_event(event)
        self.back.handle_event(event)

    def draw(self, surface):
        self.app.draw_menu_backdrop(surface)
        cx = SCREEN_W // 2
        draw_glow_text(surface, "HUNTER ACCESS", theme.font("title", 56, True), (225, 245, 245),
                       theme.CYAN, (cx, 80), radius=3, glow_alpha=45)

        if self.mode == "menu":
            draw_text(surface, "Login with your Player ID & Name, or create a new profile",
                      theme.font("sans", 16), theme.TEXT_DIM, (cx, 140), "center")
            if self.app.active_player_name:
                active_str = f"Currently active: {self.app.active_player_name} [{self.app.active_player_id}]"
                draw_text(surface, active_str, theme.font("mono", 16, True), theme.GREEN, (cx, 185), "center")

            self.group.draw(surface)
            self.back.draw(surface)

        elif self.mode == "new":
            panel = pygame.Rect(0, 0, 560, 280)
            panel.center = (cx, SCREEN_H // 2)
            draw_panel(surface, panel, 250, theme.GREEN)
            draw_text(surface, "CREATE NEW HUNTER", theme.font("serif", 26, True), theme.GREEN,
                      (panel.centerx, panel.y + 40), "center")
            draw_text(surface, "Enter your hunter name:", theme.font("sans", 16), theme.TEXT_DIM,
                      (panel.centerx, panel.y + 85), "center")

            box = pygame.Rect(0, 0, 360, 50)
            box.center = (panel.centerx, panel.y + 140)
            pygame.draw.rect(surface, (10, 12, 18), box, border_radius=6)
            pygame.draw.rect(surface, theme.GREEN, box, 2, border_radius=6)
            caret = "_" if int(pygame.time.get_ticks() / 400) % 2 == 0 else " "
            draw_text(surface, self.new_name + caret, theme.font("mono", 26, True), theme.TEXT,
                      (box.x + 16, box.centery), "midleft")
            draw_text(surface, "Press ENTER to confirm   ·   ESC to cancel", theme.font("sans", 14),
                      theme.TEXT_FAINT, (panel.centerx, panel.bottom - 26), "center")

        elif self.mode == "login":
            panel = pygame.Rect(0, 0, 580, 320)
            panel.center = (cx, SCREEN_H // 2)
            draw_panel(surface, panel, 250, theme.CYAN)
            step_title = "STEP 1: ENTER PLAYER ID (e.g. P-1)" if self.login_step == 0 else f"STEP 2: VERIFY NAME FOR [{self.input_id}]"
            draw_text(surface, step_title, theme.font("serif", 22, True), theme.CYAN,
                      (panel.centerx, panel.y + 36), "center")

            prompt = "Enter your assigned Player ID:" if self.login_step == 0 else "Enter the name matching this Player ID:"
            draw_text(surface, prompt, theme.font("sans", 16), theme.TEXT_DIM,
                      (panel.centerx, panel.y + 85), "center")

            box = pygame.Rect(0, 0, 360, 50)
            box.center = (panel.centerx, panel.y + 140)
            pygame.draw.rect(surface, (10, 12, 18), box, border_radius=6)
            pygame.draw.rect(surface, theme.CYAN, box, 2, border_radius=6)
            caret = "_" if int(pygame.time.get_ticks() / 400) % 2 == 0 else " "
            curr_text = self.input_id if self.login_step == 0 else self.input_name
            draw_text(surface, curr_text + caret, theme.font("mono", 26, True), theme.TEXT,
                      (box.x + 16, box.centery), "midleft")

            if self.error_msg:
                draw_text(surface, self.error_msg, theme.font("sans", 15, True), theme.RED,
                          (panel.centerx, panel.y + 195), "center")

            draw_text(surface, "Press ENTER to proceed   ·   ESC to return", theme.font("sans", 14),
                      theme.TEXT_FAINT, (panel.centerx, panel.bottom - 26), "center")
