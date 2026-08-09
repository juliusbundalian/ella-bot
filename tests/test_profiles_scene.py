from __future__ import annotations

from unittest.mock import MagicMock

import pygame

from ella_bot.services.profile_store import Profile, ProfileValidationError
from ella_bot.services.session_checkpoint import SavedSessionSummary
from ella_bot.ui.pygame_gui.components.on_screen_keyboard import KeyboardAction
from ella_bot.ui.pygame_gui.scenes.profiles import ProfilesScene, _summary_text


def _scene():
    pygame.font.init()
    app = MagicMock()
    app.screen = pygame.Surface((1280, 720))
    app.font_title = pygame.font.SysFont(None, 64)
    app.font_body = pygame.font.SysFont(None, 30)
    app.font_small = pygame.font.SysFont(None, 22)
    app.font_button = pygame.font.SysFont(None, 42)
    app.profiles.return_value = ()
    app.active_profile.return_value = None
    app.profile_session_summary.return_value = None
    return ProfilesScene(app)


def _profile(index: int, name: str | None = None) -> Profile:
    return Profile(
        f'{index:032x}',
        name or f'Reader {index}',
        '2026-07-28T12:00:00+08:00',
    )


def _tap_keyboard_key(scene, key_id):
    scene.render()
    point = scene.keyboard.key_rects[key_id].center
    scene.handle_event(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=point)
    )
    scene.handle_event(
        pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=point)
    )


def test_profile_container_matches_options_container_geometry():
    from ella_bot.ui.pygame_gui.scenes.profiles import (
        _PROFILE_CONTAINER_RADIUS,
    )

    scene = _scene()
    rect = scene._get_container_rect(1280, 720)

    assert rect == pygame.Rect(280, 32, 720, 656)
    assert rect.centerx == 640
    assert _PROFILE_CONTAINER_RADIUS == 140


def test_profile_pages_contain_two_profiles():
    scene = _scene()
    profiles = tuple(_profile(index) for index in range(5))

    assert scene._page_count(len(profiles)) == 3
    scene.carousel_page = 1
    assert scene._visible_profiles(profiles) == profiles[2:4]


def test_on_enter_opens_page_containing_active_profile():
    scene = _scene()
    scene._lottie_bg = False
    profiles = tuple(_profile(index) for index in range(5))
    scene.app.profiles.return_value = profiles
    scene.app.active_profile.return_value = profiles[3]

    scene.on_enter()

    assert scene.carousel_page == 1


def test_carousel_renders_only_two_profiles_and_three_indicators():
    scene = _scene()
    profiles = tuple(_profile(index) for index in range(5))
    scene.app.profiles.return_value = profiles

    scene.render()

    assert tuple(scene.profile_cards) == (profiles[0].id, profiles[1].id)
    assert scene.carousel_previous_button is None
    assert scene.carousel_next_button is not None
    assert len(scene.page_indicator_rects) == 3
    assert scene.page_indicator_states == [True, False, False]
    assert scene.carousel_page == 0


def test_carousel_arrow_moves_page_and_disables_at_last_page():
    scene = _scene()
    profiles = tuple(_profile(index) for index in range(5))
    scene.app.profiles.return_value = profiles
    scene.render()

    next_point = scene.carousel_next_button.center
    scene.handle_event(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=next_point)
    )
    scene.handle_event(
        pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=next_point)
    )
    scene.render()

    assert scene.carousel_page == 1
    assert tuple(scene.profile_cards) == (profiles[2].id, profiles[3].id)

    next_point = scene.carousel_next_button.center
    scene.handle_event(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=next_point)
    )
    scene.handle_event(
        pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=next_point)
    )
    scene.render()

    assert scene.carousel_page == 2
    assert tuple(scene.profile_cards) == (profiles[4].id,)
    assert scene.carousel_previous_button is not None
    assert scene.carousel_next_button is None

    disabled_next_point = (952, 286)
    scene.handle_event(
        pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=1,
            pos=disabled_next_point,
        )
    )
    scene.handle_event(
        pygame.event.Event(
            pygame.MOUSEBUTTONUP,
            button=1,
            pos=disabled_next_point,
        )
    )
    assert scene.carousel_page == 2

    previous_point = scene.carousel_previous_button.center
    for expected_page in (1, 0):
        scene.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=previous_point)
        )
        scene.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=previous_point)
        )
        scene.render()
        assert scene.carousel_page == expected_page
        previous_point = scene.carousel_previous_button.center if expected_page else None

    disabled_previous_point = (328, 286)
    scene.handle_event(
        pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=1,
            pos=disabled_previous_point,
        )
    )
    scene.handle_event(
        pygame.event.Event(
            pygame.MOUSEBUTTONUP,
            button=1,
            pos=disabled_previous_point,
        )
    )
    assert scene.carousel_page == 0


