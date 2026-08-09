# tests/test_reading_prompt_auto_continue.py
import queue
import time
from unittest.mock import MagicMock


def _make_scene_for_layout(expected_sentence, current_level="2a"):
    import pygame

    pygame.font.init()
    scene = _make_scene()
    scene.app.expected_sentence = expected_sentence
    scene.app.session.current_level = current_level
    scene.app.font_prompt_small = pygame.font.SysFont("Arial", 96)
    scene.app._prompt_font.side_effect = lambda pygame_module: scene.app.font_prompt_small
    scene.app._get_prompt_font.side_effect = lambda size: pygame.font.SysFont("Arial", size)
    return scene, pygame


def test_levels_3_and_4_use_smaller_font_and_narrower_prompt_area():
    for current_level in ("3", "4"):
        scene, pygame = _make_scene_for_layout(
            "Please read this advanced sentence aloud",
            current_level=current_level,
        )
        inner_rect = pygame.Rect(32, 32, 1216, 656)

        font, text_rect = scene._prompt_layout(inner_rect, pygame)

        assert font.get_height() < scene.app.font_prompt_small.get_height()
        assert text_rect.left > inner_rect.left + 40
        assert text_rect.width < inner_rect.width - 80
        assert text_rect.right < inner_rect.right - 40
        assert abs(text_rect.centerx - inner_rect.centerx) <= 1
        assert text_rect.centery == inner_rect.centery
        assert text_rect.bottom <= scene._bot_safe_bottom(inner_rect)
        assert max(call.args[0] for call in scene.app._get_prompt_font.call_args_list) <= 80


def test_level_4_prompt_is_narrower_to_clear_ella_on_the_right():
    sentence = "Please read this advanced sentence aloud"
    level_3_scene, pygame = _make_scene_for_layout(sentence, current_level="3")
    level_4_scene, _ = _make_scene_for_layout(sentence, current_level="4")
    inner_rect = pygame.Rect(32, 32, 1216, 656)

    _, level_3_rect = level_3_scene._prompt_layout(inner_rect, pygame)
    _, level_4_rect = level_4_scene._prompt_layout(inner_rect, pygame)

    assert level_4_rect.width == int(inner_rect.width * 0.50)
    assert level_4_rect.width < level_3_rect.width
    assert level_4_rect.right < level_3_rect.right


def test_level_2_uses_smaller_font_and_stays_above_ella():
    scene, pygame = _make_scene_for_layout(
        "Please read this sentence",
        current_level="2a",
    )
    inner_rect = pygame.Rect(32, 32, 1216, 656)

    font, text_rect = scene._prompt_layout(inner_rect, pygame)

    assert font.get_height() < scene.app.font_prompt_small.get_height()
    assert text_rect == pygame.Rect(
        inner_rect.left + 40,
        scene._centered_safe_top(inner_rect, scene._bot_safe_bottom(inner_rect)),
        inner_rect.width - 80,
        scene._bot_safe_bottom(inner_rect)
        - scene._centered_safe_top(inner_rect, scene._bot_safe_bottom(inner_rect)),
    )
    assert text_rect.centery == inner_rect.centery
    assert text_rect.bottom <= scene._bot_safe_bottom(inner_rect)
    assert max(call.args[0] for call in scene.app._get_prompt_font.call_args_list) <= 72


def test_level_2_shrinks_a_short_prompt_that_is_too_wide():
    scene, pygame = _make_scene_for_layout(
        "characteristically incomprehensibilities institutionalization counterrevolutionaries",
        current_level="2a",
    )
    inner_rect = pygame.Rect(32, 32, 1216, 656)

    font, text_rect = scene._prompt_layout(inner_rect, pygame)

    assert font.get_height() < scene.app.font_prompt_small.get_height()
    assert font.size(scene.app.expected_sentence)[0] <= text_rect.width
    scene.app._get_prompt_font.assert_called()


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
    scene.runner = MagicMock()
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


def test_session_completion_opens_standard_results_scene():
    from ella_bot.core.events import SessionCompleted
    from ella_bot.services.evaluation import CumulativeResult
    from ella_bot.ui.pygame_gui.scenes.reading_prompt import ReadingPromptScene

    scene = _make_scene()
    result = CumulativeResult(0.86, "A", 28, 24, [], 180.0)
    scene.app.event_queue = queue.Queue()
    scene.app.event_queue.put(SessionCompleted(result))

    ReadingPromptScene._drain_event_queue(scene)

    assert scene.app.latest_result == result
    assert scene.app.latest_result_kind == "session"
    scene.app.switch_scene.assert_called_once_with("results")


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


