import queue
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


def test_completing_a_sublevel_posts_sublevel_completed(tmp_path, monkeypatch):
    monkeypatch.setattr(runner_mod, "validate_spoken_text", lambda exp, got: _FakeValidation())
    monkeypatch.setattr(runner_mod, "build_feedback", lambda **k: _FakeFeedback())
    monkeypatch.setattr(runner_mod, "build_highlighted_expected", lambda alignment: "")
    monkeypatch.setattr(runner_mod, "normalize", lambda t: ["a"])
    monkeypatch.setattr(runner_mod, "spoken_word_confidence_map", lambda toks, confs: {})

    app = _make_app(tmp_path)
    runner = AttemptRunner(app, is_paused=lambda: False)
    runner.run()

    events = []
    while not app.event_queue.empty():
        events.append(app.event_queue.get_nowait())
    assert any(isinstance(e, SubLevelCompleted) and e.kind == "sublevel" for e in events)
    # one attempt recorded and a sublevel record written
    assert (tmp_path / "s.jsonl").read_text().count('"type": "sublevel"') == 1


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


def test_phonics_override_applies_on_tier1_item(tmp_path, monkeypatch):
    monkeypatch.setattr(runner_mod, "validate_spoken_text", lambda exp, got: _FakeValidation())
    monkeypatch.setattr(runner_mod, "build_feedback", lambda **k: _FakeFeedback())
    monkeypatch.setattr(runner_mod, "build_highlighted_expected", lambda alignment: "")
    monkeypatch.setattr(runner_mod, "normalize", lambda t: ["go"])
    monkeypatch.setattr(runner_mod, "spoken_word_confidence_map", lambda toks, confs: {})

    app = _make_app_with_tts(tmp_path, {"1c": ["go"]}, "1c")
    AttemptRunner(app, is_paused=lambda: False).run()

    # On a tier-1 phonics level the IPA blend pronunciation must be used.
    assert "phonemes:ɡˈɔ." in _spoken(app)


def test_phonics_override_skipped_on_tier2_word(tmp_path, monkeypatch):
    monkeypatch.setattr(runner_mod, "validate_spoken_text", lambda exp, got: _FakeValidation())
    monkeypatch.setattr(runner_mod, "build_feedback", lambda **k: _FakeFeedback())
    monkeypatch.setattr(runner_mod, "build_highlighted_expected", lambda alignment: "")
    monkeypatch.setattr(runner_mod, "normalize", lambda t: ["go"])
    monkeypatch.setattr(runner_mod, "spoken_word_confidence_map", lambda toks, confs: {})

    app = _make_app_with_tts(tmp_path, {"2a": ["go"]}, "2a")
    AttemptRunner(app, is_paused=lambda: False).run()

    # On tier 2+ the real word "go" must be spoken naturally, never as the
    # tier-1 phonics phoneme.
    assert not any("phonemes:" in line for line in _spoken(app))


class _FakeWrongValidation:
    accuracy = 0.0
    wer = 1.0
    alignment = []


def test_tier1_wrong_answer_advances_to_next_item(tmp_path, monkeypatch):
    monkeypatch.setattr(runner_mod, "validate_spoken_text", lambda exp, got: _FakeWrongValidation())
    monkeypatch.setattr(runner_mod, "build_feedback", lambda **k: _FakeFeedback())
    monkeypatch.setattr(runner_mod, "build_highlighted_expected", lambda alignment: "")
    monkeypatch.setattr(runner_mod, "normalize", lambda t: [])
    monkeypatch.setattr(runner_mod, "spoken_word_confidence_map", lambda toks, confs: {})

    app = _make_app(tmp_path)
    app.session = SessionManager(
        level_pools={"1a": ["sentence one", "sentence two"]}, start_level="1a"
    )
    runner = AttemptRunner(app, is_paused=lambda: False)

    assert app.session.expected_sentence == "sentence one"
    runner.run()
    assert app.session.expected_sentence == "sentence two"
    assert app.session.completed_in_level == 1


def test_tier1_sublevel_completes_on_single_wrong_answer(tmp_path, monkeypatch):
    monkeypatch.setattr(runner_mod, "validate_spoken_text", lambda exp, got: _FakeWrongValidation())
    monkeypatch.setattr(runner_mod, "build_feedback", lambda **k: _FakeFeedback())
    monkeypatch.setattr(runner_mod, "build_highlighted_expected", lambda alignment: "")
    monkeypatch.setattr(runner_mod, "normalize", lambda t: [])
    monkeypatch.setattr(runner_mod, "spoken_word_confidence_map", lambda toks, confs: {})

    app = _make_app(tmp_path)
    app.session = SessionManager(level_pools={"1a": ["a"]}, start_level="1a")
    runner = AttemptRunner(app, is_paused=lambda: False)
    runner.run()

    events = []
    while not app.event_queue.empty():
        events.append(app.event_queue.get_nowait())
    assert any(isinstance(e, SubLevelCompleted) for e in events)


def test_tier2_wrong_answers_retry_within_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(runner_mod, "validate_spoken_text", lambda exp, got: _FakeWrongValidation())
    monkeypatch.setattr(runner_mod, "build_feedback", lambda **k: _FakeFeedback())
    monkeypatch.setattr(runner_mod, "build_highlighted_expected", lambda alignment: "")
    monkeypatch.setattr(runner_mod, "normalize", lambda t: [])
    monkeypatch.setattr(runner_mod, "spoken_word_confidence_map", lambda toks, confs: {})

    app = _make_app(tmp_path)
    app.session = SessionManager(
        level_pools={"2a": ["item one", "item two"]}, start_level="2a"
    )
    runner = AttemptRunner(app, is_paused=lambda: False)

    runner.run()  # attempt 1
    assert app.session.expected_sentence == "item one"
    assert app.session.completed_in_level == 0

    runner.run()  # attempt 2
    assert app.session.expected_sentence == "item one"
    assert app.session.completed_in_level == 0


