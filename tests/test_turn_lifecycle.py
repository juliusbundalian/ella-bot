import queue
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ella_bot.core.events import SubLevelCompleted, SessionCompleted
from ella_bot.services.attempt_runner import AttemptRunner
from ella_bot.services.evaluation import EvaluationService
from ella_bot.services.session_manager import SessionManager
import ella_bot.services.attempt_runner as runner_mod


def _app(tmp_path, transcript="cat", level="2a", items=None):
    app = SimpleNamespace(
        session=SessionManager({level: items or ["cat", "dog"]}, level),
        evaluation=EvaluationService(tmp_path / "attempts.jsonl", 0.70),
        event_queue=queue.Queue(), audio_feedback=False, tts=None,
        pronunciation_overrides={}, current_level=level, prompt_active=False,
        save_active_session=MagicMock(return_value=True), clear_active_session=MagicMock(),
    )

    def transcribe(**kwargs):
        if kwargs.get("on_capture_started"):
            kwargs["on_capture_started"]()
        if kwargs.get("on_capture_stopped"):
            kwargs["on_capture_stopped"]()
        return SimpleNamespace(transcript=transcript, words=[])

    app.asr = SimpleNamespace(transcribe=transcribe)
    return app


def _events(app):
    return list(app.event_queue.queue)


def _statuses(app):
    return [event for event in _events(app) if type(event).__name__ == "TurnStatusChanged"]


@pytest.fixture(autouse=True)
def _skip_real_hold(monkeypatch):
    monkeypatch.setattr(runner_mod, "OUTCOME_HOLD_SECONDS", 0.0, raising=False)


@pytest.mark.parametrize(("transcript", "phase"), [("cat", "correct"), ("wrong", "retry"), ("", "no_input")])
def test_scored_turn_publishes_capture_and_outcome_phases(tmp_path, transcript, phase):
    app = _app(tmp_path, transcript)
    AttemptRunner(app, lambda: False).run()

    statuses = _statuses(app)
    assert [event.phase for event in statuses] == ["prompting", "preparing", "listening", "processing", phase]
    assert statuses[-1].expected_sentence == "cat"
    assert statuses[-1].attempt_number == 1
    assert statuses[-1].attempt_limit == 3
    assert len(app.evaluation._attempts["2a"]) == 1
    assert app.session.expected_sentence == ("dog" if phase == "correct" else "cat")
    assert app.prompt_active is False


@pytest.mark.parametrize("transcript", ["wrong", ""])
def test_three_unsuccessful_attempts_finish_item_once(tmp_path, transcript):
    app = _app(tmp_path, transcript)
    runner = AttemptRunner(app, lambda: False)
    for _ in range(3):
        runner.run()

    outcomes = [event for event in _statuses(app) if event.phase in {"retry", "no_input", "exhausted"}]
    assert [event.attempt_number for event in outcomes] == [1, 2, 3]
    assert outcomes[-1].phase == "exhausted"
    assert len(app.evaluation._attempts["2a"]) == 3
    assert app.session.current_item_number() == 2


def test_leaving_after_scoring_preserves_result_and_next_position(tmp_path, monkeypatch):
    app = _app(tmp_path)
    runner = AttemptRunner(app, lambda: False)

    def leave_during_hold(started_at):
        assert app.session.expected_sentence == "dog"
        assert app.prompt_active is True
        assert app.save_active_session.call_args.args == ("reading",)
        runner.abort()
        return True

    monkeypatch.setattr(runner, "_wait_for_outcome_hold", leave_during_hold, raising=False)
    runner.run()

    assert len(app.evaluation._attempts["2a"]) == 1
    assert _statuses(app)[-1].expected_sentence == "cat"


@pytest.mark.parametrize(("level", "event_type"), [("2a", SubLevelCompleted), ("4", SessionCompleted)])
def test_results_navigation_waits_for_hold_and_abort_keeps_checkpoint(tmp_path, monkeypatch, level, event_type):
    app = _app(tmp_path, level=level, items=["cat"])
    runner = AttemptRunner(app, lambda: False)

    def leave_during_hold(started_at):
        assert len(app.evaluation._attempts[level]) == 1
        assert not any(isinstance(event, event_type) for event in _events(app))
        runner.abort()
        return True

    monkeypatch.setattr(runner, "_wait_for_outcome_hold", leave_during_hold, raising=False)
    runner.run()

    assert not any(isinstance(event, event_type) for event in _events(app))
    if level == "4":
        app.clear_active_session.assert_called_once()
    else:
        assert app.save_active_session.call_args.args[0] == "results"


def test_microphone_error_does_not_consume_attempt(tmp_path):
    app = _app(tmp_path)
    app.asr.transcribe = MagicMock(side_effect=RuntimeError("microphone unavailable"))
    AttemptRunner(app, lambda: False).run()

    assert _statuses(app)[-1].phase == "error"
    assert not app.evaluation._attempts
    assert app.session.current_item_number() == 1


