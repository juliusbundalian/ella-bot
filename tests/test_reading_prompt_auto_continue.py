# tests/test_reading_prompt_auto_continue.py
import time
from unittest.mock import MagicMock


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


def test_neither_trigger_fires_when_modal_visible():
    """Both triggers are blocked while the pause modal is open."""
    scene = _make_scene(
        state="listening",
        modal_visible=True,
        auto_start_at=time.monotonic() - 0.1,
    )
    scene.update(0)
    scene._start_attempt.assert_not_called()
