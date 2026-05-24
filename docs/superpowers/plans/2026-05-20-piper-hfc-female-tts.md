# Piper (hfc_female) TTS Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Piper the default TTS engine using the in-process `piper-tts` Python package and the `en_US-hfc_female-medium` voice, replacing the Windows-only subprocess binary path.

**Architecture:** Replace the subprocess-based `PiperTTS` with an in-process engine that loads a `PiperVoice` once at construction and streams synthesized audio through `sounddevice`. The factory's `piper` branch stops requiring a native binary and defaults the voice to `en_US-hfc_female-medium.onnx`. Kokoro stays in the codebase as a selectable engine but is no longer the default. `settings.ini` switches the default `tts_engine` to `piper`.

**Tech Stack:** Python 3.14, `piper-tts==1.4.2` (cp39-abi3 wheel, bundles its own espeak-ng phonemizer; depends on `onnxruntime` which is already installed), `sounddevice`, `numpy`, `pytest`.

**Key API facts (verified against piper-tts 1.4.2 in this venv):**
- `from piper import PiperVoice, SynthesisConfig`
- `PiperVoice.load(model_path, config_path=None, use_cuda=False)` — when `config_path` is omitted it loads `<model_path>.json` next to the model.
- `voice.synthesize(text, syn_config=None) -> Iterable[AudioChunk]`
- `SynthesisConfig(speaker_id=None, length_scale=None, noise_scale=None, noise_w_scale=None, normalize_audio=True, volume=1.0)`
- `AudioChunk` exposes `.audio_int16_bytes` (bytes), `.audio_int16_array` (np.int16), `.sample_rate` (int), `.sample_width` (int), `.sample_channels` (int).

**User-provided asset (NOT created by this plan):** `models/en_US-hfc_female-medium.onnx` and `models/en_US-hfc_female-medium.onnx.json`. The engine will fail to construct until these exist; tests stub `PiperVoice.load` so they do not need the real files.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `pyproject.toml` | Declare `piper-tts` as a runtime dependency | Modify |
| `src/ella_bot/speech/tts/engines/piper.py` | In-process Piper engine (load voice once, stream audio, apply warmth filter) | Rewrite |
| `src/ella_bot/speech/tts/factory.py` | `piper` branch builds the package-based engine with hfc_female default; `auto` branch prefers Piper over Kokoro | Modify |
| `config/settings.ini` | Default engine `piper`, default model `en_US-hfc_female-medium.onnx` | Modify |
| `tests/test_tts_piper.py` | Unit tests for engine streaming/warmth and factory wiring | Create |

---

### Task 1: Add piper-tts dependency

**Files:**
- Modify: `pyproject.toml:10-17`

- [ ] **Step 1: Add the dependency**

In `pyproject.toml`, change the `dependencies` list to include `piper-tts`:

```toml
dependencies = [
    "vosk",
    "sounddevice",
    "pygame-ce",
    "pyttsx3",
    "pronouncing",
    "numpy",
    "piper-tts>=1.4,<2",
]
```

- [ ] **Step 2: Install into the venv**

Run: `.venv/bin/pip install "piper-tts>=1.4,<2"`
Expected: ends with `Successfully installed ... piper-tts-1.4.2` (or already-satisfied if previously installed).

- [ ] **Step 3: Verify the import and API surface**

Run:
```bash
.venv/bin/python -c "from piper import PiperVoice, SynthesisConfig; from piper.voice import AudioChunk; print('ok')"
```
Expected: prints `ok` with no traceback.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "build: add piper-tts runtime dependency"
```

---

### Task 2: Rewrite PiperTTS as an in-process engine

**Files:**
- Rewrite: `src/ella_bot/speech/tts/engines/piper.py`
- Test: `tests/test_tts_piper.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_tts_piper.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_tts_piper.py -v`
Expected: FAIL — the current `PiperTTS.__init__` signature is `(config, piper_binary, piper_model)` and there is no `_voice`, `_syn_config`, `PiperVoice`, or module-level `sd.RawOutputStream` patch target matching the new design. Collection or assertions fail.

- [ ] **Step 3: Rewrite the engine**

Replace the entire contents of `src/ella_bot/speech/tts/engines/piper.py` with:

```python
from __future__ import annotations

import threading

import numpy as np
import sounddevice as sd
from piper import PiperVoice, SynthesisConfig

