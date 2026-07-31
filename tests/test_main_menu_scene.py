from unittest.mock import MagicMock

import pygame
import pytest

from ella_bot.services.profile_store import Profile
from ella_bot.services.session_checkpoint import SavedSessionSummary
from ella_bot.ui.pygame_gui.scenes.main_menu import MainMenuScene


def _scene():
    pygame.font.init()
    app = MagicMock()
    app.screen = pygame.Surface((1280, 720))
    app.font_title = pygame.font.SysFont(None, 64)
    app.font_body = pygame.font.SysFont(None, 30)
    app.font_small = pygame.font.SysFont(None, 22)
    app.active_profile.return_value = Profile(
        'a' * 32,
        'Maria',
        '2026-07-28T12:00:00+08:00',
    )
    app.profiles.return_value = (app.active_profile.return_value,)
    return MainMenuScene(app)


def test_start_without_profiles_opens_create_profile_prompt():
    scene = _scene()
    scene.app.active_profile.return_value = None
    scene.app.profiles.return_value = ()

    scene._do_start()

    assert scene.show_profile_required_prompt is True
    assert scene.profile_required_message == 'Create a profile before starting.'
    scene.app.saved_session_summary.assert_not_called()


def test_start_without_selection_opens_choose_profile_prompt():
    scene = _scene()
    scene.app.active_profile.return_value = None
    scene.app.profiles.return_value = (
        Profile('a' * 32, 'Maria', '2026-07-28T12:00:00+08:00'),
    )

    scene._do_start()

    assert scene.show_profile_required_prompt is True
    assert scene.profile_required_message == 'Choose a profile before starting.'


def test_profiles_action_opens_profiles_scene():
    scene = _scene()

    scene._do_profiles()

    scene.app.switch_scene.assert_called_once_with('profiles')


@pytest.mark.parametrize(
    ('profile', 'expected_greeting'),
    [
        (None, 'Welcome!'),
        (
            Profile('a' * 32, 'Maria', '2026-07-28T12:00:00+08:00'),
            'Welcome, Maria!',
        ),
    ],
)
def test_render_shows_profile_greeting_and_safe_three_button_layout(
    profile,
    expected_greeting,
):
    scene = _scene()
    scene.app.active_profile.return_value = profile
    real_font = scene.app.font_body
    scene.app.font_body = MagicMock()
    scene.app.font_body.render.side_effect = real_font.render
    scene._title_img = pygame.Surface((2134, 878))
    scene._settings_icon = False

    scene.render()

    rendered_labels = [
        call.args[0] for call in scene.app.font_body.render.call_args_list
    ]
    assert expected_greeting in rendered_labels
    inner_rect = pygame.Rect(32, 32, 1216, 656)
    buttons = [
        scene.menu_start_button,
        scene.menu_profiles_button,
        scene.menu_exit_button,
    ]
    assert all(inner_rect.contains(button) for button in buttons)
    assert all(
        not first.colliderect(second)
        for index, first in enumerate(buttons)
        for second in buttons[index + 1:]
    )
    assert all(not button.colliderect(scene.menu_gear_button) for button in buttons)
    bot_left = inner_rect.right - 26 - int(inner_rect.width * 0.32)
    bot_region = pygame.Rect(
        bot_left,
        inner_rect.top,
        inner_rect.right - bot_left,
        inner_rect.height,
    )
    assert all(not button.colliderect(bot_region) for button in buttons)


def test_profile_required_open_action_takes_priority_over_other_modals():
    scene = _scene()
    shared = pygame.Rect(10, 10, 100, 40)
    scene.show_profile_required_prompt = True
    scene.show_resume_prompt = True
    scene.show_exit_confirm = True
    scene.profile_required_open_button = shared
    scene.resume_continue_button = shared
    scene.menu_confirm_yes_button = shared

    scene._handle_mouse_down(shared.center)
    scene._handle_mouse_up(shared.center)

    assert scene.show_profile_required_prompt is False
    scene.app.switch_scene.assert_called_once_with('profiles')


def test_profile_required_cancel_only_closes_prompt():
    scene = _scene()
    scene.show_profile_required_prompt = True
    scene.profile_required_cancel_button = pygame.Rect(10, 10, 100, 40)

    scene._handle_mouse_down(scene.profile_required_cancel_button.center)
    scene._handle_mouse_up(scene.profile_required_cancel_button.center)

    assert scene.show_profile_required_prompt is False
    scene.app.switch_scene.assert_not_called()


def test_profile_required_prompt_renders_message_and_actions():
    scene = _scene()
    scene.show_profile_required_prompt = True
    scene.profile_required_message = 'Create a profile before starting.'
    real_font = scene.app.font_body
    scene.app.font_body = MagicMock()
    scene.app.font_body.render.side_effect = real_font.render
    scene._title_img = False
    scene._settings_icon = False

    scene.render()

    rendered_labels = [
        call.args[0] for call in scene.app.font_body.render.call_args_list
    ]
    assert 'Create a profile before starting.' in rendered_labels
    assert scene.profile_required_open_button is not None
    assert scene.profile_required_cancel_button is not None


def test_start_without_checkpoint_opens_level_selection():
    scene = _scene()
    scene.app.saved_session_summary.return_value = None

    scene._do_start()

    scene.app.switch_scene.assert_called_once_with("level_selection")
    assert scene.show_resume_prompt is False


def test_start_with_checkpoint_opens_resume_prompt():
    scene = _scene()
    summary = SavedSessionSummary("2c", 4, "2026-07-24T10:00:00+08:00", "reading")
    scene.app.saved_session_summary.return_value = summary

    scene._do_start()

    assert scene.show_resume_prompt is True
    assert scene.resume_summary == summary
    scene.app.switch_scene.assert_not_called()


def test_continue_reading_checkpoint_starts_saved_attempt():
    scene = _scene()
    scene.app.continue_saved_session.return_value = "reading"

    scene._do_continue()

    scene.app.switch_scene.assert_called_once_with("reading_prompt")
    scene.app.active_scene._start_attempt.assert_called_once()


def test_continue_results_checkpoint_opens_results_without_attempt():
    scene = _scene()
    scene.app.continue_saved_session.return_value = "results"

    scene._do_continue()

    scene.app.switch_scene.assert_called_once_with("results")
    scene.app.active_scene._start_attempt.assert_not_called()


def test_new_session_choice_does_not_clear_checkpoint():
    scene = _scene()

    scene._do_new_session()

    scene.app.clear_active_session.assert_not_called()
    scene.app.switch_scene.assert_called_once_with("level_selection")


def test_entering_main_menu_does_not_reset_progress():
    scene = _scene()
    scene.on_enter()
    scene.app.session.reset_current_level.assert_not_called()


def test_welcome_speech_bubble_position_and_drawing():
    scene = _scene()
    inner_rect = pygame.Rect(32, 32, 1216, 656)
    bot_rect = pygame.Rect(900, 400, 200, 250)
    screen = scene.app.screen

    scene._draw_welcome_speech_bubble(screen, "Welcome, Maria!", bot_rect, inner_rect)

