import json
import queue
from types import SimpleNamespace

import pytest

from ella_bot.speech.asr import vosk_engine
from ella_bot.speech.asr.simulated import SimulatedASR


def _engine(monkeypatch, events):
    engine = object.__new__(vosk_engine.VoskASR)
    engine._model = object()
    engine._stream = SimpleNamespace(active=True)
    engine._audio_queue = queue.Queue()
    engine._audio_queue.put(b"old prompt audio")
    engine.sample_rate = 16000
    engine.listen_seconds = 0
    engine._ensure_model_loaded = lambda: events.append("model ready")

    class Recognizer:
        def SetWords(self, enabled):
            events.append("recognizer ready")
            engine._audio_queue.put(b"audio during setup")

        def FinalResult(self):
            events.append("final result")
            return json.dumps({"text": "cat", "result": []})

    original_import = vosk_engine.importlib.import_module
    monkeypatch.setattr(
        vosk_engine.importlib, "import_module",
        lambda name: SimpleNamespace(KaldiRecognizer=lambda *args: Recognizer())
        if name == "vosk" else original_import(name),
    )
    return engine


def test_capture_started_after_queue_reset_and_recognizer_ready(monkeypatch):
    events = []
    engine = _engine(monkeypatch, events)

    def started():
        assert engine._audio_queue.empty()
        events.append("started")

    result = engine.transcribe(on_capture_started=started, on_capture_stopped=lambda: events.append("stopped"))

    assert result.transcript == "cat"
    assert events == ["model ready", "recognizer ready", "started", "stopped", "final result"]


def test_cancelled_preparation_does_not_open_response_window(monkeypatch):
    events = []
    engine = _engine(monkeypatch, events)

    result = engine.transcribe(
        is_paused=lambda: True,
        on_capture_started=lambda: events.append("started"),
        on_capture_stopped=lambda: events.append("stopped"),
    )

    assert result.transcript == ""
    assert "started" not in events
    assert "final result" not in events


def test_failed_stream_is_an_error_instead_of_a_silent_attempt(monkeypatch):
    events = []
    engine = _engine(monkeypatch, events)
    engine._stream = None
    engine._start_background_stream = lambda: None

    with pytest.raises(RuntimeError, match="microphone"):
        engine.transcribe(on_capture_started=lambda: events.append("started"))
    assert "started" not in events


def test_simulated_asr_honors_capture_callbacks():
    events = []
    result = SimulatedASR("cat").transcribe(
        on_capture_started=lambda: events.append("started"),
        on_capture_stopped=lambda: events.append("stopped"),
    )
    assert result.transcript == "cat"
    assert events == ["started", "stopped"]