from ella_bot.speech.tts.base import BaseTTS, TTSConfig
from ella_bot.utils.logging import get_logger

logger = get_logger(__name__)


def _apply_warmth(pcm_int16: np.ndarray) -> np.ndarray:
    """Gentle FIR low-pass to soften harsh high frequencies, making the voice warmer."""
    audio = pcm_int16.astype(np.float32) / 32768.0
    b = np.array([0.25, 0.50, 0.25], dtype=np.float32)
    smoothed = np.convolve(audio, b, mode="same")
    output = 0.70 * audio + 0.30 * smoothed
    peak = np.max(np.abs(output)) if output.size else 0.0
    if peak > 0.95:
        output = output / peak * 0.95
    return (output * 32767).astype(np.int16)


class PiperTTS(BaseTTS):
    """Offline TTS using the in-process piper-tts package.

    The voice model is loaded once at construction and reused for every
    utterance, avoiding a per-call subprocess spawn (important on Pi 5).
    """

    def __init__(self, config: TTSConfig, piper_model: str):
        self.config = config or TTSConfig()
        self.piper_model = piper_model
        self._voice = PiperVoice.load(piper_model)
        self._syn_config = SynthesisConfig(
            length_scale=self.config.length_scale,
            noise_scale=self.config.noise_scale,
            noise_w_scale=self.config.noise_w,
        )
        self._stop = threading.Event()

    def speak(self, text: str) -> None:
        if self.config.non_blocking:
            threading.Thread(target=self._speak_sync, args=(text,), daemon=True).start()
        else:
            self._speak_sync(text)

    def stop(self) -> None:
        self._stop.set()
        try:
            sd.stop()
        except Exception:
            pass

    def _speak_sync(self, text: str) -> None:
        if not text.strip():
            return

        self._stop.clear()
        stream = None
        try:
            for chunk in self._voice.synthesize(text, syn_config=self._syn_config):
                if self._stop.is_set():
                    break
                pcm = np.frombuffer(chunk.audio_int16_bytes, dtype=np.int16).copy()
                pcm_warm = _apply_warmth(pcm)
                if stream is None:
                    stream = sd.RawOutputStream(
                        samplerate=chunk.sample_rate,
                        channels=chunk.sample_channels,
                        dtype="int16",
                    )
                    stream.start()
                stream.write(pcm_warm.tobytes())
        except Exception as exc:
            logger.error("PiperTTS error: %s", exc)
        finally:
            if stream is not None:
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_tts_piper.py -v`
Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ella_bot/speech/tts/engines/piper.py tests/test_tts_piper.py
git commit -m "refactor: rewrite PiperTTS to use in-process piper-tts package"
```

---

### Task 3: Update the factory for the package-based Piper and hfc_female default

**Files:**
- Modify: `src/ella_bot/speech/tts/factory.py:32-37` (piper branch)
- Modify: `src/ella_bot/speech/tts/factory.py:62-77` (auto branch piper detection)
- Test: `tests/test_tts_piper.py` (add factory tests)

- [ ] **Step 1: Add failing factory tests**

Append to `tests/test_tts_piper.py`:

```python
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
    from ella_bot.speech.tts.engines import piper as piper_mod
    captured = {}

    class FakePiper:
        def __init__(self, config, piper_model):
            captured["model"] = piper_model

    monkeypatch.setattr(piper_mod, "PiperTTS", FakePiper)
    from ella_bot.speech.tts.factory import build_tts
    build_tts("piper", TTSConfig(piper_model="./models/en_US-amy-medium.onnx"))
    assert captured["model"].endswith("en_US-amy-medium.onnx")
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_tts_piper.py::test_build_tts_piper_defaults_to_hfc_female tests/test_tts_piper.py::test_build_tts_piper_honors_explicit_model -v`
Expected: FAIL — the current `piper` branch builds `PiperTTS(config=config, piper_binary=binary, piper_model=model)` (extra `piper_binary` arg) and defaults the model to `bmo.onnx`, not `en_US-hfc_female-medium.onnx`.

- [ ] **Step 3: Update the `piper` branch**

In `src/ella_bot/speech/tts/factory.py`, replace the current `piper` branch (lines 32-37):

```python
    if name == "piper":
        from ella_bot.speech.tts.engines.piper import PiperTTS
        # Use defaults if not provided in config
        binary = (config.piper_binary if config else None) or "./piper/piper.exe"
        model = (config.piper_model if config else None) or "./models/bmo.onnx"
        return PiperTTS(config=config, piper_binary=binary, piper_model=model)
```

