from dataclasses import asdict
from unittest.mock import MagicMock

from ella_bot.core.events import AttemptReady, MessageChanged
from ella_bot.services.evaluation import SubLevelResult
from ella_bot.ui.pygame_gui.app import EllaGUIApp
from ella_bot.ui.pygame_gui.config import GUIConfig


def _make_app(tmp_path, *, create_profile=False):
    app = EllaGUIApp(
        expected_sentence="",
        asr=MagicMock(),
        tts=None,
        audio_feedback=False,
        pronunciation_overrides={},
        config=GUIConfig(session_log_path=tmp_path / "sessions.jsonl"),
    )
    if create_profile and app.active_profile() is None:
        app.create_profile('Reader')
    return app


def test_new_session_requires_active_profile(tmp_path):
    app = _make_app(tmp_path)

    assert app.start_new_session('1a') is False
    assert not (tmp_path / 'active_session.json').exists()


def test_profile_selection_persists_and_binds_paths(tmp_path):
    app = _make_app(tmp_path)
    first = app.create_profile('First')
    app.create_profile('Second')
    app.select_profile(first.id)

    restarted = _make_app(tmp_path)

    assert restarted.active_profile() == first
    assert restarted.checkpoint_store.path == (
        tmp_path / 'profiles' / first.id / 'active_session.json'
    )
    assert restarted.evaluation.log_path == (
        tmp_path / 'profiles' / first.id / 'sessions.jsonl'
    )


def test_active_profile_greeting_data_persists_across_restart(tmp_path):
    app = _make_app(tmp_path)
    maria = app.create_profile('Maria')
    app.select_profile(maria.id)

    replacement = _make_app(tmp_path)

    assert replacement.active_profile().name == 'Maria'


def test_new_session_is_saved_before_live_state_is_replaced(tmp_path):
    app = _make_app(tmp_path, create_profile=True)
    old_session = app.session

    assert app.start_new_session("2c") is True

    assert app.session is not old_session
    assert app.current_level == "2c"
    assert app.selected_start_level == "2c"
    assert app.has_saved_session() is True


def test_invalid_new_level_does_not_replace_state(tmp_path):
    app = _make_app(tmp_path, create_profile=True)
    old_session = app.session

    assert app.start_new_session("missing") is False
    assert app.session is old_session
    assert app.has_saved_session() is False


def test_failed_new_session_save_keeps_old_state(tmp_path, monkeypatch):
    app = _make_app(tmp_path, create_profile=True)
    old_session = app.session
    monkeypatch.setattr(
        app.checkpoint_store,
        "save",
        MagicMock(side_effect=OSError("full")),
    )

    assert app.start_new_session("2a") is False
    assert app.session is old_session
    assert "could not be saved" in app.message.lower()


def test_continue_restores_reading_checkpoint(tmp_path):
    app = _make_app(tmp_path, create_profile=True)
    app.start_new_session("1a")
    app.session.advance_to_next_sentence()
    app.save_active_session("reading")
    replacement = _make_app(tmp_path)

    assert replacement.continue_saved_session() == "reading"
    assert replacement.session.current_item_number() == 2


def test_continue_restores_pending_result(tmp_path):
    app = _make_app(tmp_path, create_profile=True)
    app.start_new_session("1a")
    result = SubLevelResult(1, "1a", 5, 4, 6, 0.8, "B", True)
    app.save_active_session(
        "results",
        {"kind": "sublevel", "payload": asdict(result)},
    )
    replacement = _make_app(tmp_path)

    assert replacement.continue_saved_session() == "results"
    assert replacement.latest_result == result
    assert replacement.latest_result_kind == "sublevel"


def test_profiles_restore_distinct_exact_sessions(tmp_path):
    app = _make_app(tmp_path)
    first = app.create_profile('First')
    assert app.start_new_session('1a')
    app.evaluation.record_attempt(
        '1a', 1, app.expected_sentence, 'first learner', 0.25, 0.75, False
    )
    app.session.advance_to_next_sentence()
    first_result = SubLevelResult(1, '1a', 1, 1, 1, 0.98, 'A', True)
    app.save_active_session(
        'results',
        {'kind': 'sublevel', 'payload': asdict(first_result)},
    )

    second = app.create_profile('Second')
    assert app.start_new_session('2c')
    app.evaluation.record_attempt(
        '2c', 1, app.expected_sentence, 'second learner', 0.5, 0.5, False
    )
    second_result = SubLevelResult(2, '2c', 1, 0, 2, 0.5, 'E', False)
    app.save_active_session(
        'results',
        {'kind': 'sublevel', 'payload': asdict(second_result)},
    )

    app.select_profile(first.id)
    assert app.continue_saved_session() == 'results'
    assert app.current_level == '1a'
    assert app.session.current_item_number() == 2
    assert app.evaluation._attempts['1a'][0].heard == 'first learner'
    assert '2c' not in app.evaluation._attempts
    assert app.latest_result == first_result

    app.select_profile(second.id)
    assert app.continue_saved_session() == 'results'
    assert app.current_level == '2c'
    assert app.session.current_item_number() == 1
    assert app.evaluation._attempts['2c'][0].heard == 'second learner'
    assert '1a' not in app.evaluation._attempts
    assert app.latest_result == second_result


def test_profile_binding_clears_attempt_transients_and_queued_events(tmp_path):
    app = _make_app(tmp_path)
    first = app.create_profile('First')
    second = app.create_profile('Second')
    app.select_profile(first.id)
    stale_attempt = object()
    app.latest_attempt = stale_attempt
    app.state = 'retry'
    app.message = 'First learner feedback'
    app.prompt_active = True
    app.event_queue.put(AttemptReady(stale_attempt))
    app.event_queue.put(MessageChanged('Queued first learner feedback'))

    app.select_profile(second.id)

    assert app.latest_attempt is None
    assert app.state == 'idle'
    assert app.message == ''
    assert app.prompt_active is False
    assert app.event_queue.empty()


def test_app_shutdown_saves_started_active_session(tmp_path):
    app = _make_app(tmp_path, create_profile=True)
    app.selected_start_level = "1a"
    app.checkpoint_phase = "reading"
    app.save_active_session = MagicMock(return_value=True)
    app.active_scene = MagicMock()

    app.shutdown()

    app.active_scene.prepare_shutdown.assert_called_once()
    app.save_active_session.assert_called_once_with("reading", None)


def test_app_shutdown_does_not_save_unstarted_session(tmp_path):
    app = _make_app(tmp_path)
    app.save_active_session = MagicMock(return_value=True)
    app.active_scene = MagicMock()

    app.shutdown()

    app.active_scene.prepare_shutdown.assert_called_once()
    app.save_active_session.assert_not_called()