def test_tier2_exhausted_after_third_wrong_advances_item(tmp_path, monkeypatch):
    monkeypatch.setattr(runner_mod, "validate_spoken_text", lambda exp, got: _FakeWrongValidation())
    monkeypatch.setattr(runner_mod, "build_feedback", lambda **k: _FakeFeedback())
    monkeypatch.setattr(runner_mod, "build_highlighted_expected", lambda alignment: "")
    monkeypatch.setattr(runner_mod, "normalize", lambda t: [])
    monkeypatch.setattr(runner_mod, "spoken_word_confidence_map", lambda toks, confs: {})

    app = _make_app(tmp_path)
    app.session = SessionManager(
        level_pools={"2a": ["item one", "item two"]}, start_level="2a"
    )
    runner = AttemptRunner(app, is_paused=lambda: False)

    runner.run()  # attempt 1 — retry
    runner.run()  # attempt 2 — retry
    runner.run()  # attempt 3 — exhausted, advance

    assert app.session.expected_sentence == "item two"
    assert app.session.completed_in_level == 1


def test_tier2_attempt_counter_resets_on_new_item(tmp_path, monkeypatch):
    monkeypatch.setattr(runner_mod, "validate_spoken_text", lambda exp, got: _FakeWrongValidation())
    monkeypatch.setattr(runner_mod, "build_feedback", lambda **k: _FakeFeedback())
    monkeypatch.setattr(runner_mod, "build_highlighted_expected", lambda alignment: "")
    monkeypatch.setattr(runner_mod, "normalize", lambda t: [])
    monkeypatch.setattr(runner_mod, "spoken_word_confidence_map", lambda toks, confs: {})

    app = _make_app(tmp_path)
    app.session = SessionManager(
        level_pools={"2a": ["item one", "item two"]}, start_level="2a"
    )
    runner = AttemptRunner(app, is_paused=lambda: False)

    runner.run(); runner.run(); runner.run()  # exhaust item one
    assert app.session.expected_sentence == "item two"

    runner.run()  # first wrong attempt on item two — should NOT advance yet
    assert app.session.expected_sentence == "item two"
    assert app.session.completed_in_level == 1  # only item one counted so far


def _drain(app):
    events = []
    while not app.event_queue.empty():
        events.append(app.event_queue.get_nowait())
    return events


def test_silent_turn_tier1_advances_with_move_on_phrase(tmp_path):
    app = _make_app_with_tts(tmp_path, {"1a": ["a", "b"]}, "1a")
    app.asr.transcribe.return_value = _FakeASRResult("")

    runner = AttemptRunner(app, is_paused=lambda: False)
    assert app.session.expected_sentence == "a"
    runner.run()

    assert app.session.expected_sentence == "b"
    assert app.session.completed_in_level == 1
    assert any(line in runner_mod._NO_INPUT_MOVE_ON_PHRASES for line in _spoken(app))
    assert app.evaluation._attempts["1a"][0].heard == ""


def test_silent_turn_tier2_with_tries_left_stays_with_reprompt(tmp_path):
    app = _make_app_with_tts(tmp_path, {"2a": ["item one", "item two"]}, "2a")
    app.asr.transcribe.return_value = _FakeASRResult("")

    runner = AttemptRunner(app, is_paused=lambda: False)
    runner.run()

    assert app.session.expected_sentence == "item one"
    assert app.session.completed_in_level == 0
    assert any(line in runner_mod._NO_INPUT_PHRASES for line in _spoken(app))


def test_silent_turn_tier2_final_attempt_advances(tmp_path):
    app = _make_app_with_tts(tmp_path, {"2a": ["item one", "item two"]}, "2a")
    app.asr.transcribe.return_value = _FakeASRResult("")

    runner = AttemptRunner(app, is_paused=lambda: False)
    runner.run()  # attempt 1 — re-prompt
    runner.run()  # attempt 2 — re-prompt
    runner.run()  # attempt 3 — exhausted, advance

    assert app.session.expected_sentence == "item two"
    assert app.session.completed_in_level == 1
    assert any(line in runner_mod._NO_INPUT_MOVE_ON_PHRASES for line in _spoken(app))


def test_silent_turn_speaks_no_coaching(tmp_path):
    app = _make_app_with_tts(tmp_path, {"2a": ["item one", "item two"]}, "2a")
    app.asr.transcribe.return_value = _FakeASRResult("")

    AttemptRunner(app, is_paused=lambda: False).run()

    spoken = _spoken(app)
    assert not any("Now you try!" in line for line in spoken)
    assert not any("let me read" in line.lower() for line in spoken)


def test_silent_turn_emits_no_attempt_ready(tmp_path):
    app = _make_app_with_tts(tmp_path, {"2a": ["item one", "item two"]}, "2a")
    app.asr.transcribe.return_value = _FakeASRResult("")

    AttemptRunner(app, is_paused=lambda: False).run()

    assert not any(isinstance(e, AttemptReady) for e in _drain(app))


def test_silent_turn_completing_sublevel_posts_sublevel_completed(tmp_path):
    app = _make_app_with_tts(tmp_path, {"1a": ["only item"]}, "1a")
    app.asr.transcribe.return_value = _FakeASRResult("")

    AttemptRunner(app, is_paused=lambda: False).run()

    assert any(
        isinstance(e, SubLevelCompleted) and e.kind == "sublevel" for e in _drain(app)
    )