def test_back_and_create_are_fixed_equal_actions_outside_carousel():
    scene = _scene()
    scene.app.profiles.return_value = tuple(_profile(index) for index in range(3))

    scene.render()

    assert scene.create_button is not None
    assert scene.back_button is not None
    assert scene.create_button.size == scene.back_button.size
    assert scene.back_button.left < scene.create_button.left
    assert not any(
        rect.colliderect(scene.create_button)
        for rect in scene._profile_card_rects.values()
    )


def test_profile_actions_use_requested_color_variants(monkeypatch):
    import ella_bot.ui.pygame_gui.scenes.profiles as profiles_module

    rendered_buttons = []

    class RecordingButton:
        def __init__(self, rect, *, label, variant="yellow", **kwargs):
            self.label = label
            self.variant = variant
            self.is_pressed = False

        def draw(self, screen):
            rendered_buttons.append((self.label, self.variant))

    monkeypatch.setattr(profiles_module, "Button", RecordingButton)
    scene = _scene()

    scene.render()
    assert ("+ Create Profile", "yellow") in rendered_buttons
    assert ("Back to Menu", "violet") in rendered_buttons

    rendered_buttons.clear()
    scene._open_create()
    scene.render()
    assert ("Create", "yellow") in rendered_buttons
    assert ("Cancel", "violet") in rendered_buttons

    rendered_buttons.clear()
    scene.modal = "delete"
    scene.target_profile_name = "Leo"
    scene.render()
    assert ("Cancel", "violet") in rendered_buttons


def test_empty_profiles_show_empty_state_without_indicators():
    scene = _scene()

    scene.render()

    assert scene.empty_state_rect is not None
    assert scene.page_indicator_rects == []
    assert scene.carousel_previous_button is None
    assert scene.carousel_next_button is None
    assert scene.create_button is not None


def test_profiles_page_uses_exact_title_copy():
    scene = _scene()
    profile = _profile(1)
    scene.app.profiles.return_value = (profile,)
    real_title_font = scene.app.font_title
    scene.app.font_title = MagicMock()
    scene.app.font_title.render.side_effect = real_title_font.render

    scene.render()

    title_labels = [
        call.args[0] for call in scene.app.font_title.render.call_args_list
    ]
    assert 'Who\'s Learning?' in title_labels
    assert 'Choose a Profile' not in title_labels


def test_close_modal_stops_text_input(monkeypatch):
    scene = _scene()
    stop_text_input = MagicMock()
    monkeypatch.setattr(pygame.key, 'stop_text_input', stop_text_input)
    scene.modal = 'create'

    scene._close_modal()

    stop_text_input.assert_called_once_with()


def test_on_exit_stops_text_input(monkeypatch):
    scene = _scene()
    stop_text_input = MagicMock()
    monkeypatch.setattr(pygame.key, 'stop_text_input', stop_text_input)

    scene.on_exit()

    stop_text_input.assert_called_once_with()


def test_clicking_profile_selects_and_returns_to_menu():
    scene = _scene()
    profile = Profile('a' * 32, 'Maria', '2026-07-28T12:00:00+08:00')
    scene.app.profiles.return_value = (profile,)

    scene._select_profile(profile.id)

    scene.app.select_profile.assert_called_once_with(profile.id)
    scene.app.switch_scene.assert_called_once_with('main_menu')


def test_successful_creation_selects_and_opens_level_selection():
    scene = _scene()
    created = Profile('b' * 32, 'Leo', '2026-07-28T12:00:00+08:00')
    scene.app.create_profile.return_value = created
    scene.name_input = ' Leo '

    scene._save_name()

    scene.app.create_profile.assert_called_once_with(' Leo ')
    scene.app.switch_scene.assert_called_once_with('level_selection')


def test_rendering_five_profiles_hides_create_button():
    scene = _scene()
    scene.app.profiles.return_value = tuple(_profile(index) for index in range(5))

    scene.render()

    assert scene.create_button is None
    assert scene.capacity_status_rect is not None
    assert len(scene.profile_cards) == 2