with:

```python
    if name == "piper":
        from ella_bot.speech.tts.engines.piper import PiperTTS
        from ella_bot.utils.file_utils import resolve_model_path
        model = resolve_model_path(
            (config.piper_model if config else None) or "en_US-hfc_female-medium.onnx"
        )
        return PiperTTS(config=config, piper_model=str(model))
```

- [ ] **Step 4: Update the `auto` branch to prefer Piper over Kokoro**

In the `auto` branch, the Kokoro block currently runs first (lines ~50-60) and the Piper block (lines ~62-77) requires a binary. Reorder so Piper is tried first and no binary is required. Replace the Kokoro-first block AND the Piper block — i.e. replace this span:

```python
        # 1. Check if Kokoro is available (High quality offline)
        kokoro_model = resolve_model_path((config.kokoro_model if config else None) or "kokoro-v1.0.onnx")
        kokoro_voices = resolve_model_path((config.kokoro_voices if config else None) or "voices-v1.0.bin")
        
        if kokoro_model.exists() and kokoro_voices.exists():
            try:
                from ella_bot.speech.tts.engines.kokoro import KokoroTTS
                print(f"[TTS] Auto-selecting Kokoro (High Quality Offline) for natural speech.")
                return KokoroTTS(config=config, model_path=str(kokoro_model), voices_path=str(kokoro_voices))
            except Exception as e:
                print(f"[TTS Warning] Kokoro failed to load: {e}")

        # 2. Check if Piper is available (Neural TTS)
        piper_bin = resolve_piper_path(config.piper_binary or "piper.exe")
        piper_model = resolve_model_path(config.piper_model or "en_US-amy-medium.onnx")
        
        # Fallback to other models if amy is missing
        if not piper_model.exists():
             piper_model = resolve_model_path("en_US-libritts_r-medium.onnx")

        if piper_bin.exists() and piper_model.exists():
            try:
                from ella_bot.speech.tts.engines.piper import PiperTTS
                print(f"[TTS] Auto-selecting Piper (Neural TTS) for high-quality offline speech.")
                print(f"[TTS] Using model: {piper_model}")
                return PiperTTS(config=config, piper_binary=str(piper_bin), piper_model=str(piper_model))
            except Exception as e:
                 print(f"[TTS Warning] Piper failed to load: {e}")
```

with:

```python
        # 1. Prefer Piper (in-process neural TTS, light enough for Pi 5)
        piper_model = resolve_model_path(
            (config.piper_model if config else None) or "en_US-hfc_female-medium.onnx"
        )
        if piper_model.exists():
            try:
                from ella_bot.speech.tts.engines.piper import PiperTTS
                print(f"[TTS] Auto-selecting Piper (Neural TTS). Model: {piper_model}")
                return PiperTTS(config=config, piper_model=str(piper_model))
            except Exception as e:
                print(f"[TTS Warning] Piper failed to load: {e}")

        # 2. Fall back to Kokoro if its model files are present
        kokoro_model = resolve_model_path((config.kokoro_model if config else None) or "kokoro-v1.0.onnx")
        kokoro_voices = resolve_model_path((config.kokoro_voices if config else None) or "voices-v1.0.bin")
        if kokoro_model.exists() and kokoro_voices.exists():
            try:
                from ella_bot.speech.tts.engines.kokoro import KokoroTTS
                print(f"[TTS] Auto-selecting Kokoro (High Quality Offline) for natural speech.")
                return KokoroTTS(config=config, model_path=str(kokoro_model), voices_path=str(kokoro_voices))
            except Exception as e:
                print(f"[TTS Warning] Kokoro failed to load: {e}")
```

Note: `resolve_piper_path` is now unused in the `auto` branch. Leave the import line at the top of the `auto` block as-is only if other code uses it; if the only use was the removed Piper-binary line, remove `resolve_piper_path` from that local import to avoid an unused name. Check with: `grep -n resolve_piper_path src/ella_bot/speech/tts/factory.py` and trim the import accordingly.

- [ ] **Step 5: Run the full piper test file**

Run: `.venv/bin/python -m pytest tests/test_tts_piper.py -v`
Expected: all tests PASS (7 total).

- [ ] **Step 6: Commit**

