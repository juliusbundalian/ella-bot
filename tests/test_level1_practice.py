import queue
import time
from unittest.mock import MagicMock
from pathlib import Path

from ella_bot.services.attempt_runner import AttemptRunner
from ella_bot.services.session_manager import SessionManager
from ella_bot.services.evaluation import EvaluationService
from ella_bot.core.events import SubLevelCompleted, StateChanged


def _make_app(tmp_path, level="1a"):
    app = MagicMock()
    app.audio_feedback = True
    app.tts = MagicMock()
    app.pronunciation_overrides = {"a": "phonemes:æ."}
    app.event_queue = queue.Queue()
    app.session = SessionManager(level_pools={"1a": ["a", "b"], "2a": ["cat"]}, start_level=level)
    app.evaluation = EvaluationService(log_path=tmp_path / "eval.jsonl", pass_bar=0.70)
    app.asr = MagicMock()
    return app


def _drain_events(app):
    events = []
    while not app.event_queue.empty():
        events.append(app.event_queue.get_nowait())
    return events


def test_level1_practice_run_bypasses_asr(tmp_path):
    app = _make_app(tmp_path, level="1a")
    runner = AttemptRunner(app, is_paused=lambda: False)

    runner.run()

    # ASR should NOT be called for Level 1 practice mode
    app.asr.transcribe.assert_not_called()
    # TTS should speak the pronunciation
    app.tts.speak.assert_called()


def test_level1_replay_speaks_pronunciation(tmp_path):
    app = _make_app(tmp_path, level="1a")
    runner = AttemptRunner(app, is_paused=lambda: False)

    runner.replay_level1()

    app.tts.speak.assert_called()
    events = _drain_events(app)
    assert any(isinstance(e, StateChanged) and e.state == "idle" for e in events)


def test_level1_advance_progresses_items_and_completes_sublevel(tmp_path):
    app = _make_app(tmp_path, level="1a")
    runner = AttemptRunner(app, is_paused=lambda: False)

    assert app.session.expected_sentence == "a"

    # Advance to next item ('b')
    runner.advance_level1()
    assert app.session.expected_sentence == "b"
    assert app.session.completed_in_level == 1

    # Advance to complete sublevel 1a (bypasses completion screen and advances directly to 1b)
    runner.advance_level1()
    assert app.session.current_level == "1b"


def test_level2_uses_asr_validation(tmp_path):
    app = _make_app(tmp_path, level="2a")
    fake_asr_res = MagicMock()
    fake_asr_res.transcript = "cat"
    fake_asr_res.words = []
    app.asr.transcribe.return_value = fake_asr_res

    runner = AttemptRunner(app, is_paused=lambda: False)
    runner.run()

    # Level 2 must invoke ASR transcribe
    app.asr.transcribe.assert_called_once()