def test_outcome_hold_counts_only_unpaused_time(tmp_path, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(runner_mod, "OUTCOME_HOLD_SECONDS", 1.5)
    monkeypatch.setattr(runner_mod.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(runner_mod.time, "sleep", lambda duration: clock.__setitem__(0, clock[0] + duration))
    runner = AttemptRunner(_app(tmp_path), lambda: 0.2 <= clock[0] < 0.7)

    assert runner._wait_for_outcome_hold(0.0) is False
    assert 1.99 <= clock[0] <= 2.1


def test_long_feedback_already_satisfies_outcome_hold(tmp_path, monkeypatch):
    monkeypatch.setattr(runner_mod, "OUTCOME_HOLD_SECONDS", 1.5)
    monkeypatch.setattr(runner_mod.time, "monotonic", lambda: 6.0)
    sleep = MagicMock()
    monkeypatch.setattr(runner_mod.time, "sleep", sleep)
    assert AttemptRunner(_app(tmp_path), lambda: False)._wait_for_outcome_hold(0.0) is False
    sleep.assert_not_called()


def test_level1_publishes_practice_without_capture_or_scoring(tmp_path):
    app = _app(tmp_path, level="1a", items=["a"])
    app.asr.transcribe = MagicMock()
    AttemptRunner(app, lambda: False).run()

    assert [event.phase for event in _statuses(app)] == ["prompting", "practice"]
    assert _statuses(app)[-1].attempt_number is None
    app.asr.transcribe.assert_not_called()
    assert not app.evaluation._attempts


def test_paused_capture_restarts_without_consuming_attempt(tmp_path, monkeypatch):
    app = _app(tmp_path)
    paused = [False]
    calls = []
    runner = AttemptRunner(app, lambda: paused[0])

    def resume_when_waiting():
        paused[0] = False
        return runner._abort_requested

    monkeypatch.setattr(runner, "_wait_if_paused", resume_when_waiting)

    def transcribe(**kwargs):
        calls.append("capture")
        kwargs["on_capture_started"]()
        paused[0] = len(calls) == 1
        kwargs["on_capture_stopped"]()
        return SimpleNamespace(transcript="" if paused[0] else "cat", words=[])

    app.asr.transcribe = transcribe
    runner.run()
    assert len(calls) == 2
    assert len(app.evaluation._attempts["2a"]) == 1
    assert _statuses(app)[-1].phase == "correct"


def test_abort_before_scoring_does_not_consume_attempt(tmp_path):
    app = _app(tmp_path)
    runner = AttemptRunner(app, lambda: False)

    def transcribe(**kwargs):
        kwargs["on_capture_started"]()
        runner.abort()
        kwargs["on_capture_stopped"]()
        return SimpleNamespace(transcript="cat", words=[])

    app.asr.transcribe = transcribe
    runner.run()
    assert not app.evaluation._attempts
    assert app.session.current_item_number() == 1
    assert not any(event.phase in {"processing", "correct"} for event in _statuses(app))


def test_failed_results_save_stops_navigation(tmp_path):
    app = _app(tmp_path, items=["cat"])
    app.save_active_session.return_value = False
    AttemptRunner(app, lambda: False).run()
    assert _statuses(app)[-1].phase == "error"
    assert not any(isinstance(event, SubLevelCompleted) for event in _events(app))


def test_outcome_hold_excludes_pause_inside_blocking_feedback(tmp_path, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(runner_mod, "OUTCOME_HOLD_SECONDS", 1.5)
    monkeypatch.setattr(runner_mod.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(runner_mod.time, "sleep", lambda duration: clock.__setitem__(0, clock[0] + duration))
    runner = AttemptRunner(_app(tmp_path), lambda: False)
    clock[0] = 0.2
    runner.pause_changed(True)
    clock[0] = 6.2
    runner.pause_changed(False)
    clock[0] = 6.3

    assert runner._wait_for_outcome_hold(0.0) is False
    assert 7.49 <= clock[0] <= 7.6


def test_brief_pause_during_decode_is_latched_until_recapture(tmp_path):
    app = _app(tmp_path)
    runner = AttemptRunner(app, lambda: False)
    captures = []

    def transcribe(**kwargs):
        captures.append("started")
        kwargs["on_capture_started"]()
        if len(captures) == 1:
            runner.pause_changed(True)
            runner.pause_changed(False)
            assert kwargs["is_paused"]() is True
        kwargs["on_capture_stopped"]()
        return SimpleNamespace(transcript="cat", words=[])

    app.asr.transcribe = transcribe
    runner.run()
    assert len(captures) == 2
    assert len(app.evaluation._attempts["2a"]) == 1