```bash
git add src/ella_bot/speech/tts/factory.py tests/test_tts_piper.py
git commit -m "refactor: default piper engine to hfc_female and prefer it in auto"
```

---

### Task 4: Switch settings.ini default engine to Piper

**Files:**
- Modify: `config/settings.ini:10-26`

- [ ] **Step 1: Update the `[TTS]` section**

In `config/settings.ini`, change `tts_engine` and `piper_model`, and update the model comment block. Replace:

```ini
tts_engine = say
tts_rate = 240
piper_binary = ./piper/piper.exe
# Available models (all in ./models/):
#   en_US-amy-medium.onnx         <- Warm, young FEMALE voice (Ella's voice) ✅
#   en_US-lessac-medium.onnx      <- Male voice
#   en_US-libritts_r-medium.onnx  <- Multi-speaker (mixed)
#   en_GB-semaine-medium.onnx     <- Female, British accent
#   bmo.onnx                      <- BMO cartoon voice
piper_model = ./models/en_US-amy-medium.onnx
```

with:

```ini
tts_engine = piper
tts_rate = 240
# piper_binary is unused: Piper now runs in-process via the piper-tts package.
# Available voice models (place the .onnx and matching .onnx.json in ./models/):
#   en_US-hfc_female-medium.onnx  <- Warm female voice (Ella's voice) ✅ default
#   en_US-amy-medium.onnx         <- Alternate young female voice
#   en_US-lessac-medium.onnx      <- Male voice
piper_model = ./models/en_US-hfc_female-medium.onnx
```

- [ ] **Step 2: Verify the config parses and resolves the engine name**

Run:
```bash
.venv/bin/python -c "import configparser; p=configparser.ConfigParser(); p.read('config/settings.ini'); print(p.get('TTS','tts_engine'), '|', p.get('TTS','piper_model'))"
```
Expected: prints `piper | ./models/en_US-hfc_female-medium.onnx`

- [ ] **Step 3: Commit**

```bash
git add config/settings.ini
git commit -m "config: default TTS engine to piper with hfc_female voice"
```

---

### Task 5: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Run the entire test suite**

Run: `.venv/bin/python -m pytest -v`
Expected: all tests PASS (the prior 36 + the new piper tests). No regressions.

- [ ] **Step 2: Confirm the engine constructs against the real voice (requires the user-provided model)**

Precondition: `models/en_US-hfc_female-medium.onnx` and `models/en_US-hfc_female-medium.onnx.json` exist.

Run:
```bash
.venv/bin/python -c "
from ella_bot.speech.tts.base import TTSConfig
from ella_bot.speech.tts.factory import build_tts
tts = build_tts('piper', TTSConfig(non_blocking=False))
print('built:', type(tts).__name__, '| sr-from-voice:', tts._voice.config.sample_rate)
"
```
Expected: prints `built: PiperTTS | sr-from-voice: 22050`.

If the model files are absent, this step is expected to raise from `PiperVoice.load`; report that the asset is missing rather than treating it as a code failure.

- [ ] **Step 3: Manual audio smoke (on a machine with audio output)**

Run:
```bash
.venv/bin/python -c "
from ella_bot.speech.tts.base import TTSConfig
from ella_bot.speech.tts.factory import build_tts
build_tts('piper', TTSConfig(non_blocking=False)).speak('Hello! I am Ella. Can you read this with me?')
"
```
Expected: audible speech in the hfc_female voice, no traceback. Confirm by listening. If running headless/CI, note that audio cannot be verified there and say so explicitly.

- [ ] **Step 4: Final commit if any verification fixups were needed**

Only if Step 1-3 required code changes:
```bash
git add -A
git commit -m "fix: address piper migration verification findings"
```

---

## Notes / Out of Scope

- **Deferred (separate plans, per scope decision):** Vosk 16 kHz downsampling, BotSprite frame pre-scaling, typed `AppConfig`, Tutorial/Settings scenes.
- **Kokoro:** kept as a selectable engine (`tts_engine = kokoro` still works); only the default changed.
- **`piper_binary` / `resolve_piper_path`:** now vestigial for the Piper path. `TTSConfig.piper_binary` and the CLI arg are left in place to avoid touching the argparse/loader surface in this focused change; remove them in the typed-`AppConfig` follow-up.
- **Warmth filter:** retained from the old engine, now applied per synthesized chunk. Piper chunks break at sentence boundaries (near-silence), so per-chunk `convolve(mode="same")` introduces no audible seam.
