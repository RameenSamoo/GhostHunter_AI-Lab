"""Gameplay screen: grid rendering, HUD, minimap, pause, turn banners,
victory/scorecards and name entry, for all three modes.

The screen is a small state machine. Hotkeys are dispatched by mode, so
typing a name can never trigger the radar (Space), restart (R), pause (P) or
hint (H), and during Sir Nadeem's turn the arrows, radar and hint do nothing.

Modes
    Solo          - one human hunter (the original game).
    Simultaneous  - human (hunter 0) and Sir Nadeem (hunter 1) on one maze.
    Turn-based    - a TurnMatch: two consecutive sessions on the same level.
"""

from __future__ import annotations

import math
from enum import Enum, auto

import numpy as np
import pygame

from config import (AI_CATCH_MESSAGE, AI_CATCH_MESSAGE_DURATION, AI_NAME,
                    HINT_COOLDOWN, HINT_DURATION, HINT_PENALTY, MODE_LABELS,
                    MODE_SIMULTANEOUS, MODE_SOLO, MODE_TURNS, NAME_MAX_LEN,
                    RADAR_COOLDOWN, RADAR_DURATION, RADAR_PENALTY, RADAR_USES,
                    SCREEN_H, SCREEN_W, TURN_BANNER_DURATION, Difficulty)
from core.agents import Action, KeyboardAgent
from core.ai_agent import AIHunterAgent
from core.match import RESULT_MESSAGES, TurnMatch, decide_winner, simultaneous_session
from core.scoring import ScoreBreakdown, sanitize_name
from core.session import GameSession, HunterState
from . import theme
from .app import Screen
from .sprites import radial_gradient
from .widgets import (Button, ButtonGroup, draw_bar, draw_glow_text, draw_panel,
                      draw_text)

GRID_AREA = pygame.Rect(20, 20, 680, 680)
SIDEBAR_X = 720
SIDEBAR_W = SCREEN_W - SIDEBAR_X - 20

ARROWS = {
    pygame.K_UP: Action.UP,
    pygame.K_DOWN: Action.DOWN,
    pygame.K_LEFT: Action.LEFT,
    pygame.K_RIGHT: Action.RIGHT,
}

CAPTURE_ANIM = 1.1   # seconds of capture effect before the next turn / scorecard


class Mode(Enum):
    BANNER = auto()       # "Your turn" / "Sir Nadeem's turn" (turn-based only)
    PLAYING = auto()
    PAUSED = auto()
    CAPTURE = auto()      # short capture animation
    NAME_ENTRY = auto()
    VICTORY = auto()


def _num(v: float) -> str:
    """14,992.5 stays exact; 14,445.0 shows as 14,445."""
    return f"{v:,.1f}".removesuffix(".0")


class GameScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.agent = KeyboardAgent()
        self.session: GameSession | None = None
        self.match: TurnMatch | None = None
        self.difficulty: Difficulty | None = None
        self.game_mode = MODE_SOLO
        self.ai_first = False
        self.mode = Mode.PLAYING
        self.resume_mode = Mode.PLAYING
        self.t = 0.0
        self._build_overlay_buttons()

    # ================================================================ lifecycle
    def enter(self, difficulty: Difficulty | None = None, **_):
        if difficulty is not None:
            self.start(difficulty, self.app.game_mode, self.app.ai_first)
        # Returning from the difficulty screen without choosing keeps the old state.

    def leave(self):
        pygame.key.stop_text_input()
        self.agent.reset()

    def start(self, difficulty: Difficulty, game_mode: str | None = None, ai_first: bool | None = None) -> None:
        self.difficulty = difficulty
        if game_mode is not None:
            self.game_mode = game_mode
        if ai_first is not None:
            self.ai_first = ai_first
        self.agent.reset()
        rng = self.app.rng

        self.match = None
        if self.game_mode == MODE_SOLO:
            session = GameSession(difficulty, rng, self.agent)
        elif self.game_mode == MODE_SIMULTANEOUS:
            session = simultaneous_session(difficulty, rng, self.agent, AIHunterAgent(move_rate=difficulty.ai_speed))
        else:
            self.match = TurnMatch(difficulty, rng, self.agent, AIHunterAgent(move_rate=difficulty.ai_speed), self.ai_first)
            session = self.match.session

        self.capture_timer = 0.0
        self.name_text = ""
        self.saved_rank: int | None = None
        self.qualified = False
        self.heart_pulse = 0.0
        self.flash = 0.0
        self.ai_message_timer = 0.0
        self.last_catcher: int | None = None
        self.final: dict | None = None
        pygame.key.stop_text_input()
        self._begin_session(session)
        if self.match is not None:
            self._show_banner()
        else:
            self.mode = Mode.PLAYING

    def _begin_session(self, session: GameSession) -> None:
        self.session = session
        self.last_catcher = None
        self.app.sound.reset_heartbeat()
        self._layout()
        self._prerender_level()

    def _show_banner(self) -> None:
        self.mode = Mode.BANNER
        self.banner_timer = TURN_BANNER_DURATION
        self.agent.reset()

    # ============================================================ who is who
    @property
    def vs(self) -> bool:
        return self.game_mode != MODE_SOLO

    @property
    def ai_turn(self) -> bool:
        """Turn-based and it is Sir Nadeem's turn (the screen shows his hunt)."""
        return self.session is not None and self.session.primary.is_ai

    @property
    def human(self) -> HunterState | None:
        """The human's hunter in the current session, if any."""
        for h in self.session.hunters:
            if not h.is_ai:
                return h
        return None

    @property
    def human_hunting(self) -> bool:
        h = self.human
        return h is not None and not h.caught

    def _focus_index(self) -> int:
        """Which hunter the light follows: the human while hunting, else Sir Nadeem."""
        s = self.session
        for i, h in enumerate(s.hunters):
            if not h.is_ai and not h.caught:
                return i
        for i, h in enumerate(s.hunters):
            if not h.caught:
                return i
        return self.last_catcher if self.last_catcher is not None else 0

    # ================================================================ layout
    def _layout(self) -> None:
        n = self.session.grid.size
        self.cell = GRID_AREA.width // n
        px = self.cell * n
        self.origin = (GRID_AREA.centerx - px // 2, GRID_AREA.centery - px // 2)
        self.grid_rect = pygame.Rect(self.origin, (px, px))
        self.hunter_draw = [self._cell_px(c) for c in self.session.env.hunters]

        # Lights scaled to the cell size
        c = self.cell
        self.torch = [radial_gradient(int(c * k), (255, 170, 70), 120, 1.6) for k in (3.0, 3.15, 3.3, 3.45)]
        self.torch_ai = [radial_gradient(int(c * k), (170, 110, 255), 110, 1.6) for k in (3.0, 3.15, 3.3, 3.45)]
        self.ai_glow = radial_gradient(int(c * 1.4), (150, 100, 240), 120, 1.5)

        # Darkness mask twice the grid size with a light hole in the centre.
        # Each frame we blit the px*px window centred on the focus hunter: one blit.
        mask = pygame.Surface((2 * px, 2 * px), pygame.SRCALPHA)
        mask.fill((0, 0, 6, 175))
        hole = radial_gradient(int(c * 3.2), (0, 0, 0), 175, 1.2)
        mask.blit(hole, hole.get_rect(center=(px, px)), special_flags=pygame.BLEND_RGBA_SUB)
        self.dark_mask = mask.convert_alpha()
        self.ghost_aura = radial_gradient(int(c * 1.6), (60, 230, 220), 150, 1.5)

        # Minimap geometry
        mm = 222
        self.mm_cell = max(2, mm // n)
        mm_px = self.mm_cell * n
        self.mm_rect = pygame.Rect(0, 0, mm_px, mm_px)
        self.mm_rect.center = (SIDEBAR_X + 404, 352)

    def _prerender_level(self) -> None:
        grid, c, atlas = self.session.grid, self.cell, self.app.atlas
        px = c * grid.size
        self.floor_layer = pygame.Surface((px, px)).convert()
        self.floor_mask = pygame.Surface((px, px)).convert()
        self.floor_mask.fill((0, 0, 0))
        line = pygame.Surface((c, c), pygame.SRCALPHA)
        pygame.draw.rect(line, (0, 0, 0, 55), line.get_rect(), 1)
        for r in range(grid.size):
            for col in range(grid.size):
                pos = (col * c, r * c)
                if grid.walls[r][col]:
                    self.floor_layer.blit(atlas.tile("wall", (r, col), c), pos)
                else:
                    self.floor_layer.blit(atlas.tile("floor", (r, col), c), pos)
                    self.floor_layer.blit(line, pos)
                    self.floor_mask.fill((255, 255, 255), (*pos, c, c))
        # Wall edge bevel so corridors read clearly
        for r in range(grid.size):
            for col in range(grid.size):
                if grid.walls[r][col]:
                    x, y = col * c, r * c
                    pygame.draw.line(self.floor_layer, (95, 105, 125), (x, y), (x + c - 1, y))
                    pygame.draw.line(self.floor_layer, (8, 8, 12), (x, y + c - 1), (x + c - 1, y + c - 1))

        self.minimap_base = pygame.Surface(self.mm_rect.size).convert()
        m = self.mm_cell
        for r in range(grid.size):
            for col in range(grid.size):
                colour = theme.MINIMAP_WALL if grid.walls[r][col] else theme.MINIMAP_FLOOR
                self.minimap_base.fill(colour, (col * m, r * m, m, m))

        n = grid.size
        self.display_heat = np.zeros((n, n))
        self.heat_rgba = np.zeros((n, n, 4), dtype=np.uint8)

    # ================================================================ helpers
    def _cell_px(self, cell) -> tuple[float, float]:
        r, c = cell
        return (self.origin[0] + c * self.cell, self.origin[1] + r * self.cell)

    def _cell_center(self, cell) -> tuple[int, int]:
        x, y = self._cell_px(cell)
        return (int(x + self.cell / 2), int(y + self.cell / 2))

    # ================================================================ overlays
    def _build_overlay_buttons(self) -> None:
        cx = SCREEN_W // 2
        self.pause_buttons = ButtonGroup([
            Button((cx - 150, 300, 300, 56), "Resume", self._resume, 26),
            Button((cx - 150, 370, 300, 56), "Change Difficulty", self._change_difficulty, 26),
            Button((cx - 150, 440, 300, 56), "Quit", self._quit_to_menu, 26),
        ])
        y = 628
        self.victory_buttons = ButtonGroup([
            Button((cx - 330, y, 200, 52), "Play Again", self._play_again, 22, theme.GREEN),
            Button((cx - 110, y, 220, 52), "Change Difficulty", self._change_difficulty, 22),
            Button((cx + 130, y, 200, 52), "Main Menu", self._quit_to_menu, 22, theme.AMBER),
        ], horizontal=True)

    def _pause(self):
        self.resume_mode = self.mode
        self.mode = Mode.PAUSED
        self.agent.reset()
        self.pause_buttons.index = -1

    def _resume(self):
        self.mode = self.resume_mode
        self.agent.reset()

    def _change_difficulty(self):
        self.app.go("difficulty", return_to="game")

    def _quit_to_menu(self):
        self.session = None
        self.match = None
        self.app.go("menu")

    def _play_again(self):
        self.start(self.difficulty)

    def _after_capture(self):
        """Capture animation finished: next turn, or the end of the game."""
        if self.match is not None and self.match.advance():
            self._begin_session(self.match.session)
            self._show_banner()
            return
        self._finish()

    def _finish(self):
        """Collect results, then name entry (if the human qualifies) or the scorecard."""
        if self.match is not None:
            player, ai = self.match.results["player"], self.match.results["ai"]
        elif self.game_mode == MODE_SIMULTANEOUS:
            player, ai = self.session.hunters[0], self.session.hunters[1]
        else:
            player, ai = self.session.hunters[0], None
        self.final = {
            "player": player,
            "ai": ai,
            "winner": decide_winner(player.score, ai.score) if ai is not None else None,
        }
        self.qualified = self.app.highscores.qualifies(self.difficulty.key, player.score.final, self.game_mode)
        if self.qualified:
            # If an active player is already set, auto-record under their Player ID without prompting
            if self.app.active_player_name:
                p, ai = self.final["player"], self.final["ai"]
                self.saved_rank = self.app.highscores.add(
                    self.difficulty.key, self.app.active_player_name, p.score.final,
                    p.score.seconds, p.moves, mode=self.game_mode,
                    ai=ai.score if ai is not None else None, player_id=self.app.active_player_id)
                self.mode = Mode.VICTORY
            else:
                self.mode = Mode.NAME_ENTRY
                self.name_text = ""
                pygame.key.start_text_input()
        else:
            self.mode = Mode.VICTORY
        self._sync_victory_buttons()

    def _submit_name(self, skip: bool = False):
        pygame.key.stop_text_input()
        if not skip:
            entered = self.name_text.strip() or self.app.active_player_name
            pid, resolved_name = self.app.highscores.get_or_create_player(entered)
            self.app.active_player_name = resolved_name
            self.app.active_player_id = pid
            p, ai = self.final["player"], self.final["ai"]
            self.saved_rank = self.app.highscores.add(
                self.difficulty.key, resolved_name, p.score.final, p.score.seconds, p.moves,
                mode=self.game_mode, ai=ai.score if ai is not None else None, player_id=pid)
        self.mode = Mode.VICTORY
        self._sync_victory_buttons()

    def _sync_victory_buttons(self):
        for b in self.victory_buttons.buttons:
            b.enabled = self.mode == Mode.VICTORY
        self.victory_buttons.index = -1

    # ================================================================ events
    def handle_event(self, event):
        if self.session is None:
            return
        handler = {
            Mode.BANNER: self._events_banner,
            Mode.PLAYING: self._events_playing,
            Mode.PAUSED: self._events_paused,
            Mode.CAPTURE: lambda e: None,
            Mode.NAME_ENTRY: self._events_name_entry,
            Mode.VICTORY: self._events_victory,
        }[self.mode]
        handler(event)

    def _events_banner(self, event):
        # Pause and restart work for the whole game; nothing else during the banner.
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_p, pygame.K_ESCAPE):
                self._pause()
            elif event.key == pygame.K_r:
                self.start(self.difficulty)

    def _events_playing(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_p, pygame.K_ESCAPE):
                self._pause()
            elif event.key == pygame.K_r:
                self.start(self.difficulty)
            elif not self.human_hunting:
                return                      # Sir Nadeem's turn, or your hunt is over: just watch
            elif event.key in ARROWS:
                self.agent.key_down(ARROWS[event.key])
            elif event.key == pygame.K_SPACE:
                self.session.use_radar()
            elif event.key == pygame.K_h:
                self.session.use_hint()
        elif event.type == pygame.KEYUP and event.key in ARROWS:
            self.agent.key_up(ARROWS[event.key])
        elif event.type == pygame.WINDOWFOCUSLOST:
            self.agent.reset()   # don't keep "holding" a key released elsewhere

    def _events_paused(self, event):
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_p, pygame.K_ESCAPE):
            self._resume()
            return
        self.pause_buttons.handle_event(event)

    def _events_name_entry(self, event):
        # Only text, Backspace, Enter and Esc are live here. Space/R/P/H are just letters.
        if event.type == pygame.TEXTINPUT:
            self.name_text = sanitize_name(self.name_text + event.text)[:NAME_MAX_LEN]
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.name_text = self.name_text[:-1]
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._submit_name()
            elif event.key == pygame.K_ESCAPE:
                self._submit_name(skip=True)

    def _events_victory(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._quit_to_menu()
            return
        self.victory_buttons.handle_event(event)

    # ================================================================ update
    def update(self, dt):
        if self.session is None:
            return
        self.t += dt
        self.heart_pulse = max(0.0, self.heart_pulse - dt * 3)
        self.flash = max(0.0, self.flash - dt * 2.5)

        if self.mode == Mode.BANNER:
            self.banner_timer -= dt
            if self.banner_timer <= 0:
                self.mode = Mode.PLAYING          # the turn's clock starts now
        elif self.mode == Mode.PLAYING:
            s = self.session
            s.update(dt)
            self._consume_events()
            self.ai_message_timer = max(0.0, self.ai_message_timer - dt)
            if s.caught:
                self.mode = Mode.CAPTURE
                self.capture_timer = CAPTURE_ANIM
                self.flash = 1.0
                self.agent.reset()
            elif self.human_hunting and self.app.sound.update_heartbeat(
                    dt, self.human.belief.last_obs, s.grid.max_distance):
                self.heart_pulse = 1.0
        elif self.mode == Mode.CAPTURE:
            self.capture_timer -= dt
            if self.capture_timer <= 0:
                self._after_capture()

        if self.mode != Mode.PAUSED and self.session is not None:
            self._animate(dt)

    def _consume_events(self):
        snd = self.app.sound
        simultaneous = self.game_mode == MODE_SIMULTANEOUS
        for ev in self.session.events:
            if ev == "step":
                snd.play("step", 0.35)
            elif ev == "ai_step":
                snd.play("step", 0.22 if simultaneous else 0.35)
            elif ev == "radar":
                snd.play("radar_ping", 0.7)
            elif ev == "hint":
                snd.play("hint_chime", 0.6)
            elif ev in ("catch", "ai_catch"):
                snd.play("catch_stinger", 0.9)
                is_ai = ev == "ai_catch"
                self.last_catcher = next(i for i, h in enumerate(self.session.hunters) if h.is_ai == is_ai)
                if is_ai and simultaneous and not self.session.caught:
                    self.ai_message_timer = AI_CATCH_MESSAGE_DURATION
        self.session.events.clear()

    def _animate(self, dt):
        # Smooth hunter sprite motion and heat glow.
        k = min(1.0, dt * 22)
        for i, cell in enumerate(self.session.env.hunters):
            tx, ty = self._cell_px(cell)
            hx, hy = self.hunter_draw[i]
            self.hunter_draw[i] = (hx + (tx - hx) * k, hy + (ty - hy) * k)
        h = self.human
        if h is not None:
            target = h.belief.as_grid()
            self.display_heat += (target - self.display_heat) * min(1.0, dt * 9)

    # ================================================================ drawing
    def draw(self, surface):
        if self.session is None:
            return
        surface.fill(theme.BG)
        shake = (0, 0)
        if self.mode == Mode.CAPTURE:
            amp = 6 * (self.capture_timer / CAPTURE_ANIM)
            shake = (int(math.sin(self.t * 70) * amp), int(math.cos(self.t * 53) * amp))
        self._draw_grid(surface, shake)
        self._draw_sidebar(surface)

        if self.mode == Mode.BANNER:
            self._draw_banner(surface)
        elif self.mode == Mode.PAUSED:
            self._draw_pause(surface)
        elif self.mode in (Mode.NAME_ENTRY, Mode.VICTORY):
            if self.vs:
                self._draw_vs_victory(surface)
            else:
                self._draw_victory(surface)
        if self.flash > 0:
            f = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            f.fill((200, 255, 250, int(150 * self.flash)))
            surface.blit(f, (0, 0))

    # ---------------------------------------------------------------- grid
    def _draw_grid(self, surface, shake):
        s = self.session
        ox, oy = self.origin[0] + shake[0], self.origin[1] + shake[1]
        frame = self.grid_rect.inflate(16, 16).move(shake)
        draw_panel(surface, frame, 255, ornate=True)

        grid_pos = (ox, oy)
        px = self.grid_rect.width
        surface.blit(self.floor_layer, grid_pos)

        # Darkness with a light hole that follows the focus hunter (one blit).
        focus = self._focus_index()
        flick_i = int((math.sin(self.t * 11) + math.sin(self.t * 17.3) + 2) * 0.999)  # 0..3
        hx, hy = self.hunter_draw[focus]
        hcx = hx - self.origin[0] + self.cell / 2
        hcy = hy - self.origin[1] + self.cell / 2
        surface.blit(self.dark_mask, grid_pos, pygame.Rect(int(px - hcx), int(px - hcy), px, px))

        # HMM heat glow: the human's belief only, and only while the human hunts.
        if self.human_hunting:
            surface.blit(self._heat_surface(), grid_pos, special_flags=pygame.BLEND_RGB_ADD)

        clip = pygame.Rect(ox, oy, px, px)
        prev_clip = surface.get_clip()
        surface.set_clip(clip)
        # Flickering light around the focus hunter (amber for you, violet for Sir Nadeem)
        torch = (self.torch_ai if s.hunters[focus].is_ai else self.torch)[flick_i]
        surface.blit(torch, (ox + hcx - torch.get_width() / 2, oy + hcy - torch.get_height() / 2),
                     special_flags=pygame.BLEND_RGB_ADD)
        # Sir Nadeem's own small lantern glow when he isn't the focus (keeps him visible)
        for i, h in enumerate(s.hunters):
            if h.is_ai and not h.caught and i != focus:
                ax, ay = self.hunter_draw[i]
                glow = self.ai_glow
                surface.blit(glow, (ax + shake[0] + self.cell / 2 - glow.get_width() / 2,
                                    ay + shake[1] + self.cell / 2 - glow.get_height() / 2),
                             special_flags=pygame.BLEND_RGB_ADD)
        surface.set_clip(prev_clip)

        # A* hint path (human only)
        if s.hint_active and s.hint_result and s.hint_result.found and self.human_hunting:
            self._draw_hint(surface, shake)

        ended = self.mode in (Mode.CAPTURE, Mode.NAME_ENTRY, Mode.VICTORY)
        if s.ghost_visible_on_grid or ended:
            self._draw_ghost(surface, shake)

        # Hunters: everyone still hunting, plus the final catcher during the capture/end.
        bob = math.sin(self.t * 6) * self.cell * 0.03
        for i, h in enumerate(s.hunters):
            if h.caught and not (ended and i == self.last_catcher):
                continue                       # caught hunters leave the board
            x, y = self.hunter_draw[i]
            sprite = self.app.atlas.get("ai_hunter" if h.is_ai else "hunter", self.cell)
            surface.blit(sprite, (x + shake[0], y + shake[1] + bob))
            if h.is_ai and self.game_mode == MODE_SIMULTANEOUS and self.cell >= 20:
                self._draw_name_tag(surface, AI_NAME, (x + shake[0] + self.cell / 2, y + shake[1] - 2))

        self.app.atmosphere.draw_fog(surface, clip)

        # On-grid messages
        if self.game_mode == MODE_SIMULTANEOUS and self.mode == Mode.PLAYING:
            if self.ai_message_timer > 0:
                self._grid_message(surface, AI_CATCH_MESSAGE, theme.VIOLET, top=True)
            if self.human is not None and self.human.caught and not s.caught:
                self._grid_message(surface, f"You caught the ghost! {AI_NAME} is still hunting...",
                                   theme.GREEN, top=False)

    def _draw_name_tag(self, surface, text, midbottom):
        fnt = theme.font("sans", 13, True)
        img = fnt.render(text, True, theme.VIOLET)
        rect = img.get_rect(midbottom=(int(midbottom[0]), int(midbottom[1])))
        bg = pygame.Surface(rect.inflate(8, 2).size, pygame.SRCALPHA)
        bg.fill((8, 6, 14, 170))
        surface.blit(bg, rect.inflate(8, 2))
        surface.blit(img, rect)

    def _grid_message(self, surface, text, colour, top=True):
        fnt = theme.font("serif", 22, True)
        img = fnt.render(text, True, colour)
        rect = img.get_rect(centerx=self.grid_rect.centerx)
        if top:
            rect.top = self.grid_rect.top + 14
        else:
            rect.bottom = self.grid_rect.bottom - 14
        box = rect.inflate(32, 18)
        draw_panel(surface, box, 235, colour)
        surface.blit(img, rect)

    def _heat_surface(self) -> pygame.Surface:
        n = self.session.grid.size
        heat = self.display_heat
        peak = heat.max()
        positive = heat[heat > 1e-12]
        if peak <= 0 or (len(positive) > 1 and positive.max() - positive.min() <= 1e-9 * peak):
            # Flat belief (no reading yet): no cell is more likely than another,
            # so nothing glows warm. Without this, every cell would tie for
            # "hottest" and the whole maze would render red.
            rel = np.zeros_like(heat)
        else:
            rel = np.sqrt(heat / peak)
        stops = theme.HEAT_STOPS
        xs = np.array([p for p, _ in stops])
        rgb = np.stack([np.interp(rel, xs, [c[i] for _, c in stops]) for i in range(3)], axis=-1)
        # Cold cells stay a faint blue; hot cells glow strongly.
        intensity = (0.10 + 0.90 * rel ** 1.3)[..., None]
        floor = ~np.array(self.session.grid.walls)
        base = rgb * intensity * floor[..., None]

        # Half the light as crisp per-cell squares (readable), half as a soft halo.
        self.heat_rgba[..., :3] = (base * 0.5).astype(np.uint8)
        self.heat_rgba[..., 3] = 255
        small = pygame.image.frombuffer(self.heat_rgba.tobytes(), (n, n), "RGBA").convert()
        glow = pygame.transform.smoothscale(small, self.grid_rect.size)
        glow.blit(pygame.transform.scale(small, self.grid_rect.size), (0, 0),
                  special_flags=pygame.BLEND_RGB_ADD)
        glow.blit(self.floor_mask, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        return glow

    def _draw_hint(self, surface, shake):
        s = self.session
        fade = min(1.0, s.hint_remaining / 0.4)
        path = s.hint_result.path
        ox, oy = self.origin[0] + shake[0], self.origin[1] + shake[1]
        pts = [(x - self.origin[0], y - self.origin[1]) for x, y in (self._cell_center(c) for c in path)]
        layer = pygame.Surface(self.grid_rect.size, pygame.SRCALPHA)
        if len(pts) > 1:
            pygame.draw.lines(layer, (255, 190, 80, int(70 * fade)), False, pts, max(3, self.cell // 4))
            pygame.draw.lines(layer, (255, 220, 140, int(200 * fade)), False, pts, max(1, self.cell // 12))
        # Dots pulsing toward the target
        for i, (x, y) in enumerate(pts[1:], 1):
            pulse = 0.5 + 0.5 * math.sin((i - self.t * 8) * 0.9)
            r = max(2, int(self.cell * (0.08 + 0.06 * pulse)))
            pygame.draw.circle(layer, (255, 230, 160, int(230 * fade)), (x, y), r)
        tx, ty = pts[-1]
        ring = int(self.cell * (0.35 + 0.12 * math.sin(self.t * 8)))
        pygame.draw.circle(layer, (255, 120, 60, int(230 * fade)), (tx, ty), ring, max(2, self.cell // 14))
        surface.blit(layer, (ox, oy))

    def _draw_ghost(self, surface, shake):
        s = self.session
        x, y = self._cell_px(s.env.ghost)
        x += shake[0]
        y += shake[1]
        if self.mode == Mode.PLAYING:
            jitter = (math.sin(self.t * 97) * self.cell * 0.05, math.cos(self.t * 71) * self.cell * 0.05)
            alpha = int(120 + 135 * abs(math.sin(self.t * 43)))
        else:
            jitter = (0, -math.sin(self.t * 3) * self.cell * 0.06)
            alpha = 235
        aura = self.ghost_aura
        cx, cy = x + self.cell / 2, y + self.cell / 2
        surface.blit(aura, (cx - aura.get_width() / 2, cy - aura.get_height() / 2),
                     special_flags=pygame.BLEND_RGB_ADD)
        ghost = self.app.atlas.get("ghost", self.cell).copy()
        ghost.set_alpha(alpha)
        surface.blit(ghost, (x + jitter[0], y + jitter[1]))

    # ---------------------------------------------------------------- sidebar
    def _draw_sidebar(self, surface):
        s, d = self.session, self.difficulty
        x = SIDEBAR_X

        # Header
        head = pygame.Rect(x, 20, SIDEBAR_W, 92)
        draw_panel(surface, head)
        draw_glow_text(surface, "GHOST HUNTER 2D", theme.font("title", 34, True), (225, 245, 245),
                       theme.CYAN, (x + 20, 30), anchor="topleft", radius=2, glow_alpha=40)
        if self.vs:
            line = f"{MODE_LABELS[self.game_mode]}  ·  {d.name} {d.size}×{d.size}  ·  ×{d.multiplier:.1f}"
        else:
            line = f"{d.name}  ·  {d.size}×{d.size}  ·  score ×{d.multiplier:.1f}"
        draw_text(surface, line, theme.font("sans", 17), theme.TEXT_DIM, (x + 22, 78))
        if self.match is not None:
            whose = AI_NAME.upper() if self.ai_turn else "YOU"
            draw_text(surface, f"TURN {self.match.turn + 1}/2 · {whose}", theme.font("mono", 14, True),
                      theme.VIOLET if self.ai_turn else theme.AMBER, (head.right - 18, 38), "topright")

        # Time / moves tiles (the hunter whose screen this is)
        p = s.primary
        half = (SIDEBAR_W - 12) // 2
        prefix = f"{AI_NAME} · " if p.is_ai else ""
        tiles = ((prefix + "Time", f"{p.time(s.elapsed):6.1f}s"), (prefix + "Moves", f"{p.moves}"))
        for i, (label, value) in enumerate(tiles):
            r = pygame.Rect(x + i * (half + 12), 124, half, 78)
            draw_panel(surface, r, title=label)
            draw_text(surface, value.strip(), theme.font("mono", 36, True),
                      theme.VIOLET if p.is_ai else theme.TEXT, (r.right - 18, r.centery + 8), "midright")

        # PKE / heat signature panel
        pke = pygame.Rect(x, 214, half, 276)
        draw_panel(surface, pke, title="Heat signature (PKE)")
        self._draw_pke(surface, pke)

        # Minimap
        mm_panel = pygame.Rect(x + half + 12, 214, half, 276)
        draw_panel(surface, mm_panel, title="Spirit radar")
        self._draw_minimap(surface)

        # Abilities
        ab = pygame.Rect(x, 502, SIDEBAR_W, 112)
        draw_panel(surface, ab)
        self._draw_abilities(surface, ab)

        # Bottom panel: controls legend (solo) or the VS panel
        bottom = pygame.Rect(x, 626, SIDEBAR_W, 74)
        draw_panel(surface, bottom, edge=theme.VIOLET_DIM if self.vs else theme.PANEL_EDGE)
        if self.vs:
            self._draw_vs_panel(surface, bottom)
        else:
            self._draw_legend(surface, bottom)

    def _draw_legend(self, surface, legend):
        keys = [("←↑↓→", "move"), ("SPACE", "radar"), ("H", "hint"), ("P", "pause"), ("R", "new maze")]
        lx = legend.x + 20
        for k, label in keys:
            kr = draw_text(surface, k, theme.font("mono", 16, True), theme.AMBER, (lx, legend.y + 16))
            lr = draw_text(surface, label, theme.font("sans", 15), theme.TEXT_DIM, (kr.right + 6, legend.y + 17))
            lx = lr.right + 18
        draw_text(surface, "Warm floor = where the ghost probably is. Hunt the red.",
                  theme.font("sans", 15), theme.TEXT_FAINT, (legend.x + 20, legend.y + 44))

    def _draw_vs_panel(self, surface, rect):
        s = self.session
        x0, y1, y2 = rect.x + 18, rect.y + 13, rect.y + 43
        name_font = theme.font("sans", 16, True)
        body = theme.font("mono", 15, True)
        keys_line = "←↑↓→ move · SPACE radar · H hint · P pause · R restart"

        if self.game_mode == MODE_SIMULTANEOUS:
            ai = s.hunters[1]
            nr = draw_text(surface, AI_NAME.upper(), name_font, theme.VIOLET, (x0, y1))
            if ai.caught:
                status = f"CAUGHT IT · {ai.catch_time:.1f}s · {ai.moves} moves · {ai.score.final:,}"
                colour = theme.VIOLET
            else:
                status = f"Hunting...  ·  {s.elapsed:.1f}s  ·  {ai.moves} moves"
                colour = theme.TEXT_DIM
            draw_text(surface, status, body, colour, (nr.right + 14, y1 + 1))
            draw_text(surface, keys_line, theme.font("sans", 14), theme.TEXT_FAINT, (x0, y2))
            return

        # Turn-based
        m = self.match
        target = m.target
        if target is not None:
            setter = AI_NAME if m.order[0] == "ai" else "you"
            lr = draw_text(surface, "TARGET TO BEAT", name_font, theme.AMBER, (x0, y1))
            draw_text(surface, f"{target.final:,}", theme.font("mono", 20, True), theme.TEXT,
                      (lr.right + 14, y1 - 2))
            draw_text(surface, f"set by {setter}", theme.font("sans", 14), theme.TEXT_FAINT,
                      (rect.right - 18, y1 + 2), "topright")
        else:
            first = AI_NAME if self.ai_turn else "You"
            draw_text(surface, f"FIRST TURN  ·  {first} set{'s' if self.ai_turn else ''} the target",
                      name_font, theme.AMBER, (x0, y1))
        if self.ai_turn:
            draw_text(surface, f"Watching {AI_NAME}  ·  P pause  ·  R restart the game",
                      theme.font("sans", 14), theme.TEXT_FAINT, (x0, y2))
        else:
            draw_text(surface, keys_line, theme.font("sans", 14), theme.TEXT_FAINT, (x0, y2))

    def _draw_pke(self, surface, rect):
        s = self.session
        if self.ai_turn:
            draw_text(surface, "Sensor hidden", theme.font("serif", 24, True), theme.VIOLET,
                      (rect.centerx, rect.y + 96), "center")
            for i, line in enumerate((f"{AI_NAME} reads his", "own instruments.", "", "You're watching", "this turn.")):
                draw_text(surface, line, theme.font("sans", 16), theme.TEXT_DIM,
                          (rect.centerx, rect.y + 132 + i * 24), "center")
            return
        h = self.human
        if h.caught:
            draw_text(surface, "Ghost caught", theme.font("serif", 24, True), theme.GREEN,
                      (rect.centerx, rect.y + 96), "center")
            draw_text(surface, f"{h.catch_time:.1f}s  ·  {h.moves} moves", theme.font("mono", 18, True),
                      theme.TEXT, (rect.centerx, rect.y + 132), "center")
            draw_text(surface, "Sensor off", theme.font("sans", 16), theme.TEXT_DIM,
                      (rect.centerx, rect.y + 168), "center")
            return

        reading = h.belief.last_obs
        maxd = max(1, s.grid.max_distance)
        closeness = 0.0 if reading is None else 1.0 - min(1.0, reading / maxd)

        draw_text(surface, "Reading", theme.font("sans", 15), theme.TEXT_DIM, (rect.x + 18, rect.y + 38))
        txt = "--" if reading is None else f"{reading}"
        colour = theme.heat_colour(closeness)
        draw_text(surface, txt, theme.font("mono", 58, True), colour, (rect.x + 18, rect.y + 56))
        draw_text(surface, "cells away (noisy)", theme.font("sans", 14), theme.TEXT_FAINT,
                  (rect.x + 20, rect.y + 122))

        # Segmented meter
        segs = 12
        lit = round(closeness * segs)
        sw = (rect.width - 36 - (segs - 1) * 3) / segs
        for i in range(segs):
            r = pygame.Rect(rect.x + 18 + i * (sw + 3), rect.y + 150, sw, 22)
            c = theme.heat_colour(i / (segs - 1)) if i < lit else (32, 35, 46)
            pygame.draw.rect(surface, c, r, border_radius=2)

        # Peak belief
        peak = float(h.belief.belief.max())
        draw_text(surface, "Hottest cell", theme.font("sans", 15), theme.TEXT_DIM, (rect.x + 18, rect.y + 190))
        draw_text(surface, f"{peak * 100:4.1f}%", theme.font("mono", 22, True), theme.TEXT,
                  (rect.right - 18, rect.y + 188), "topright")
        draw_bar(surface, (rect.x + 18, rect.y + 216, rect.width - 36, 8), peak, theme.heat_colour(peak))

        # Heartbeat
        size = int(30 + 12 * self.heart_pulse)
        heart = self.app.atlas.get("heart_icon", size)
        surface.blit(heart, (rect.x + 34 - size // 2, rect.y + 252 - size // 2))
        interval = self.app.sound.heartbeat_interval(reading, s.grid.max_distance)
        draw_text(surface, f"{60 / interval:3.0f} bpm", theme.font("mono", 18, True),
                  theme.RED if closeness > 0.7 else theme.TEXT_DIM, (rect.x + 60, rect.y + 241))

    def _draw_minimap(self, surface):
        s = self.session
        rect = self.mm_rect
        surface.blit(self.minimap_base, rect)
        m = self.mm_cell
        # Hunters still on the board: you in amber, Sir Nadeem in violet.
        for i, h in enumerate(s.hunters):
            if h.caught:
                continue
            hr, hc = s.env.hunters[i]
            cen = (rect.x + hc * m + m // 2, rect.y + hr * m + m // 2)
            pygame.draw.circle(surface, theme.VIOLET if h.is_ai else theme.AMBER, cen, max(2, int(m * 0.42)))

        if s.ghost_visible_on_minimap:
            # Sweep line
            ang = self.t * 5
            length = rect.width * 0.75
            end = (rect.centerx + math.cos(ang) * length, rect.centery + math.sin(ang) * length)
            layer = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.line(layer, (90, 240, 230, 90), (rect.width / 2, rect.height / 2),
                             (end[0] - rect.x, end[1] - rect.y), 2)
            surface.blit(layer, rect)
            gr, gc = s.env.ghost
            gcen = (rect.x + gc * m + m // 2, rect.y + gr * m + m // 2)
            pulse = 0.5 + 0.5 * math.sin(self.t * 12)
            pygame.draw.circle(surface, theme.CYAN, gcen, max(2, int(m * 0.45)))
            pygame.draw.circle(surface, theme.CYAN, gcen, int(m * (0.8 + 0.9 * pulse)), 1)
            status, colour = f"GHOST LOCATED  {s.radar_remaining:.1f}s", theme.CYAN
        else:
            status, colour = "Ghost hidden", theme.TEXT_FAINT
        pygame.draw.rect(surface, theme.PANEL_EDGE, rect.inflate(4, 4), 1)
        draw_text(surface, status, theme.font("sans", 14, True), colour, (rect.centerx, rect.bottom + 8), "midtop")

    def _draw_abilities(self, surface, rect):
        s = self.session
        half = rect.width // 2
        atlas = self.app.atlas

        # Radar
        x0 = rect.x + 18
        surface.blit(atlas.get("radar_icon", 32), (x0, rect.y + 14))
        draw_text(surface, "SPIRIT RADAR", theme.font("sans", 16, True), theme.CYAN, (x0 + 42, rect.y + 14))
        draw_text(surface, f"SPACE  ·  −{RADAR_PENALTY}", theme.font("mono", 13), theme.TEXT_FAINT, (x0 + 42, rect.y + 34))
        for i in range(RADAR_USES):
            filled = i < s.radar_charges
            c = (x0 + half - 70 + i * 18, rect.y + 24)
            pygame.draw.circle(surface, theme.CYAN if filled else (40, 46, 58), c, 6)
            pygame.draw.circle(surface, theme.CYAN_DIM, c, 6, 1)
        bar = pygame.Rect(x0, rect.y + 62, half - 40, 12)
        if s.ghost_visible_on_minimap:
            draw_bar(surface, bar, s.radar_remaining / RADAR_DURATION, theme.CYAN)
            label = "ACTIVE"
        elif s.radar_charges == 0:
            draw_bar(surface, bar, 0, theme.CYAN)
            label = "NO CHARGES LEFT"
        elif s.radar_cooldown > 0:
            draw_bar(surface, bar, 1 - s.radar_cooldown / RADAR_COOLDOWN, (70, 80, 100))
            label = f"COOLDOWN {s.radar_cooldown:.1f}s"
        else:
            draw_bar(surface, bar, 1, theme.CYAN_DIM)
            label = f"READY  ({s.radar_charges}/{RADAR_USES})"
        draw_text(surface, label, theme.font("mono", 14, True), theme.TEXT_DIM, (x0, rect.y + 82))

        # Hint
        x1 = rect.x + half + 10
        surface.blit(atlas.get("hint_icon", 32), (x1, rect.y + 14))
        draw_text(surface, "A* HINT PATH", theme.font("sans", 16, True), theme.AMBER, (x1 + 42, rect.y + 14))
        draw_text(surface, f"H  ·  −{HINT_PENALTY}  ·  used {s.hint_uses}", theme.font("mono", 13),
                  theme.TEXT_FAINT, (x1 + 42, rect.y + 34))
        bar = pygame.Rect(x1, rect.y + 62, half - 40, 12)
        if s.hint_active:
            draw_bar(surface, bar, s.hint_remaining / HINT_DURATION, theme.AMBER)
            res = s.hint_result
            label = f"SHOWING  {res.cost} steps · {res.nodes_expanded} nodes" if res else "SHOWING"
        elif s.hint_cooldown > 0:
            draw_bar(surface, bar, 1 - s.hint_cooldown / HINT_COOLDOWN, (70, 80, 100))
            label = f"COOLDOWN {s.hint_cooldown:.1f}s"
        else:
            draw_bar(surface, bar, 1, theme.AMBER_DIM)
            label = "READY  (unlimited)"
        draw_text(surface, label, theme.font("mono", 14, True), theme.TEXT_DIM, (x1, rect.y + 82))

        # Not usable right now: Sir Nadeem's turn, or your hunt is over.
        if self.ai_turn or not self.human_hunting:
            veil = pygame.Surface(rect.inflate(-4, -4).size, pygame.SRCALPHA)
            veil.fill((10, 11, 16, 215))
            surface.blit(veil, rect.inflate(-4, -4))
            msg = f"Not available during {AI_NAME}'s turn" if self.ai_turn else "Your hunt is over"
            draw_text(surface, msg, theme.font("sans", 17, True), theme.TEXT_DIM, rect.center, "center")

    # ---------------------------------------------------------------- overlays
    def _dim(self, surface, alpha=170):
        dim = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        dim.fill((2, 3, 6, alpha))
        surface.blit(dim, (0, 0))

    def _draw_banner(self, surface):
        """Turn intro: dims the grid; the turn clock starts when it ends."""
        m = self.match
        ai = self.ai_turn
        dim = pygame.Surface(self.grid_rect.inflate(16, 16).size, pygame.SRCALPHA)
        dim.fill((2, 3, 6, 200))
        surface.blit(dim, self.grid_rect.inflate(16, 16))
        cx, cy = self.grid_rect.center
        accent = theme.VIOLET if ai else theme.AMBER
        title = f"{AI_NAME.upper()}'S TURN" if ai else "YOUR TURN"
        draw_text(surface, f"TURN {m.turn + 1} OF 2", theme.font("mono", 18, True), theme.TEXT_DIM,
                  (cx, cy - 92), "center")
        draw_glow_text(surface, title, theme.font("title", 58, True), (240, 240, 250), accent,
                       (cx, cy - 40), radius=3, glow_alpha=55)
        sub = "Watch him hunt the ghost." if ai else "Find the ghost. Trust the heat."
        draw_text(surface, sub, theme.font("serif", 20), theme.TEXT, (cx, cy + 14), "center")
        if m.target is not None:
            draw_text(surface, f"Target to beat: {m.target.final:,}", theme.font("mono", 22, True),
                      theme.AMBER, (cx, cy + 52), "center")
        secs = max(1, math.ceil(self.banner_timer))
        draw_text(surface, f"Starting in {secs}", theme.font("sans", 16), theme.TEXT_DIM,
                  (cx, cy + 92), "center")
        sprite = self.app.atlas.get("ai_hunter" if ai else "hunter", 72)
        surface.blit(sprite, (cx - 36, cy - 190))

    def _draw_pause(self, surface):
        self._dim(surface)
        panel = pygame.Rect(0, 0, 440, 360)
        panel.center = (SCREEN_W // 2, SCREEN_H // 2 + 10)
        draw_panel(surface, panel, 255, theme.CYAN_DIM)
        draw_glow_text(surface, "PAUSED", theme.font("title", 56, True), (225, 245, 245), theme.CYAN,
                       (SCREEN_W // 2, panel.y + 58), radius=3, glow_alpha=45)
        self.pause_buttons.draw(surface)
        draw_text(surface, "P / Esc to resume", theme.font("sans", 14), theme.TEXT_FAINT,
                  (SCREEN_W // 2, panel.bottom - 26), "center")

    def _draw_name_entry(self, surface, cx, box_y):
        prompt = f"NEW HIGH SCORE!  Confirm Hunter Name [{self.app.active_player_id}]:"
        draw_text(surface, prompt, theme.font("sans", 18, True), theme.GREEN,
                  (cx, box_y), "midtop")
        box = pygame.Rect(0, 0, 360, 50)
        box.midtop = (cx, box_y + 30)
        pygame.draw.rect(surface, (10, 12, 18), box, border_radius=6)
        pygame.draw.rect(surface, theme.GREEN, box, 2, border_radius=6)
        caret = "_" if int(self.t * 2.5) % 2 == 0 else " "
        draw_text(surface, self.name_text + caret, theme.font("mono", 28, True), theme.TEXT,
                  (box.x + 16, box.centery), "midleft")
        draw_text(surface, f"{len(self.name_text)}/{NAME_MAX_LEN}", theme.font("mono", 13), theme.TEXT_FAINT,
                  (box.right - 10, box.bottom - 6), "bottomright")
        draw_text(surface, "Letters, numbers, spaces  ·  Enter to save  ·  Esc to skip",
                  theme.font("sans", 14), theme.TEXT_FAINT, (cx, box.bottom + 10), "midtop")

    def _save_message(self) -> tuple[str, tuple]:
        table = MODE_LABELS[self.game_mode] if self.vs else self.difficulty.name
        if self.saved_rank:
            where = f"{self.difficulty.name} · {table}" if self.vs else table
            return f"Saved as #{self.saved_rank} in the {where} hall of hunters.", theme.GREEN
        if self.qualified:
            return "Score not saved.", theme.TEXT_DIM
        return "Not quite a top-5 hunt this time.", theme.TEXT_DIM

    def _draw_victory(self, surface):
        """Solo scorecard (unchanged from the original game)."""
        sc = self.final["player"].score
        self._dim(surface, 150)
        panel = pygame.Rect(0, 0, 720, 690)
        panel.center = (SCREEN_W // 2, SCREEN_H // 2)
        draw_panel(surface, panel, 255, theme.CYAN_DIM)
        cx = panel.centerx
        draw_glow_text(surface, "GHOST CAPTURED", theme.font("title", 58, True), (225, 255, 250), theme.CYAN,
                       (cx, panel.y + 52), radius=4, glow_alpha=55)
        draw_text(surface, f"{self.difficulty.name}  ·  {self.difficulty.size}×{self.difficulty.size}",
                  theme.font("sans", 16), theme.TEXT_DIM, (cx, panel.y + 96), "center")

        # Stat tiles
        stats = [("TIME", f"{sc.seconds:.1f}s"), ("MOVES", str(sc.moves)),
                 ("RADAR", f"{sc.radar_uses}/{RADAR_USES}"), ("HINTS", str(sc.hint_uses))]
        tw = 150
        sx = cx - (4 * tw + 3 * 12) // 2
        for i, (label, value) in enumerate(stats):
            r = pygame.Rect(sx + i * (tw + 12), panel.y + 118, tw, 66)
            draw_panel(surface, r, 255, title=label)
            draw_text(surface, value, theme.font("mono", 26, True), theme.TEXT, (r.right - 14, r.y + 30), "topright")

        # Itemised breakdown
        lines = [
            ("Base score", f"max(0, 10000 − 50×{sc.seconds:.1f} − 20×{sc.moves})", _num(sc.base), theme.TEXT),
            ("Difficulty", f"× {sc.multiplier:.1f}", _num(sc.scaled), theme.TEXT),
            ("Radar penalty", f"{sc.radar_uses} × {RADAR_PENALTY}", f"−{sc.radar_penalty:,}", theme.RED if sc.radar_penalty else theme.TEXT_DIM),
            ("Hint penalty", f"{sc.hint_uses} × {HINT_PENALTY}", f"−{sc.hint_penalty:,}", theme.RED if sc.hint_penalty else theme.TEXT_DIM),
        ]
        ly = panel.y + 208
        for label, formula, value, colour in lines:
            draw_text(surface, label, theme.font("sans", 18, True), theme.TEXT_DIM, (panel.x + 50, ly))
            draw_text(surface, formula, theme.font("mono", 16), theme.TEXT_FAINT, (panel.x + 210, ly + 2))
            draw_text(surface, value, theme.font("mono", 20, True), colour, (panel.right - 50, ly), "topright")
            ly += 34
        pygame.draw.line(surface, theme.PANEL_EDGE, (panel.x + 50, ly + 4), (panel.right - 50, ly + 4), 2)
        draw_text(surface, "FINAL SCORE", theme.font("serif", 26, True), theme.TEXT, (panel.x + 50, ly + 20))
        draw_glow_text(surface, f"{sc.final:,}", theme.font("mono", 46, True),
                       theme.AMBER if sc.final >= 0 else theme.RED, (255, 120, 40),
                       (panel.right - 50, ly + 36), anchor="midright", radius=2, glow_alpha=50)

        # Name entry / save result
        box_y = ly + 82
        if self.mode == Mode.NAME_ENTRY:
            self._draw_name_entry(surface, cx, box_y)
        else:
            msg, colour = self._save_message()
            draw_text(surface, msg, theme.font("serif", 20), colour, (cx, box_y + 30), "midtop")

        for b in self.victory_buttons.buttons:
            b.rect.y = panel.bottom - 76
        self.victory_buttons.draw(surface)

    def _draw_vs_victory(self, surface):
        """Both scorecards side by side, the result message, name entry, buttons."""
        player, ai, winner = self.final["player"], self.final["ai"], self.final["winner"]
        self._dim(surface, 150)
        panel = pygame.Rect(0, 0, 1000, 690)
        panel.center = (SCREEN_W // 2, SCREEN_H // 2)
        draw_panel(surface, panel, 255, theme.CYAN_DIM)
        cx = panel.centerx
        draw_glow_text(surface, "GHOST CAPTURED", theme.font("title", 50, True), (225, 255, 250), theme.CYAN,
                       (cx, panel.y + 42), radius=3, glow_alpha=50)
        d = self.difficulty
        draw_text(surface, f"{MODE_LABELS[self.game_mode]}  ·  {d.name} {d.size}×{d.size}  ·  ×{d.multiplier:.1f}",
                  theme.font("sans", 15), theme.TEXT_DIM, (cx, panel.y + 80), "center")
        result_colour = {"player": theme.GREEN, "ai": theme.RED, "tie": theme.AMBER}[winner]
        draw_text(surface, RESULT_MESSAGES[winner], theme.font("serif", 26, True), result_colour,
                  (cx, panel.y + 114), "center")

        col_w, gap = 445, 30
        col_y = panel.y + 142
        for j, (state, name, accent) in enumerate(((player, "You", theme.AMBER), (ai, AI_NAME, theme.VIOLET))):
            rect = pygame.Rect(panel.x + (panel.width - 2 * col_w - gap) // 2 + j * (col_w + gap), col_y, col_w, 330)
            is_winner = winner == ("player" if j == 0 else "ai")
            self._draw_scorecard(surface, rect, state.score, name, accent, is_winner, j == 1)

        box_y = col_y + 346
        if self.mode == Mode.NAME_ENTRY:
            self._draw_name_entry(surface, cx, box_y)
        else:
            msg, colour = self._save_message()
            draw_text(surface, msg, theme.font("serif", 20), colour, (cx, box_y + 36), "midtop")

        for b in self.victory_buttons.buttons:
            b.rect.y = panel.bottom - 72
        self.victory_buttons.draw(surface)

    def _draw_scorecard(self, surface, rect, sc: ScoreBreakdown, name, accent, is_winner, is_ai):
        draw_panel(surface, rect, 255, accent if is_winner else theme.PANEL_EDGE)
        x0, x1 = rect.x + 22, rect.right - 22
        sprite = self.app.atlas.get("ai_hunter" if is_ai else "hunter", 40)
        surface.blit(sprite, (x0 - 4, rect.y + 10))
        draw_text(surface, name, theme.font("serif", 26, True), accent, (x0 + 44, rect.y + 16))
        if is_winner:
            tag = draw_text(surface, "WINNER", theme.font("mono", 14, True), theme.BG, (x1 - 8, rect.y + 22), "topright")
            pygame.draw.rect(surface, accent, tag.inflate(14, 8), border_radius=4)
            draw_text(surface, "WINNER", theme.font("mono", 14, True), theme.BG, (x1 - 8, rect.y + 22), "topright")

        rows = [
            ("Time", f"{sc.seconds:.1f}s", theme.TEXT),
            ("Moves", str(sc.moves), theme.TEXT),
            ("Radar used", f"{sc.radar_uses}/{RADAR_USES}", theme.TEXT),
            ("Hints used", str(sc.hint_uses), theme.TEXT),
            ("Base score", _num(sc.base), theme.TEXT),
            (f"× {sc.multiplier:.1f} difficulty", _num(sc.scaled), theme.TEXT),
            ("Radar penalty", f"−{sc.radar_penalty:,}", theme.RED if sc.radar_penalty else theme.TEXT_DIM),
            ("Hint penalty", f"−{sc.hint_penalty:,}", theme.RED if sc.hint_penalty else theme.TEXT_DIM),
        ]
        y = rect.y + 64
        for label, value, colour in rows:
            draw_text(surface, label, theme.font("sans", 16), theme.TEXT_DIM, (x0, y))
            draw_text(surface, value, theme.font("mono", 17, True), colour, (x1, y), "topright")
            if label == "Base score":
                draw_text(surface, f"10000 − 50×{sc.seconds:.1f} − 20×{sc.moves}", theme.font("mono", 12),
                          theme.TEXT_FAINT, (x0 + 100, y + 3))
            y += 26
        pygame.draw.line(surface, theme.PANEL_EDGE, (x0, y + 4), (x1, y + 4), 2)
        draw_text(surface, "FINAL", theme.font("serif", 22, True), theme.TEXT, (x0, y + 18))
        draw_glow_text(surface, f"{sc.final:,}", theme.font("mono", 34, True),
                       theme.AMBER if sc.final >= 0 else theme.RED, (255, 120, 40),
                       (x1, y + 30), anchor="midright", radius=2, glow_alpha=45)
