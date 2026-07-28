from __future__ import annotations

from unittest.mock import MagicMock

import pygame

from ella_bot.services.profile_store import Profile, ProfileValidationError
from ella_bot.services.session_checkpoint import SavedSessionSummary
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


def test_empty_page_exposes_create_card():
    scene = _scene()

    scene.render()

    assert scene.create_button is not None


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
    assert len(scene.profile_cards) == 5


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
