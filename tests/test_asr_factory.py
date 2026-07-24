from ella_bot.speech.asr.factory import build_asr
from ella_bot.speech.asr.simulated import SimulatedASR
from ella_bot.speech.asr.vosk_engine import VoskASR, WordScore, format_attempt_diagnostics


def test_build_asr_returns_simulated_when_not_using_mic():
    engine = build_asr(use_mic=False, spoken="the cat sat")
    assert isinstance(engine, SimulatedASR)
    assert engine.transcribe().transcript == "the cat sat"


def test_build_asr_returns_vosk_when_using_mic(monkeypatch):
    # Avoid loading a real model: stub VoskASR construction.
    captured = {}

    class FakeVosk:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("ella_bot.speech.asr.factory.VoskASR", FakeVosk)
    build_asr(
        use_mic=True,
        vosk_model_path="/models/x",
        sample_rate=16000,
        listen_seconds=5,
        input_device=3,
    )
    assert captured["model_path"] == "/models/x"
    assert captured["sample_rate"] == 16000
    assert captured["listen_seconds"] == 5
    assert captured["input_device"] == 3


def test_format_attempt_diagnostics_reports_backlog_and_word_confidence():
    message = format_attempt_diagnostics(
        capture_seconds=10.0,
        processed_bytes=320000,
        processed_blocks=40,
        queued_bytes=8000,
        queued_blocks=1,
        sample_rate=16000,
        decoder_seconds=10.2,
        transcript="the cat sat",
        words=[WordScore("the", 0.98), WordScore("cat", 0.62)],
    )

    assert "capture=10.00s" in message
    assert "processed=10.00s/40 blocks" in message
    assert "backlog=0.25s/1 blocks" in message
    assert "decode=10.20s" in message
    assert "transcript='the cat sat'" in message
    assert "the:0.98, cat:0.62" in message
