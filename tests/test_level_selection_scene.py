from unittest.mock import MagicMock

import pygame

from ella_bot.core.constants import LEVEL_ORDER
from ella_bot.ui.pygame_gui.scenes.level_selection import (
    LEVEL_CAROUSEL_PAGES,
    LEVEL_NAMES,
    LevelSelectionScene,
)


def _scene():
    pygame.font.init()
    app = MagicMock()
    app.screen = pygame.Surface((1280, 720))
    app.font_title = pygame.font.SysFont(None, 64)
    app.font_body = pygame.font.SysFont(None, 30)
    app.font_small = pygame.font.SysFont(None, 22)
    app.font_button = pygame.font.SysFont(None, 42)
    return LevelSelectionScene(app)


def _click(scene, point):
    scene.handle_event(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=point)
    )
    scene.handle_event(
        pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=point)
    )


def test_carousel_pages_cover_every_level_in_curriculum_order():
    carousel_levels = [
        level
        for _, levels in LEVEL_CAROUSEL_PAGES
        for level in levels
    ]

    assert carousel_levels == LEVEL_ORDER
    assert LEVEL_CAROUSEL_PAGES[0][0] == "Level 1 - Practice Levels"
    assert LEVEL_CAROUSEL_PAGES[1][0] == "Level 1 - Practice Levels"


def test_first_page_shows_four_named_level_1_cards_and_indicators():
    scene = _scene()
    scene.render()

    assert list(scene.level_buttons) == ["1a", "1b", "1c", "1d"]
    assert scene.level_labels == {
        level: LEVEL_NAMES[level] for level in ("1a", "1b", "1c", "1d")
    }
    assert all(rect.width > 0 and rect.height > 0 for rect in scene.level_buttons.values())
    assert scene.carousel_previous_button is None
    assert scene.carousel_next_button is not None
    assert scene.page_indicator_states == [True, False, False, False]
    assert scene.back_button.centerx == scene.app.screen.get_rect().centerx
    assert scene.level_buttons["1a"].top == 219
    assert scene.back_button.top == 618


def test_each_carousel_page_shows_its_expected_named_levels():
    scene = _scene()

    for page, (_, expected_levels) in enumerate(LEVEL_CAROUSEL_PAGES):
        scene.carousel_page = page
        scene.render()

        assert tuple(scene.level_buttons) == expected_levels
        assert scene.level_labels == {
            level: LEVEL_NAMES[level] for level in expected_levels
        }
        assert scene.page_indicator_states == [
            index == page for index in range(len(LEVEL_CAROUSEL_PAGES))
        ]


def test_carousel_arrows_navigate_and_disabled_ends_do_not_wrap():
    scene = _scene()
    scene.render()

    disabled_previous_point = (112, 315)
    _click(scene, disabled_previous_point)
    assert scene.carousel_page == 0

    for expected_page in (1, 2, 3):
        next_point = scene.carousel_next_button.center
        _click(scene, next_point)
        assert scene.carousel_page == expected_page
        scene.render()

    assert scene.carousel_next_button is None
    disabled_next_point = (1168, 315)
    _click(scene, disabled_next_point)
    assert scene.carousel_page == 3

    previous_point = scene.carousel_previous_button.center
    _click(scene, previous_point)
    assert scene.carousel_page == 2


def test_selecting_level_opens_confirmation_without_replacing_checkpoint():
    scene = _scene()
    scene._select_level("2c")
    assert scene.pending_level == "2c"
    assert scene.show_confirmation is True
    scene.app.start_new_session.assert_not_called()


def test_start_level_modal_swaps_actions_and_uses_violet_cancel(monkeypatch):
    import ella_bot.ui.pygame_gui.scenes.level_selection as level_module

    rendered_buttons = []

    class RecordingButton:
        def __init__(self, rect, *, label, variant="yellow", **kwargs):
            self.rect = pygame.Rect(rect)
            self.label = label
            self.variant = variant
            self.is_pressed = False

        def draw(self, screen):
            rendered_buttons.append((self.label, self.variant, self.rect))

    monkeypatch.setattr(level_module, "Button", RecordingButton)
    scene = _scene()
    scene.pending_level = "2c"

    scene._draw_confirmation(scene.app.screen, 1280, 720)

    buttons = {label: (variant, rect) for label, variant, rect in rendered_buttons}
    assert buttons["Cancel"][0] == "violet"
    assert buttons["Cancel"][1].left < buttons["Confirm"][1].left


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
