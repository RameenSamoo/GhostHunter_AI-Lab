"""Application shell: window, main loop and the screen state machine."""

from __future__ import annotations

import random

import pygame

from config import (ASSETS_DIR, AUDIO_DIR, DATABASE_FILE, FPS, HIGHSCORE_FILE, MODE_SOLO,
                    SCREEN_H, SCREEN_W, WINDOW_TITLE)
from core.database import HighScoreTable
from sfx.manager import SoundManager
from .atmosphere import Atmosphere
from .sprites import SpriteAtlas


class Screen:
    """Base class for every top-level screen."""

    def __init__(self, app: "App"):
        self.app = app

    def enter(self, **kwargs) -> None: ...
    def leave(self) -> None: ...
    def handle_event(self, event: pygame.event.Event) -> None: ...
    def update(self, dt: float) -> None: ...
    def draw(self, surface: pygame.Surface) -> None: ...


class App:
    def __init__(self, seed: int | None = None, mute: bool = False, regen_assets: bool = False):
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.init()
        pygame.display.set_caption(WINDOW_TITLE)
        self.fullscreen = False
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.SCALED | pygame.RESIZABLE)
        self.clock = pygame.time.Clock()

        # One seeded RNG drives everything, so --seed reproduces whole runs.
        self.rng = random.Random(seed)

        self.atlas = SpriteAtlas(ASSETS_DIR, force_save=regen_assets)
        try:
            pygame.display.set_icon(pygame.transform.scale(self.atlas.base["ghost"], (32, 32)))
        except pygame.error:
            pass
        if regen_assets:
            from sfx.synth import generate_all
            generate_all(AUDIO_DIR, force=True)
        self.sound = SoundManager(AUDIO_DIR, muted=mute)
        self.highscores = HighScoreTable(DATABASE_FILE, legacy_json=HIGHSCORE_FILE)
        # Nobody is selected at launch (a remembered player is ignored). The hunter is chosen
        # either from "Hunter Profile" or by the new/current prompt shown after Play.
        # profile_chosen stays True for the rest of this launch once a hunter is selected.
        self.active_player_name = ""
        self.active_player_id = "P-1"
        self.profile_chosen = False
        self.atmosphere = Atmosphere()
        self.menu_background = self._build_menu_background()

        # Match settings chosen on the mode / first-player screens.
        self.game_mode = MODE_SOLO
        self.ai_first = False

        from .screens import (DifficultyScreen, FirstScreen, GuideScreen, MenuScreen,
                              ModeScreen, ScoresScreen, PlayerSelectScreen)
        from .game_screen import GameScreen
        self.screens: dict[str, Screen] = {
            "menu": MenuScreen(self),
            "players": PlayerSelectScreen(self),
            "mode": ModeScreen(self),
            "first": FirstScreen(self),
            "difficulty": DifficultyScreen(self),
            "guide": GuideScreen(self),
            "scores": ScoresScreen(self),
            "game": GameScreen(self),
        }
        self.current_name = "menu"
        self.current = self.screens["menu"]
        self.current.enter()
        self.running = True
        self.time = 0.0

    def _build_menu_background(self) -> pygame.Surface:
        tile = 48
        bg = pygame.Surface((SCREEN_W, SCREEN_H))
        for r in range(SCREEN_H // tile + 1):
            for c in range(SCREEN_W // tile + 1):
                bg.blit(self.atlas.tile("wall", (r, c), tile), (c * tile, r * tile))
        shade = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        shade.fill((6, 7, 12, 145))
        bg.blit(shade, (0, 0))
        from .sprites import radial_gradient
        amber_glow = radial_gradient(520, (210, 130, 50), 95, falloff=1.6)
        teal_glow = radial_gradient(520, (50, 180, 175), 85, falloff=1.6)
        bg.blit(amber_glow, (-180, SCREEN_H // 2 - 520), special_flags=pygame.BLEND_RGB_ADD)
        bg.blit(teal_glow, (SCREEN_W - 860, SCREEN_H // 2 - 520), special_flags=pygame.BLEND_RGB_ADD)
        return bg.convert()

    def toggle_fullscreen(self) -> None:
        self.fullscreen = not self.fullscreen
        flags = pygame.SCALED | pygame.RESIZABLE | (pygame.FULLSCREEN if self.fullscreen else 0)
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), flags)

    def go(self, name: str, **kwargs) -> None:
        self.current.leave()
        self.current_name = name
        self.current = self.screens[name]
        self.current.enter(**kwargs)

    def draw_menu_backdrop(self, surface: pygame.Surface) -> None:
        surface.blit(self.menu_background, (0, 0))
        self.atmosphere.draw_fog(surface)
        self.atmosphere.draw_motes(surface)
        self.atmosphere.draw_vignette(surface)

    def run(self) -> None:
        self.sound.start_drone()
        while self.running:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.1)  # clamp hitches (e.g. window drag)
            self.time += dt
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                    self.toggle_fullscreen()
                else:
                    self.current.handle_event(event)
            self.atmosphere.update(dt)
            self.current.update(dt)
            self.current.draw(self.screen)
            self.atmosphere.draw_vignette(self.screen)
            pygame.display.flip()
        pygame.quit()
