# tests/test_reading_prompt_auto_continue.py
import time
from unittest.mock import MagicMock


def _make_scene_for_layout(expected_sentence):
    import pygame

    pygame.font.init()
    scene = _make_scene()
    scene.app.expected_sentence = expected_sentence
    scene.app.font_prompt_small = pygame.font.SysFont("Arial", 96)
    scene.app._prompt_font.side_effect = lambda pygame_module: scene.app.font_prompt_small
    scene.app._get_sys_font.side_effect = lambda size: pygame.font.SysFont("Arial", size)
    return scene, pygame


def _make_scene(state="idle", prompt_active=False, is_paused=False,
                modal_visible=False, auto_start_at=None):
    from ella_bot.ui.pygame_gui.scenes.reading_prompt import ReadingPromptScene
    app = MagicMock()
    app.state = state
    app.prompt_active = prompt_active
    scene = object.__new__(ReadingPromptScene)
    scene.app = app
    scene.is_paused = is_paused
    scene._auto_start_at = auto_start_at
    scene.modal = MagicMock()
    scene.modal.visible = modal_visible
    scene.bot = MagicMock()
    scene.worker_thread = None
    scene.last_activity_monotonic = time.monotonic()
    scene.idle_timeout_seconds = 10
    scene._drain_event_queue = MagicMock()
    scene._start_attempt = MagicMock()
    return scene


def test_timer_fires_when_expired():
    """Timer trigger calls _start_attempt and clears _auto_start_at."""
    scene = _make_scene(auto_start_at=time.monotonic() - 0.1)
    scene.update(0)
    scene._start_attempt.assert_called_once()
    assert scene._auto_start_at is None


def test_timer_does_not_fire_before_expiry():
    """Timer trigger does not fire when timestamp is in the future."""
    scene = _make_scene(auto_start_at=time.monotonic() + 60.0)
    scene.update(0)
    scene._start_attempt.assert_not_called()


def test_state_trigger_fires_when_listening_no_prompt():
    """State trigger fires when state is listening and prompt is inactive."""
    scene = _make_scene(state="listening", prompt_active=False, auto_start_at=None)
    scene.update(0)
    scene._start_attempt.assert_called_once()


def test_state_trigger_does_not_fire_when_prompt_active():
    """State trigger is blocked while an attempt is already running."""
    scene = _make_scene(state="listening", prompt_active=True, auto_start_at=None)
    scene.update(0)
    scene._start_attempt.assert_not_called()


def test_neither_trigger_fires_when_paused():
    """Both triggers are blocked while the session is paused."""
    scene = _make_scene(
        state="listening",
        is_paused=True,
        auto_start_at=time.monotonic() - 0.1,
    )
    scene.update(0)
    scene._start_attempt.assert_not_called()
    assert scene._auto_start_at is not None


def test_neither_trigger_fires_when_modal_visible():
    """Both triggers are blocked while the pause modal is open."""
    scene = _make_scene(
        state="listening",
        modal_visible=True,
        auto_start_at=time.monotonic() - 0.1,
    )
    scene.update(0)
    scene._start_attempt.assert_not_called()
    assert scene._auto_start_at is not None


def test_state_trigger_does_not_fire_when_not_listening():
    """State trigger only fires on 'listening'; other states do not trigger."""
    scene = _make_scene(state="processing", prompt_active=False, auto_start_at=None)
    scene.update(0)
    scene._start_attempt.assert_not_called()


def test_long_prompt_uses_smaller_font_and_higher_text_area():
    scene, pygame = _make_scene_for_layout(
        "she stepped in and respectfully stated a reasonable solution by "
        "sharing the consumer's rights and the store's policy."
    )
    inner_rect = pygame.Rect(32, 32, 1216, 656)

    font, text_rect = scene._prompt_layout(inner_rect, pygame)

    assert font.get_height() < scene.app.font_prompt_small.get_height()
    assert text_rect.top < inner_rect.top + 120
    assert text_rect.bottom <= scene._bot_safe_bottom(inner_rect)
    assert scene._wrapped_height(
        scene.app.expected_sentence, font, text_rect.width
    ) <= text_rect.height


def test_long_prompt_stays_above_ella_rendered_top():
    scene, pygame = _make_scene_for_layout(
        "she stepped in and respectfully stated a reasonable solution by "
        "sharing the consumer's rights and the store's policy."
    )
    inner_rect = pygame.Rect(32, 32, 1216, 656)

    _, text_rect = scene._prompt_layout(inner_rect, pygame)

    # BotSprite.draw() positions a maximum-height frame with its top at y=442.
    assert scene._bot_safe_bottom(inner_rect) == 442
    assert text_rect.bottom <= scene._bot_safe_bottom(inner_rect)


def test_long_prompt_returns_no_font_when_no_size_fits_safe_area():
    scene, pygame = _make_scene_for_layout("word " * 2_000)
    inner_rect = pygame.Rect(32, 32, 1216, 656)

    font, text_rect = scene._prompt_layout(inner_rect, pygame)

    assert font is None
    assert text_rect.bottom <= scene._bot_safe_bottom(inner_rect)