def test_long_level_2_prompt_uses_smaller_font_and_centered_safe_area():
    scene, pygame = _make_scene_for_layout(
        "she stepped in and respectfully stated a reasonable solution by "
        "sharing the consumer's rights and the store's policy."
    )
    inner_rect = pygame.Rect(32, 32, 1216, 656)

    font, text_rect = scene._prompt_layout(inner_rect, pygame)

    assert font.get_height() < scene.app.font_prompt_small.get_height()
    assert text_rect.centery == inner_rect.centery
    assert text_rect.bottom <= scene._bot_safe_bottom(inner_rect)
    assert scene._wrapped_height(
        scene.app.expected_sentence, font, text_rect.width
    ) <= text_rect.height
    scene.app._get_prompt_font.assert_called()
    scene.app._get_sys_font.assert_not_called()


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


def test_pause_restart_aborts_then_resets_saves_and_starts():
    scene = _make_scene(is_paused=True, modal_visible=True)
    scene.app.save_active_session.return_value = True
    actions = []
    scene.runner.abort.side_effect = lambda: actions.append("abort")
    scene.app.session.reset_current_level.side_effect = lambda: actions.append("reset")
    scene.app.save_active_session.side_effect = lambda phase: actions.append("save") or True

    scene._restart_level_from_pause()

    assert actions == ["abort", "reset", "save"]
    scene.app.evaluation.reset_sublevel.assert_called_once()
    scene._start_attempt.assert_called_once()


def test_pause_restart_joins_worker_before_resetting_session():
    scene = _make_scene(is_paused=True, modal_visible=True)
    scene.app.save_active_session.return_value = True
    worker_thread = MagicMock()
    worker_thread.is_alive.side_effect = [True, False]
    scene.worker_thread = worker_thread
    actions = []
    worker_thread.join.side_effect = lambda timeout: actions.append("join")
    scene.app.session.reset_current_level.side_effect = lambda: actions.append("reset")

    scene._restart_level_from_pause()

    assert actions == ["join", "reset"]
    worker_thread.join.assert_called_once_with(timeout=2.0)


def test_pause_restart_failed_save_restores_and_remains_paused():
    scene = _make_scene(is_paused=True, modal_visible=True)
    scene.app.save_active_session.return_value = False

    scene._restart_level_from_pause()

    scene.app.continue_saved_session.assert_called_once()
    scene._start_attempt.assert_not_called()
    assert scene.is_paused is True


def test_pause_back_to_menu_aborts_saves_then_navigates():
    scene = _make_scene(is_paused=True, modal_visible=True)
    scene.app.save_active_session.return_value = True
    actions = []
    scene.runner.abort.side_effect = lambda: actions.append("abort")
    scene.app.save_active_session.side_effect = lambda phase: actions.append("save") or True
    scene.app.switch_scene.side_effect = lambda name: actions.append("navigate")

    scene._return_to_menu_from_pause()

    assert actions == ["abort", "save", "navigate"]
    scene.app.switch_scene.assert_called_once_with("main_menu")


def test_pause_back_to_menu_keeps_live_worker_and_refuses_navigation():
    scene = _make_scene(is_paused=True, modal_visible=True)
    worker_thread = MagicMock()
    worker_thread.is_alive.return_value = True
    scene.worker_thread = worker_thread

    scene._return_to_menu_from_pause()

    worker_thread.join.assert_called_once_with(timeout=2.0)
    assert scene.worker_thread is worker_thread
    scene.app.save_active_session.assert_not_called()
    scene.app.switch_scene.assert_not_called()


def test_prepare_shutdown_aborts_and_joins_attempt_worker():
    scene = _make_scene()
    scene.runner = MagicMock()
    scene.worker_thread = MagicMock()
    scene.worker_thread.is_alive.return_value = True

    scene.prepare_shutdown()

    scene.runner.abort.assert_called_once()
    scene.worker_thread.join.assert_called_once_with(timeout=2.0)


def test_on_exit_quiesces_attempt_worker_before_navigation():
    scene = _make_scene()
    worker_thread = MagicMock()
    worker_thread.is_alive.side_effect = [True, False]
    scene.worker_thread = worker_thread
    actions = []
    scene.runner.abort.side_effect = lambda: actions.append('abort')
    worker_thread.join.side_effect = lambda timeout: actions.append('join')

    exited = scene.on_exit()

    assert actions == ['abort', 'join']
    worker_thread.join.assert_called_once_with(timeout=2.0)
    assert exited is True
    assert scene.worker_thread is None


def test_on_exit_refuses_transition_when_worker_does_not_stop():
    scene = _make_scene()
    worker_thread = MagicMock()
    worker_thread.is_alive.return_value = True
    scene.worker_thread = worker_thread

    exited = scene.on_exit()

    assert exited is False
    worker_thread.join.assert_called_once_with(timeout=2.0)
    assert scene.worker_thread is worker_thread
