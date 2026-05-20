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
    assert tts._syn_config.length_scale == 1.2
