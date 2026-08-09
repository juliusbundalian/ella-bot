import queue
import time
from unittest.mock import MagicMock

from ella_bot.services.attempt_runner import AttemptRunner
from ella_bot.services.session_manager import SessionManager
from ella_bot.services.evaluation import EvaluationService
from ella_bot.core.events import SubLevelCompleted, AttemptReady
import ella_bot.services.attempt_runner as runner_mod


class _FakeValidation:
    accuracy = 1.0
    wer = 0.0
    alignment = []


class _FakeFeedback:
    level_message = "Excellent work! That was perfect!"


class _FakeASRResult:
    def __init__(self, transcript: str = "a"):
        self.transcript = transcript
        self.words = []


def _make_app(tmp_path):
    app = MagicMock()
    app.audio_feedback = False
    app.tts = None
    app.pronunciation_overrides = {}
    app.event_queue = queue.Queue()
    app.session = SessionManager(level_pools={"1a": ["a"], "1b": ["b"]}, start_level="1a")
    app.evaluation = EvaluationService(log_path=tmp_path / "s.jsonl", pass_bar=0.70)
    app.asr = MagicMock()
    app.asr.transcribe.return_value = _FakeASRResult()
    return app


def _make_app_with_tts(tmp_path, level_pools, start_level):
    app = MagicMock()
    app.audio_feedback = True
    app.tts = MagicMock()
    app.pronunciation_overrides = {"go": "phonemes:ɡˈɔ."}
    app.event_queue = queue.Queue()
    app.session = SessionManager(level_pools=level_pools, start_level=start_level)
    app.session.build_start_announcement = lambda: "Please read, go."
    app.evaluation = EvaluationService(log_path=tmp_path / "s.jsonl", pass_bar=0.70)
    app.asr = MagicMock()
    app.asr.transcribe.return_value = _FakeASRResult()
    return app


def _spoken(app):
    return [c.args[0] for c in app.tts.speak.call_args_list if c.args]


def _drain(app):
    events = []
    while not app.event_queue.empty():
        events.append(app.event_queue.get_nowait())
    return events


def test_completing_a_sublevel_posts_sublevel_completed(tmp_path, monkeypatch):
    monkeypatch.setattr(runner_mod, "validate_spoken_text", lambda exp, got, **kwargs: _FakeValidation())
    monkeypatch.setattr(runner_mod, "build_feedback", lambda **k: _FakeFeedback())
    monkeypatch.setattr(runner_mod, "build_highlighted_expected", lambda alignment: "")
    monkeypatch.setattr(runner_mod, "normalize", lambda t: ["a"])
    monkeypatch.setattr(runner_mod, "spoken_word_confidence_map", lambda toks, confs: {})

    app = _make_app(tmp_path)
    app.session = SessionManager(level_pools={"2a": ["a"]}, start_level="2a")
    runner = AttemptRunner(app, is_paused=lambda: False)
    runner.run()

    events = _drain(app)
    assert any(isinstance(e, SubLevelCompleted) and e.kind == "sublevel" for e in events)


def test_phonics_override_applies_on_tier1_item(tmp_path, monkeypatch):
    monkeypatch.setattr(runner_mod, "validate_spoken_text", lambda exp, got, **kwargs: _FakeValidation())
    monkeypatch.setattr(runner_mod, "build_feedback", lambda **k: _FakeFeedback())
    monkeypatch.setattr(runner_mod, "build_highlighted_expected", lambda alignment: "")
    monkeypatch.setattr(runner_mod, "normalize", lambda t: ["go"])
    monkeypatch.setattr(runner_mod, "spoken_word_confidence_map", lambda toks, confs: {})

    app = _make_app_with_tts(tmp_path, {"1c": ["go"]}, "1c")
    AttemptRunner(app, is_paused=lambda: False).run()

    assert "phonemes:ɡˈɔ." in _spoken(app)


def test_phonics_override_skipped_on_tier2_word(tmp_path, monkeypatch):
    monkeypatch.setattr(runner_mod, "validate_spoken_text", lambda exp, got, **kwargs: _FakeValidation())
    monkeypatch.setattr(runner_mod, "build_feedback", lambda **k: _FakeFeedback())
    monkeypatch.setattr(runner_mod, "build_highlighted_expected", lambda alignment: "")
    monkeypatch.setattr(runner_mod, "normalize", lambda t: ["go"])
    monkeypatch.setattr(runner_mod, "spoken_word_confidence_map", lambda toks, confs: {})

    app = _make_app_with_tts(tmp_path, {"2a": ["go"]}, "2a")
    AttemptRunner(app, is_paused=lambda: False).run()

    assert not any("phonemes:" in line for line in _spoken(app))


def test_levels_2_to_4_use_the_same_complete_prompt_and_rate(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(runner_mod, "validate_spoken_text", lambda exp, got, **kwargs: _FakeValidation())
    monkeypatch.setattr(runner_mod, "build_feedback", lambda **kwargs: _FakeFeedback())
    monkeypatch.setattr(runner_mod, "build_highlighted_expected", lambda alignment: "")
    monkeypatch.setattr(runner_mod, "normalize", lambda text: ["go"])
    monkeypatch.setattr(runner_mod, "spoken_word_confidence_map", lambda tokens, confidences: {})

    for level in ("2a", "3", "4"):
        app = _make_app_with_tts(tmp_path / level, {level: ["go"]}, level)

        AttemptRunner(app, is_paused=lambda: False).run()

        first_call = app.tts.speak.call_args_list[0]
        assert first_call.args == ("Please read, go.",)
        assert first_call.kwargs == {"rate": runner_mod.NON_LEVEL1_PROMPT_RATE}


def test_full_completion_clears_checkpoint_instead_of_saving_results(tmp_path):
    app = _make_app(tmp_path)
    app.session = SessionManager({"4": ["done"]}, "4")
    app.evaluation = EvaluationService(tmp_path / "s.jsonl", 0.70)
    runner = AttemptRunner(app, is_paused=lambda: False)
    app.evaluation.record_attempt("4", 1, "done", "done", 1.0, 0.0, True)

    runner._advance_after_attempt("4", app.session, True, False)

    app.clear_active_session.assert_called_once()
    app.save_active_session.assert_not_called()
