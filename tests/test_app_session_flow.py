from dataclasses import asdict
from unittest.mock import MagicMock

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
    app.session.advance_to_next_sentence()
    app.save_active_session('reading')

    second = app.create_profile('Second')
    assert app.start_new_session('2c')
    app.save_active_session('reading')

    app.select_profile(first.id)
    assert app.continue_saved_session() == 'reading'
    assert app.current_level == '1a'
    assert app.session.current_item_number() == 2

    app.select_profile(second.id)
    assert app.continue_saved_session() == 'reading'
    assert app.current_level == '2c'
    assert app.session.current_item_number() == 1


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
