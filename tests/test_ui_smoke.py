"""Headless smoke test of the real UI: every screen draws, a full hunt can be
completed, and hotkeys stay dead while a name is being typed."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

import config


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    # One App per module: pygame is initialised once, exactly like the real game
    # (re-initialising while fonts are cached is not supported by SDL).
    import ui.app as app_module
    original = (app_module.DATABASE_FILE, app_module.HIGHSCORE_FILE)
    scores = tmp_path_factory.mktemp("scores")
    app_module.DATABASE_FILE, app_module.HIGHSCORE_FILE = scores / "test.db", scores / "none.json"
    a = app_module.App(seed=5, mute=True)
    yield a
    app_module.DATABASE_FILE, app_module.HIGHSCORE_FILE = original
    pygame.quit()


def frames(app, n, dt=1 / 60):
    for _ in range(n):
        app.atmosphere.update(dt)
        app.current.update(dt)
        app.current.draw(app.screen)


def key(app, k, up=False):
    app.current.handle_event(pygame.event.Event(pygame.KEYUP if up else pygame.KEYDOWN, key=k, mod=0, unicode=""))


def test_every_menu_screen_draws(app):
    for name in ("menu", "difficulty", "guide", "scores"):
        app.go(name)
        frames(app, 3)


def test_pause_freezes_the_simulation(app):
    app.go("game", difficulty=config.DIFFICULTIES[0])
    game = app.current
    frames(app, 30)
    key(app, pygame.K_p)
    before = (game.session.elapsed, game.session.env.ghost, game.session.radar_cooldown)
    frames(app, 120)
    assert (game.session.elapsed, game.session.env.ghost, game.session.radar_cooldown) == before
    key(app, pygame.K_p)
    frames(app, 10)
    assert game.session.elapsed > before[0]


def test_full_hunt_and_name_entry_ignores_hotkeys(app):
    from ui.game_screen import Mode

    app.go("game", difficulty=config.DIFFICULTIES[1])
    game = app.current
    s = game.session

    # Put the hunter next to the ghost and step onto it.
    gr, gc = s.env.ghost
    for dr, dc, k in ((0, -1, pygame.K_RIGHT), (0, 1, pygame.K_LEFT), (-1, 0, pygame.K_DOWN), (1, 0, pygame.K_UP)):
        if s.grid.is_walkable((gr + dr, gc + dc)):
            s.env.hunter = (gr + dr, gc + dc)
            s.ghost_timer = -999
            key(app, k)
            frames(app, 1)
            break
    assert s.caught
    frames(app, 90)
    assert game.mode == Mode.NAME_ENTRY

    for ch in "Ab r p h":
        game.handle_event(pygame.event.Event(pygame.TEXTINPUT, text=ch))
    for k in (pygame.K_SPACE, pygame.K_r, pygame.K_p, pygame.K_h):
        key(app, k)
    assert game.mode == Mode.NAME_ENTRY
    assert game.session is s                      # R did not restart
    assert s.radar_uses == 0 and s.hint_uses == 0  # Space/H did nothing
    assert game.name_text == "Ab r p h"

    key(app, pygame.K_RETURN)
    frames(app, 2)
    assert game.mode == Mode.VICTORY and game.saved_rank == 1
    assert app.highscores.entries("intermediate")[0].name == "Ab r p h"


def test_restart_key_regenerates_level(app):
    app.go("game", difficulty=config.DIFFICULTIES[0])
    first = app.current.session
    key(app, pygame.K_r)
    assert app.current.session is not first


# ------------------------------------------------------------------ VS modes
def test_mode_and_first_player_screens_set_match_settings(app):
    app.go("mode")
    key(app, pygame.K_3)                               # turn-based
    assert app.game_mode == config.MODE_TURNS and app.current_name == "first"
    key(app, pygame.K_2)                               # Sir Nadeem first
    assert app.ai_first is True and app.current_name == "difficulty"
    key(app, pygame.K_1)
    game = app.current
    assert app.current_name == "game" and game.match is not None and game.match.current == "ai"
    app.go("mode")
    key(app, pygame.K_2)                               # simultaneous goes straight to difficulty
    assert app.game_mode == config.MODE_SIMULTANEOUS and app.current_name == "difficulty"


def test_turn_banner_freezes_clock_and_ai_turn_ignores_player_keys(app):
    from ui.game_screen import Mode
    app.game_mode, app.ai_first = config.MODE_TURNS, True
    app.go("game", difficulty=config.DIFFICULTIES[0])
    game = app.current
    assert game.mode == Mode.BANNER
    frames(app, 60)                                    # 1 s of banner
    assert game.session.elapsed == 0.0                 # turn clock hasn't started
    frames(app, 120)
    assert game.mode == Mode.PLAYING and game.ai_turn
    for k in (pygame.K_SPACE, pygame.K_h, pygame.K_LEFT, pygame.K_RIGHT):
        key(app, k)
    s = game.session
    assert s.primary.radar_uses == 0 and s.primary.hint_uses == 0
    assert not s.can_use_radar and not s.can_use_hint


def test_restart_and_quit_save_nothing(app):
    from ui.game_screen import Mode
    before = {m: {d.key: len(app.highscores.entries(d.key, m)) for d in config.DIFFICULTIES}
              for m in config.MODES}
    app.game_mode = config.MODE_SIMULTANEOUS
    app.go("game", difficulty=config.DIFFICULTIES[0])
    game = app.current
    s = game.session
    while not s.hunters[1].caught and s.elapsed < 60:  # Sir Nadeem catches first
        frames(app, 1)
    assert s.hunters[1].caught and game.ai_message_timer > 0
    key(app, pygame.K_r)                               # restart: new game, nothing saved
    assert game.session is not s
    key(app, pygame.K_p)
    assert game.mode == Mode.PAUSED
    game._quit_to_menu()
    after = {m: {d.key: len(app.highscores.entries(d.key, m)) for d in config.DIFFICULTIES}
             for m in config.MODES}
    assert before == after


def test_r_during_ai_turn_restarts_whole_match(app):
    app.game_mode, app.ai_first = config.MODE_TURNS, True
    app.go("game", difficulty=config.DIFFICULTIES[0])
    game = app.current
    frames(app, 200)
    first = game.match
    key(app, pygame.K_r)
    assert game.match is not first and game.match.turn == 0
