import numpy as np
import pytest

from ella_bot.speech.tts.base import TTSConfig


class _FakeChunk:
    def __init__(self, pcm_int16: np.ndarray, sample_rate: int = 22050, channels: int = 1):
        self.audio_int16_bytes = pcm_int16.tobytes()
        self.sample_rate = sample_rate
        self.sample_channels = channels


class _FakeVoice:
    def __init__(self):
        self.spoken = []

    def synthesize(self, text, syn_config=None, include_alignments=False):
        self.spoken.append(text)
        pcm = (np.ones(128, dtype=np.int16) * 1000)
        yield _FakeChunk(pcm)


class _FakeStream:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.written = b""
        self.started = False
        self.closed = False
        _FakeStream.instances.append(self)

    def start(self):
        self.started = True

    def write(self, data):
        self.written += bytes(data)

    def stop(self):
        pass

    def abort(self):
        pass

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def _reset_streams():
    _FakeStream.instances.clear()
    yield
    _FakeStream.instances.clear()


def _patch_piper(monkeypatch, voice):
    from ella_bot.speech.tts.engines import piper as piper_mod
    monkeypatch.setattr(piper_mod.PiperVoice, "load", staticmethod(lambda *a, **k: voice))
    monkeypatch.setattr(piper_mod.sd, "RawOutputStream", _FakeStream)
    return piper_mod


def test_apply_warmth_preserves_length_and_dtype():
    from ella_bot.speech.tts.engines.piper import _apply_warmth
    pcm = (np.random.randint(-2000, 2000, size=256)).astype(np.int16)
    out = _apply_warmth(pcm)
    assert out.dtype == np.int16
    assert out.shape == pcm.shape
    assert np.all(np.abs(out.astype(np.int32)) <= 32767)


def test_piper_loads_voice_once_at_construction(monkeypatch):
    voice = _FakeVoice()
    piper_mod = _patch_piper(monkeypatch, voice)
    tts = piper_mod.PiperTTS(config=TTSConfig(), piper_model="x.onnx")
    assert tts._voice is voice


def test_piper_speak_streams_audio_through_sounddevice(monkeypatch):
    voice = _FakeVoice()
    piper_mod = _patch_piper(monkeypatch, voice)
    tts = piper_mod.PiperTTS(config=TTSConfig(non_blocking=False), piper_model="x.onnx")
    tts.speak("hello world")
    assert voice.spoken == ["hello world"]
    assert len(_FakeStream.instances) == 1
    stream = _FakeStream.instances[0]
    assert stream.kwargs["samplerate"] == 22050
    assert stream.kwargs["channels"] == 1
    assert stream.started is True
    assert len(stream.written) == 128 * 2  # 128 int16 samples


def test_piper_speak_ignores_empty_text(monkeypatch):
    voice = _FakeVoice()
    piper_mod = _patch_piper(monkeypatch, voice)
    tts = piper_mod.PiperTTS(config=TTSConfig(), piper_model="x.onnx")
    tts.speak("   ")
    assert voice.spoken == []
    assert _FakeStream.instances == []


def test_piper_passes_synthesis_config_from_ttsconfig(monkeypatch):
    voice = _FakeVoice()
    piper_mod = _patch_piper(monkeypatch, voice)
    cfg = TTSConfig(noise_scale=0.5, noise_w=0.9, length_scale=1.2)
    tts = piper_mod.PiperTTS(config=cfg, piper_model="x.onnx")
    assert tts._syn_config.noise_scale == 0.5
    assert tts._syn_config.noise_w_scale == 0.9
    assert tts._syn_config.length_scale == pytest.approx(1.2 * 200 / cfg.rate)


def test_build_tts_piper_defaults_to_hfc_female(monkeypatch):
    from ella_bot.speech.tts.engines import piper as piper_mod
    captured = {}

    class FakePiper:
        def __init__(self, config, piper_model):
            captured["model"] = piper_model

    monkeypatch.setattr(piper_mod, "PiperTTS", FakePiper)
    from ella_bot.speech.tts.factory import build_tts
    build_tts("piper", TTSConfig())
    assert captured["model"].endswith("en_US-hfc_female-medium.onnx")
    assert "models" in captured["model"]


def test_build_tts_piper_honors_explicit_model(monkeypatch):
    import pathlib
    from ella_bot.speech.tts.engines import piper as piper_mod
    captured = {}

    class FakePiper:
        def __init__(self, config, piper_model):
            captured["model"] = piper_model

    monkeypatch.setattr(piper_mod, "PiperTTS", FakePiper)
    monkeypatch.setattr(pathlib.Path, "exists", lambda self: True)
    from ella_bot.speech.tts.factory import build_tts
    build_tts("piper", TTSConfig(piper_model="./models/en_US-amy-medium.onnx"))
    assert captured["model"].endswith("en_US-amy-medium.onnx")


def test_piper_stop_calls_stream_abort(monkeypatch):
    import threading

    class _SlowFakeVoice:
        """Yields one chunk then blocks until an event is set."""
        def __init__(self, proceed: threading.Event):
            self._proceed = proceed
            self.spoken = []

        def synthesize(self, text, syn_config=None, include_alignments=False):
            self.spoken.append(text)
            pcm = (np.ones(128, dtype=np.int16) * 500)
            yield _FakeChunk(pcm)
            # Block here — stop() should interrupt before a second chunk
            self._proceed.wait(timeout=2)

    class _TrackingStream(_FakeStream):
        aborted = False
        stopped = False

        def abort(self):
            _TrackingStream.aborted = True

        def stop(self):
            _TrackingStream.stopped = True

    _TrackingStream.aborted = False
    _TrackingStream.stopped = False

    proceed = threading.Event()
    voice = _SlowFakeVoice(proceed)

    from ella_bot.speech.tts.engines import piper as piper_mod
    monkeypatch.setattr(piper_mod.PiperVoice, "load", staticmethod(lambda *a, **k: voice))
    monkeypatch.setattr(piper_mod.sd, "RawOutputStream", _TrackingStream)

    tts = piper_mod.PiperTTS(config=TTSConfig(non_blocking=True), piper_model="x.onnx")
    tts.speak("cancel me")
    # Give the thread a moment to open the stream and reach the blocking synthesize
    import time; time.sleep(0.05)
    tts.stop()
    proceed.set()  # unblock the synthesize generator

    # Wait for the background thread to finish
    time.sleep(0.1)

    assert voice.spoken == ["cancel me"]
    assert _TrackingStream.aborted is True, "stream.abort() should be called when stop() was requested"
    assert _TrackingStream.stopped is False, "stream.stop() should NOT be called when stop() was requested"


def test_set_volume_rebuilds_syn_config():
    from unittest.mock import MagicMock, patch
    from ella_bot.speech.tts.engines.piper import PiperTTS
    from ella_bot.speech.tts.base import TTSConfig

    config = TTSConfig(length_scale=1.0, noise_scale=0.667, noise_w=0.8)
    with patch("ella_bot.speech.tts.engines.piper.PiperVoice.load", return_value=MagicMock()):
        tts = PiperTTS(config=config, piper_model="fake.onnx")

    tts.set_volume(0.5)
    assert tts._syn_config.volume == 0.5


def test_base_tts_set_volume_is_noop():
    from ella_bot.speech.tts.base import BaseTTS
    tts = BaseTTS()
    result = tts.set_volume(0.5)
    assert result is None
