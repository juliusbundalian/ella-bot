from dataclasses import asdict
from unittest.mock import MagicMock

from ella_bot.services.evaluation import SubLevelResult
from ella_bot.ui.pygame_gui.app import EllaGUIApp
from ella_bot.ui.pygame_gui.config import GUIConfig


def _make_app(tmp_path):
    return EllaGUIApp(
        expected_sentence="",
        asr=MagicMock(),
        tts=None,
        audio_feedback=False,
        pronunciation_overrides={},
        config=GUIConfig(session_log_path=tmp_path / "sessions.jsonl"),
    )


def test_new_session_is_saved_before_live_state_is_replaced(tmp_path):
    app = _make_app(tmp_path)
    old_session = app.session

    assert app.start_new_session("2c") is True

    assert app.session is not old_session
    assert app.current_level == "2c"
    assert app.selected_start_level == "2c"
    assert app.has_saved_session() is True


def test_invalid_new_level_does_not_replace_state(tmp_path):
    app = _make_app(tmp_path)
    old_session = app.session

    assert app.start_new_session("missing") is False
    assert app.session is old_session
    assert app.has_saved_session() is False


def test_failed_new_session_save_keeps_old_state(tmp_path, monkeypatch):
    app = _make_app(tmp_path)
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
    app = _make_app(tmp_path)
    app.start_new_session("1a")
    app.session.advance_to_next_sentence()
    app.save_active_session("reading")
    replacement = _make_app(tmp_path)

    assert replacement.continue_saved_session() == "reading"
    assert replacement.session.current_item_number() == 2


def test_continue_restores_pending_result(tmp_path):
    app = _make_app(tmp_path)
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