def test_selection_error_is_rendered_at_five_profile_capacity():
    scene = _scene()
    profiles = tuple(_profile(index) for index in range(5))
    scene.app.profiles.return_value = profiles
    scene.app.select_profile.side_effect = OSError('Profile write failed')
    real_font = scene.app.font_small
    scene.app.font_small = MagicMock()
    scene.app.font_small.render.side_effect = real_font.render

    scene._select_profile(profiles[0].id)
    scene.render()

    rendered_labels = [
        call.args[0] for call in scene.app.font_small.render.call_args_list
    ]
    assert 'Profile write failed' in rendered_labels
    scene.app.switch_scene.assert_not_called()


def test_create_modal_accepts_text_input_and_backspace():
    scene = _scene()
    scene._open_create()

    scene.handle_event(pygame.event.Event(pygame.TEXTINPUT, text='Leo'))
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_BACKSPACE))

    assert scene.name_input == 'Le'


def test_text_input_rejects_candidate_longer_than_twenty_characters():
    scene = _scene()
    scene._open_create()
    scene.name_input = 'a' * 20

    scene.handle_event(pygame.event.Event(pygame.TEXTINPUT, text='b'))

    assert scene.name_input == 'a' * 20


def test_service_validation_error_keeps_creation_modal_open():
    scene = _scene()
    scene.modal = 'create'
    scene.name_input = 'Leo'
    scene.app.create_profile.side_effect = ProfileValidationError('Name is taken')

    scene._save_name()

    assert scene.modal == 'create'
    assert scene.error_message == 'Name is taken'
    scene.app.switch_scene.assert_not_called()


def test_back_returns_to_menu_without_selecting_profile():
    scene = _scene()

    scene._go_back()

    scene.app.switch_scene.assert_called_once_with('main_menu')
    scene.app.select_profile.assert_not_called()


def test_summary_text_describes_progress_and_results():
    reading = SavedSessionSummary(
        '2c', 4, '2026-07-24T10:00:00+08:00', 'reading'
    )
    results = SavedSessionSummary(
        '1a', 5, '2026-07-24T10:00:00+08:00', 'results'
    )

    assert _summary_text(None) == 'Ready to begin'
    assert _summary_text(reading) == 'Level 2C - Item 4'
    assert _summary_text(results) == 'Level 1A - Results'


def test_profile_selection_hitbox_reserves_lower_management_strip():
    scene = _scene()
    profile = _profile(1)
    scene.app.profiles.return_value = (profile,)

    scene.render()

    card = scene.profile_cards[profile.id]
    assert card.bottom <= scene._profile_card_rects[profile.id].bottom - 48


def test_rename_prefills_and_saves_without_selecting():
    scene = _scene()
    profile = Profile('a' * 32, 'Old', '2026-07-28T12:00:00+08:00')
    scene._open_rename(profile)
    assert scene.name_input == 'Old'
    scene.name_input = 'New'

    scene._save_name()

    scene.app.rename_profile.assert_called_once_with(profile.id, 'New')
    scene.app.select_profile.assert_not_called()
    scene.app.switch_scene.assert_not_called()


def test_reset_targets_only_named_profile():
    scene = _scene()
    profile = Profile('a' * 32, 'Maria', '2026-07-28T12:00:00+08:00')
    scene._open_confirmation('reset', profile)

    scene._confirm_management()

    scene.app.reset_profile_progress.assert_called_once_with(profile.id)


def test_delete_active_profile_returns_to_generic_main_menu():
    scene = _scene()
    profile = Profile('a' * 32, 'Maria', '2026-07-28T12:00:00+08:00')
    scene.app.active_profile.return_value = profile
    scene._open_confirmation('delete', profile)

    scene._confirm_management()

    scene.app.delete_profile.assert_called_once_with(profile.id)
    scene.app.switch_scene.assert_called_once_with('main_menu')


def test_active_delete_cleanup_failure_warns_before_returning_to_main_menu():
    scene = _scene()
    profile = Profile('a' * 32, 'Maria', '2026-07-28T12:00:00+08:00')
    scene.app.active_profile.return_value = profile
    scene.app.delete_profile.return_value = False
    real_font = scene.app.font_small
    scene.app.font_small = MagicMock()
    scene.app.font_small.render.side_effect = real_font.render
    scene._open_confirmation('delete', profile)

    scene._confirm_management()

    scene.app.switch_scene.assert_not_called()
    scene.render()
    rendered_labels = [
        call.args[0] for call in scene.app.font_small.render.call_args_list
    ]
    assert 'Some old profile files could not be removed.' in rendered_labels
    acknowledge_button = scene._modal_save_button
    assert acknowledge_button is not None

    scene.handle_event(
        pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=1,
            pos=acknowledge_button.center,
        )
    )
    scene.handle_event(
        pygame.event.Event(
            pygame.MOUSEBUTTONUP,
            button=1,
            pos=acknowledge_button.center,
        )
    )

    scene.app.switch_scene.assert_called_once_with('main_menu')


