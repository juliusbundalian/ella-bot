from ella_bot.speech.asr.factory import build_asr
from ella_bot.speech.asr.simulated import SimulatedASR
from ella_bot.speech.asr.vosk_engine import VoskASR


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
