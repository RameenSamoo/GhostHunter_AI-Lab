"""Headless tests of the hunter-selection flow and the per-difficulty AI speed."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from config import DIFFICULTIES


@pytest.fixture()
def app(tmp_path):
    import ui.app as app_module
    original = (app_module.DATABASE_FILE, app_module.HIGHSCORE_FILE)
    app_module.DATABASE_FILE, app_module.HIGHSCORE_FILE = tmp_path / "test.db", tmp_path / "none.json"
    a = app_module.App(seed=3, mute=True)
    yield a
    app_module.DATABASE_FILE, app_module.HIGHSCORE_FILE = original
    pygame.quit()


def key(app, k):
    app.current.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode=""))


def text(app, s):
    for ch in s:                                   # the OS delivers one character per keystroke
        app.current.handle_event(pygame.event.Event(pygame.TEXTINPUT, text=ch))


def click_button(app, button):
    app.current.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=button.rect.center))


def create_player(app, name):
    """On the player screen: Down, Enter (Create New Player), type, Enter."""
    key(app, pygame.K_DOWN)
    key(app, pygame.K_RETURN)
    text(app, name)
    key(app, pygame.K_RETURN)


def test_launch_opens_main_menu_with_nobody_selected(app):
    assert app.current_name == "menu"
    assert app.active_player_name == ""
    assert app.profile_chosen is False


def test_remembered_player_is_ignored_at_launch(tmp_path):
    import ui.app as app_module
    from core.database import HighScoreTable
    path = tmp_path / "test.db"
    table = HighScoreTable(path)
    table.get_or_create_player("Ali")
    table.close()
    original = (app_module.DATABASE_FILE, app_module.HIGHSCORE_FILE)
    app_module.DATABASE_FILE, app_module.HIGHSCORE_FILE = path, tmp_path / "none.json"
    try:
        a = app_module.App(seed=1, mute=True)
        assert a.highscores.last_player_id == "P-1"     # remembered in the database...
        assert a.current_name == "menu" and a.active_player_name == "" and not a.profile_chosen   # ...but not used
    finally:
        app_module.DATABASE_FILE, app_module.HIGHSCORE_FILE = original
        pygame.quit()


def test_play_asks_new_or_current_then_continues_to_mode(app):
    app.current._play()
    assert app.current_name == "players"
    assert app.current.mode == "menu"             # the new/current choice is shown, even with no players yet
    create_player(app, "Ali")
    assert app.current_name == "mode"             # continues to Play, not back to the menu
    assert app.active_player_name == "Ali" and app.profile_chosen


def test_hunter_profile_choice_skips_the_prompt_after_play(app):
    app.go("players")                              # the Hunter Profile button
    create_player(app, "Sara")
    assert app.current_name == "menu" and app.profile_chosen
    app.current._play()
    assert app.current_name == "mode"             # no new/current prompt


def test_prompt_is_skipped_for_the_rest_of_the_launch(app):
    app.current._play()
    create_player(app, "Ali")
    app.go("menu")
    app.current._play()
    assert app.current_name == "mode"


def test_escape_from_play_prompt_returns_to_menu_and_asks_again_next_time(app):
    app.current._play()
    key(app, pygame.K_ESCAPE)
    assert app.current_name == "menu" and not app.profile_chosen
    app.current._play()
    assert app.current_name == "players"


def test_login_existing_player_by_keyboard(app):
    app.highscores.get_or_create_player("Zed")     # becomes P-1
    app.current._play()
    key(app, pygame.K_DOWN); key(app, pygame.K_DOWN)   # Create -> Login
    key(app, pygame.K_RETURN)
    text(app, "P-1"); key(app, pygame.K_RETURN)
    text(app, "zed"); key(app, pygame.K_RETURN)
    assert app.current_name == "mode" and app.active_player_name == "Zed" and app.profile_chosen


def test_arrow_keys_move_focus_and_wrap(app):
    app.go("players")
    s = app.current
    assert not s.btn_new.focused and not s.btn_login.focused
    key(app, pygame.K_DOWN);  assert s.btn_new.focused
    key(app, pygame.K_DOWN);  assert s.btn_login.focused
    key(app, pygame.K_DOWN);  assert s.btn_new.focused      # wraps
    key(app, pygame.K_UP);    assert s.btn_login.focused    # wraps back


def test_mouse_still_works_on_player_screen(app):
    app.current._play()
    click_button(app, app.current.btn_new)
    assert app.current.mode == "new"


def test_ai_speeds_per_difficulty():
    speeds = {d.key: d.ai_speed for d in DIFFICULTIES}
    assert speeds == {"beginner": 5.0, "intermediate": 5.33, "professional": 5.66, "expert": 6.0}
    from config import MOVE_REPEAT_RATE
    assert max(speeds.values()) <= MOVE_REPEAT_RATE        # never faster than a human holding a key