def test_rename_hitbox_intercepts_profile_selection():
    scene = _scene()
    profile = _profile(1)
    scene.app.profiles.return_value = (profile,)
    scene.render()
    rename_button = scene.manage_buttons[('rename', profile.id)]

    scene.handle_event(
        pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=1,
            pos=rename_button.center,
        )
    )
    scene.handle_event(
        pygame.event.Event(
            pygame.MOUSEBUTTONUP,
            button=1,
            pos=rename_button.center,
        )
    )

    assert scene.modal == 'rename'
    scene.app.select_profile.assert_not_called()


def test_rename_error_keeps_modal_open_with_message():
    scene = _scene()
    profile = _profile(1)
    scene._open_rename(profile)
    scene.name_input = 'New'
    scene.app.rename_profile.side_effect = OSError('full')

    scene._save_name()

    assert scene.modal == 'rename'
    assert scene.error_message == 'full'


def test_reset_cleanup_failure_displays_warning():
    scene = _scene()
    profile = _profile(1)
    scene.app.reset_profile_progress.return_value = False
    scene._open_confirmation('reset', profile)

    scene._confirm_management()

    assert scene.error_message == 'Some old profile files could not be removed.'


def test_delete_inactive_profile_stays_on_profiles_page():
    scene = _scene()
    active = _profile(1)
    target = _profile(2)
    scene.app.active_profile.return_value = active
    scene._open_confirmation('delete', target)

    scene._confirm_management()

    scene.app.delete_profile.assert_called_once_with(target.id)
    scene.app.switch_scene.assert_not_called()


def test_confirmation_modals_render_exact_targeted_warning():
    scene = _scene()
    profile = Profile('a' * 32, 'Maria', '2026-07-28T12:00:00+08:00')
    real_font = scene.app.font_small
    scene.app.font_small = MagicMock()
    scene.app.font_small.render.side_effect = real_font.render

    scene._open_confirmation('reset', profile)
    scene.render()
    scene._open_confirmation('delete', profile)
    scene.render()

    rendered_labels = [
        call.args[0] for call in scene.app.font_small.render.call_args_list
    ]
    assert 'Erase all learning progress for Maria? The profile will remain.' in rendered_labels
    assert 'Delete Maria and all saved progress? This cannot be undone.' in rendered_labels


def test_create_modal_accepts_touchscreen_keyboard_input():
    scene = _scene()
    scene._open_create()

    _tap_keyboard_key(scene, "shift")
    _tap_keyboard_key(scene, "l")
    _tap_keyboard_key(scene, "e")
    _tap_keyboard_key(scene, "o")

    assert scene.name_input == "Leo"


def test_rename_modal_accepts_space_and_backspace_from_touchscreen():
    scene = _scene()
    profile = _profile(1, "Ana")
    scene._open_rename(profile)

    _tap_keyboard_key(scene, "space")
    _tap_keyboard_key(scene, "m")
    _tap_keyboard_key(scene, "backspace")

    assert scene.name_input == "Ana "


def test_touchscreen_input_respects_twenty_character_limit():
    scene = _scene()
    scene._open_create()
    scene.name_input = "a" * 20

    _tap_keyboard_key(scene, "b")

    assert scene.name_input == "a" * 20


def test_keyboard_action_clears_stale_validation_error():
    scene = _scene()
    scene._open_create()
    scene.error_message = "Name is taken"

    scene._apply_keyboard_action(KeyboardAction("text", "a"))

    assert scene.name_input == "a"
    assert scene.error_message == ""


def test_opening_name_modal_resets_keyboard_case():
    scene = _scene()
    scene._open_create()
    scene.keyboard.uppercase = True

    scene._close_modal()
    scene._open_create()

    assert scene.keyboard.uppercase is False


def test_closing_modal_cancels_pressed_keyboard_key():
    scene = _scene()
    scene._open_create()
    scene.render()
    point = scene.keyboard.key_rects["q"].center
    scene.keyboard.handle_mouse_down(point)

    scene._close_modal()

    assert scene.keyboard.handle_mouse_up(point) is None


