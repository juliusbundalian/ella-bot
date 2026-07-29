from unittest.mock import MagicMock

import pygame

from ella_bot.core.constants import LEVEL_ORDER
from ella_bot.ui.pygame_gui.scenes.level_selection import LevelSelectionScene


def _scene():
    pygame.font.init()
    app = MagicMock()
    app.screen = pygame.Surface((1280, 720))
    app.font_title = pygame.font.SysFont(None, 64)
    app.font_body = pygame.font.SysFont(None, 30)
    app.font_small = pygame.font.SysFont(None, 22)
    app.font_button = pygame.font.SysFont(None, 42)
    return LevelSelectionScene(app)


def test_render_exposes_every_level_as_enabled_button():
    scene = _scene()
    scene.render()
    assert list(scene.level_buttons) == LEVEL_ORDER
    assert all(rect.width > 0 and rect.height > 0 for rect in scene.level_buttons.values())


def test_selecting_level_opens_confirmation_without_replacing_checkpoint():
    scene = _scene()
    scene._select_level("2c")
    assert scene.pending_level == "2c"
    assert scene.show_confirmation is True
    scene.app.start_new_session.assert_not_called()


def test_confirm_starts_selected_level_then_opens_prompt():
    scene = _scene()
    scene.pending_level = "2c"
    scene.show_confirmation = True
    scene.app.start_new_session.return_value = True

    scene._confirm_level()

    scene.app.start_new_session.assert_called_once_with("2c")
    scene.app.switch_scene.assert_called_once_with("reading_prompt")
    scene.app.active_scene._start_attempt.assert_called_once()


def test_failed_checkpoint_save_stays_on_confirmation():
    scene = _scene()
    scene.pending_level = "3"
    scene.show_confirmation = True
    scene.app.start_new_session.return_value = False

    scene._confirm_level()

    scene.app.switch_scene.assert_not_called()
    assert scene.show_confirmation is True


def test_cancel_and_back_preserve_saved_session():
    scene = _scene()
    scene.pending_level = "4"
    scene.show_confirmation = True
    scene._cancel_confirmation()
    scene._go_back()
    scene.app.clear_active_session.assert_not_called()
    scene.app.switch_scene.assert_called_once_with("main_menu")