def test_visible_profile_cards_and_actions_use_consistent_geometry():
    scene = _scene()
    profiles = (_profile(1, "Maria"), _profile(2, "Leo"))
    scene.app.profiles.return_value = profiles

    scene.render()

    first_card = scene._profile_card_rects[profiles[0].id]
    second_card = scene._profile_card_rects[profiles[1].id]
    assert first_card.size == second_card.size

    rename = scene.manage_buttons[("rename", profiles[0].id)]
    reset = scene.manage_buttons[("reset", profiles[0].id)]
    delete = scene.manage_buttons[("delete", profiles[0].id)]
    assert rename.height == reset.height == delete.height == 40
    assert reset.size == delete.size
    assert rename.top < reset.top
    assert rename.width == reset.width + 8 + delete.width


def test_profile_selection_hitbox_stops_above_management_actions():
    scene = _scene()
    profile = _profile(1)
    scene.app.profiles.return_value = (profile,)

    scene.render()

    selection = scene.profile_cards[profile.id]
    rename = scene.manage_buttons[("rename", profile.id)]
    assert selection.bottom <= rename.top - 8


def test_management_labels_use_short_consistent_copy():
    scene = _scene()
    profile = _profile(1)
    scene.app.profiles.return_value = (profile,)
    real_font = pygame.font.SysFont(None, 16)
    tracking_font = MagicMock()
    tracking_font.render.side_effect = real_font.render
    scene._get_adaptive_font = MagicMock(return_value=tracking_font)

    scene.render()

    rendered_labels = [call.args[0] for call in tracking_font.render.call_args_list]
    assert "Rename" in rendered_labels
    assert "Reset" in rendered_labels
    assert "Delete" in rendered_labels
    assert "Reset Progress" not in rendered_labels


def test_delete_clamps_carousel_to_new_last_page():
    scene = _scene()
    profiles = tuple(_profile(index) for index in range(5))
    scene.app.profiles.return_value = profiles[:4]
    scene.carousel_page = 2
    scene._open_confirmation("delete", profiles[4])

    scene._confirm_management()

    assert scene.carousel_page == 1


def test_rename_and_reset_keep_current_carousel_page():
    scene = _scene()
    profiles = tuple(_profile(index) for index in range(4))
    scene.app.profiles.return_value = profiles
    scene.carousel_page = 1

    scene._open_rename(profiles[2])
    scene.name_input = "Renamed"
    scene._save_name()
    assert scene.carousel_page == 1

    scene._open_confirmation("reset", profiles[2])
    scene._confirm_management()
    assert scene.carousel_page == 1


def test_leaving_scene_cancels_pressed_keyboard_key(monkeypatch):
    scene = _scene()
    scene._open_create()
    scene.render()
    point = scene.keyboard.key_rects["q"].center
    scene.keyboard.handle_mouse_down(point)
    monkeypatch.setattr(pygame.key, "stop_text_input", lambda: None)

    scene.on_exit()

    assert scene.keyboard.handle_mouse_up(point) is None


def test_name_modal_keyboard_and_actions_fit_inside_screen():
    scene = _scene()
    scene._open_create()

    scene.render()

    screen_rect = scene.app.screen.get_rect()
    assert all(screen_rect.contains(rect) for rect in scene.keyboard.key_rects.values())
    assert screen_rect.contains(scene._modal_save_button)
    assert screen_rect.contains(scene._modal_cancel_button)


def test_name_modal_matches_options_container_and_cancel_is_left():
    from ella_bot.ui.pygame_gui.scenes.settings import SettingsScene

    scene = _scene()
    scene._open_create()

    scene.render()

    width, height = scene.app.screen.get_size()
    assert scene._name_modal_rect == SettingsScene._get_card_rect(width, height)
    assert scene._modal_cancel_button.left < scene._modal_save_button.left


def test_physical_text_input_still_works_with_embedded_keyboard():
    scene = _scene()
    scene._open_create()

    scene.handle_event(pygame.event.Event(pygame.TEXTINPUT, text="Mia"))

    assert scene.name_input == "Mia"


def test_long_profile_name_scales_adaptively_to_fit():
    scene = _scene()
    profile = _profile(1, "A" * 20)
    scene.app.profiles.return_value = (profile,)

    # Should render cleanly without raising an error
    scene.render()
    assert profile.id in scene.profile_cards


def test_button_auto_scales_overflowing_label():
    from ella_bot.ui.pygame_gui.components.button import Button
    font = pygame.font.SysFont(None, 40)
    rect = pygame.Rect(0, 0, 80, 30)
    btn = Button(rect, label="Extremely Long Button Text", font=font)
    surface = pygame.Surface((100, 100))

    # Should draw scaled text without raising an error
    btn.draw(surface)
