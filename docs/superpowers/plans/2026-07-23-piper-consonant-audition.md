# Piper Consonant Audition Comparison Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in audition comparison that renders level 1B consonants with four tuning profiles through ELLA's existing Piper voice without changing runtime playback.

**Architecture:** Keep all comparison behavior in the existing diagnostic script. Represent each tuning profile with an immutable value object, keep classification/profile selection pure and directly testable, and lazily load Piper/audio only when comparison playback is requested. The normal audition path continues through `build_tts()` unchanged.

**Tech Stack:** Python 3.10+, argparse, dataclasses, NumPy, sounddevice, piper-tts, pytest

## Global Constraints

- Use only `models/en_US-hfc_female-medium.onnx`; do not introduce another voice or engine.
- Do not change normal ELLA runtime playback.
- Do not change `config/pronunciation_overrides.json`.
- Do not repeat consonants, append vowels, use carrier words, or create audio files.
- Do not change ASR, validation, accepted answers, scoring, or progression.
- Comparison mode is valid only for level `1b` with engine `piper`.
- Preserve `--dry-run` without loading the Piper model or opening an audio device.
- Preserve unrelated staged and unstaged changes in the existing working tree; every commit uses explicit pathspecs.

---

## File Structure

- Modify `scripts/audition_level.py`: define comparison profiles, validate comparison arguments, synthesize/play comparison audio, and route the opt-in CLI mode.
- Create `tests/test_audition_level.py`: cover exact profiles, consonant classification, CLI validation, dry-run isolation, and direct Piper comparison playback.

### Task 1: Define Exact Piper Comparison Profiles

**Files:**

- Modify: `scripts/audition_level.py:10-62`
- Create: `tests/test_audition_level.py`

**Interfaces:**

- Consumes: a lowercase level 1B target letter.
- Produces: `PiperVariant`, `consonant_class(letter: str) -> str`, and `comparison_variants(letter: str) -> tuple[PiperVariant, ...]`.

- [ ] **Step 1: Write failing tests for classification and all profile values**

Create `tests/test_audition_level.py`:

```python
import pytest

from scripts.audition_level import PiperVariant, comparison_variants, consonant_class


@pytest.mark.parametrize(
    ("letter", "expected"),
    [
        ("b", "stop"),
        ("j", "stop"),
        ("f", "continuous"),
        ("z", "continuous"),
        ("q", "sequence"),
        ("x", "sequence"),
    ],
)
def test_consonant_class_identifies_tuning_group(letter, expected):
    assert consonant_class(letter) == expected


def test_consonant_class_rejects_unknown_target():
    with pytest.raises(ValueError, match="Unsupported level 1B consonant"):
        consonant_class("a")


@pytest.mark.parametrize(
    ("letter", "class_rate"),
    [("b", 170), ("f", 125), ("x", 145)],
)
def test_comparison_variants_have_exact_audition_settings(letter, class_rate):
    assert comparison_variants(letter) == (
        PiperVariant("current", 190, 0.667, 0.8, True, 0),
        PiperVariant("clean", 190, 0.3, 0.3, False, 0),
        PiperVariant("relaxed", 145, 0.3, 0.3, False, 200),
        PiperVariant("class-tuned", class_rate, 0.2, 0.2, False, 250),
    )
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
./.venv/bin/python -m pytest -q tests/test_audition_level.py
```

Expected: collection fails with an import error for `PiperVariant` because the comparison API does not exist yet.

- [ ] **Step 3: Add the immutable profile model and classification functions**

In `scripts/audition_level.py`, add `dataclass` to the imports and place this code after the ELLA imports:

```python
from dataclasses import dataclass


STOP_CONSONANTS = frozenset("bcdgjkpt")
CONTINUOUS_CONSONANTS = frozenset("fhlmnrsvwyz")
SEQUENCE_CONSONANTS = frozenset("qx")


@dataclass(frozen=True)
class PiperVariant:
    name: str
    rate: int
    noise_scale: float
    noise_w_scale: float
    warmth: bool
    padding_ms: int


def consonant_class(letter: str) -> str:
    normalized = letter.lower()
    if normalized in STOP_CONSONANTS:
        return "stop"
    if normalized in CONTINUOUS_CONSONANTS:
        return "continuous"
    if normalized in SEQUENCE_CONSONANTS:
        return "sequence"
    raise ValueError(f"Unsupported level 1B consonant: {letter!r}")


def comparison_variants(letter: str) -> tuple[PiperVariant, ...]:
    class_rates = {"stop": 170, "continuous": 125, "sequence": 145}
    class_rate = class_rates[consonant_class(letter)]
    return (
        PiperVariant("current", 190, 0.667, 0.8, True, 0),
        PiperVariant("clean", 190, 0.3, 0.3, False, 0),
        PiperVariant("relaxed", 145, 0.3, 0.3, False, 200),
        PiperVariant("class-tuned", class_rate, 0.2, 0.2, False, 250),
    )
```

Keep the `dataclasses` import with the standard-library imports when formatting the final file.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run:

```bash
./.venv/bin/python -m pytest -q tests/test_audition_level.py
```

Expected: `10 passed`.

- [ ] **Step 5: Commit the profile API and tests**

```bash
git add scripts/audition_level.py tests/test_audition_level.py
git diff --cached --check
git commit -m "test: define Piper consonant audition profiles" -- scripts/audition_level.py tests/test_audition_level.py
```

### Task 2: Add Opt-In Comparison Playback and Validation

**Files:**

- Modify: `scripts/audition_level.py:35-110`
- Modify: `tests/test_audition_level.py`

**Interfaces:**

- Consumes: `--compare-piper`, a level 1B phoneme override, `PiperVariant`, and the configured Piper model path.
- Produces: `validate_compare_request(level: str, engine: str, items: list[str]) -> str | None`, `play_piper_variant(voice, spoken: str, variant: PiperVariant) -> int`, and `main(argv: list[str] | None = None) -> int`.

- [ ] **Step 1: Add failing tests for request validation and dry-run isolation**

Append to `tests/test_audition_level.py`:

```python
from scripts import audition_level
from scripts.audition_level import validate_compare_request


@pytest.mark.parametrize(
    ("level", "engine", "items", "message"),
    [
        ("1a", "piper", ["a"], "only available for level 1b"),
        ("1b", "espeak", ["b"], "requires --engine piper"),
        ("1b", "piper", [], "did not match any level 1b target"),
    ],
)
def test_validate_compare_request_rejects_invalid_combinations(level, engine, items, message):
    assert validate_compare_request(level, engine, items) == message


def test_validate_compare_request_accepts_level_1b_piper_target():
    assert validate_compare_request("1b", "piper", ["b"]) is None


def test_compare_dry_run_does_not_load_piper_or_open_audio(monkeypatch, capsys, tmp_path):
    def fail_load(*args, **kwargs):
        raise AssertionError("Piper must not load during a dry run")

    model_path = tmp_path / "voice.onnx"
    model_path.touch()
    monkeypatch.setattr(audition_level, "load_piper_voice", fail_load)

    result = audition_level.main(
        [
            "1b",
            "--compare-piper",
            "--only",
            "b",
            "--piper-model",
            str(model_path),
            "--dry-run",
        ]
    )

    assert result == 0
    output = capsys.readouterr().out
    assert "b [current]" in output
    assert "b [clean]" in output
    assert "b [relaxed]" in output
    assert "b [class-tuned]" in output


def test_compare_reports_missing_model(capsys, tmp_path):
    result = audition_level.main(
        [
            "1b",
            "--compare-piper",
            "--only",
            "b",
            "--piper-model",
            str(tmp_path / "missing.onnx"),
        ]
    )

    assert result == 2
    assert "Piper model not found" in capsys.readouterr().err


def test_compare_reports_target_and_variant_when_playback_fails(monkeypatch, capsys, tmp_path):
    model_path = tmp_path / "voice.onnx"
    model_path.touch()
    monkeypatch.setattr(audition_level, "load_piper_voice", lambda path: object())
    monkeypatch.setattr(
        audition_level,
        "play_piper_variant",
        lambda voice, spoken, variant: (_ for _ in ()).throw(RuntimeError("no output device")),
    )

    result = audition_level.main(
        [
            "1b",
            "--compare-piper",
            "--only",
            "b",
            "--piper-model",
            str(model_path),
        ]
    )

    assert result == 1
    assert "Comparison failed for b [current]: no output device" in capsys.readouterr().err
```

- [ ] **Step 2: Add a failing test for direct Piper synthesis, filtering choice, and padding**

Append to `tests/test_audition_level.py`:

```python
import numpy as np


class _FakeVoice:
    class _Config:
        sample_rate = 1000

    config = _Config()

    def __init__(self):
        self.phonemes = None
        self.syn_config = None

    def phonemes_to_ids(self, phonemes):
        self.phonemes = phonemes
        return [1, 2, 3]

    def phoneme_ids_to_audio(self, phoneme_ids, syn_config):
        assert phoneme_ids == [1, 2, 3]
        self.syn_config = syn_config
        return np.ones(100, dtype=np.int16) * 1000


def test_play_relaxed_variant_uses_exact_config_and_padding(monkeypatch):
    voice = _FakeVoice()
    played = {}
    variant = PiperVariant("relaxed", 145, 0.3, 0.3, False, 200)

    monkeypatch.setattr(
        audition_level.sd,
        "play",
        lambda pcm, samplerate: played.update(pcm=pcm.copy(), samplerate=samplerate),
    )
    monkeypatch.setattr(audition_level.sd, "wait", lambda: None)

    samples = audition_level.play_piper_variant(voice, "phonemes:b.", variant)

    assert voice.phonemes == list("b.")
    assert voice.syn_config.length_scale == pytest.approx(200 / 145)
    assert voice.syn_config.noise_scale == 0.3
    assert voice.syn_config.noise_w_scale == 0.3
    assert played["samplerate"] == 1000
    assert len(played["pcm"]) == 500
    assert np.all(played["pcm"][:200] == 0)
    assert np.all(played["pcm"][-200:] == 0)
    assert samples == 500


def test_current_variant_uses_existing_warmth_filter(monkeypatch):
    voice = _FakeVoice()
    warmth_calls = []
    variant = PiperVariant("current", 190, 0.667, 0.8, True, 0)

    monkeypatch.setattr(
        audition_level,
        "_apply_warmth",
        lambda pcm: warmth_calls.append(pcm.copy()) or pcm,
    )
    monkeypatch.setattr(audition_level.sd, "play", lambda pcm, samplerate: None)
    monkeypatch.setattr(audition_level.sd, "wait", lambda: None)

    samples = audition_level.play_piper_variant(voice, "phonemes:f.", variant)

    assert len(warmth_calls) == 1
    assert samples == 100
```

- [ ] **Step 3: Run the expanded tests and verify RED**

Run:

```bash
./.venv/bin/python -m pytest -q tests/test_audition_level.py
```

Expected: collection fails because `validate_compare_request` and the comparison playback API do not exist.

- [ ] **Step 4: Add the comparison flag and make argument parsing testable**

Change the parser and main signatures in `scripts/audition_level.py`:

```python
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("level", help="Level/sub-level to audition, e.g. 1c, 2a, 3")
    p.add_argument("--only", default=None, help="Only speak items containing this substring")
    p.add_argument("--engine", default="piper", help="TTS engine (default: piper)")
    p.add_argument(
        "--rate",
        type=int,
        default=190,
        help="Speech rate / words-per-minute. Lower is slower (default: 190)",
    )
    p.add_argument(
        "--gap",
        type=float,
        default=1.0,
        help="Seconds of silence to pause between items or comparison variants (default: 1.0)",
    )
    p.add_argument(
        "--piper-model",
        default="./models/en_US-hfc_female-medium.onnx",
        help="Path to Piper voice model",
    )
    p.add_argument(
        "--pools",
        default="./config/level_pools.json",
        help="Path to level_pools.json",
    )
    p.add_argument(
        "--overrides",
        default="./config/pronunciation_overrides.json",
        help="Path to pronunciation_overrides.json",
    )
    p.add_argument(
        "--compare-piper",
        action="store_true",
        help="Compare Piper tuning variants for isolated level 1b consonants",
    )
    p.add_argument("--dry-run", action="store_true", help="Print what would be spoken without playing audio")
    return p.parse_args(argv)
```

Change `main()` to accept arguments and pass them into `parse_args()`:

```python
def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
```

- [ ] **Step 5: Add comparison validation and direct Piper playback helpers**

Add these imports near the top of `scripts/audition_level.py`:

```python
import numpy as np
import sounddevice as sd
from piper import PiperVoice, SynthesisConfig

from ella_bot.speech.tts.engines.piper import _apply_warmth
```

Add these helpers after `comparison_variants()`:

```python
def validate_compare_request(level: str, engine: str, items: list[str]) -> str | None:
    if level.lower() != "1b":
        return "--compare-piper is only available for level 1b"
    if engine.lower() != "piper":
        return "--compare-piper requires --engine piper"
    if not items:
        return "--only did not match any level 1b target"
    return None


def load_piper_voice(model_path: Path) -> PiperVoice:
    return PiperVoice.load(str(model_path))


def _as_int16(audio: np.ndarray) -> np.ndarray:
    if audio.dtype == np.float32 or audio.dtype == np.float64:
        return (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
    return audio.astype(np.int16, copy=False)


def play_piper_variant(voice, spoken: str, variant: PiperVariant) -> int:
    if not spoken.startswith(("phonemes:", "phonemes,")):
        raise ValueError(f"Comparison target is not a phoneme override: {spoken!r}")

    raw_phonemes = spoken[9:].strip()
    phoneme_ids = voice.phonemes_to_ids(list(raw_phonemes))
    syn_config = SynthesisConfig(
        length_scale=200 / variant.rate,
        noise_scale=variant.noise_scale,
        noise_w_scale=variant.noise_w_scale,
        volume=1.0,
    )
    pcm = _as_int16(voice.phoneme_ids_to_audio(phoneme_ids, syn_config=syn_config))
    if variant.warmth:
        pcm = _apply_warmth(pcm)
    if variant.padding_ms:
        pad_samples = round(voice.config.sample_rate * variant.padding_ms / 1000)
        pcm = np.pad(pcm, (pad_samples, pad_samples))

    sd.play(pcm, samplerate=voice.config.sample_rate)
    sd.wait()
    return len(pcm)
```

- [ ] **Step 6: Route comparison mode before the existing TTS construction**

In `main()`, keep loading pools, overrides, filtering items, and printing the level header as today. Immediately after the item filter, add:

```python
    if args.compare_piper:
        error = validate_compare_request(args.level, args.engine, items)
        if error:
            print(error, file=sys.stderr)
            return 2

        model_path = Path(args.piper_model)
        if not model_path.is_absolute():
            model_path = ROOT / model_path
        if not model_path.is_file():
            print(f"Piper model not found: {model_path}", file=sys.stderr)
            return 2

        voice = None if args.dry_run else load_piper_voice(model_path)
        print(f"Level 1b Piper comparison: {len(items)} item(s).\n")
        for item in items:
            spoken = level_overrides.get(item.lower(), item)
            for variant in comparison_variants(item):
                print(
                    f"  {item} [{variant.name}] rate={variant.rate} "
                    f"noise={variant.noise_scale}/{variant.noise_w_scale} "
                    f"warmth={'on' if variant.warmth else 'off'} "
                    f"padding={variant.padding_ms}ms"
                )
                if voice is not None:
                    try:
                        play_piper_variant(voice, spoken, variant)
                    except Exception as exc:
                        print(f"Comparison failed for {item} [{variant.name}]: {exc}", file=sys.stderr)
                        return 1
                    time.sleep(args.gap)
        return 0
```

Leave the existing `build_tts()` path below this block unchanged so normal audition commands retain their current behavior.

- [ ] **Step 7: Run the focused tests and verify GREEN**

Run:

```bash
./.venv/bin/python -m pytest -q tests/test_audition_level.py
```

Expected: `19 passed`.

- [ ] **Step 8: Verify CLI validation and dry-run output manually**

Run:

```bash
./.venv/bin/python scripts/audition_level.py 1a --compare-piper --dry-run
./.venv/bin/python scripts/audition_level.py 1b --compare-piper --engine espeak --dry-run
./.venv/bin/python scripts/audition_level.py 1b --compare-piper --only b --dry-run
```

Expected: the first two commands exit `2` with the exact validation messages; the third exits `0`, does not initialize audio, and prints all four B variants.

- [ ] **Step 9: Commit comparison playback**

```bash
git add scripts/audition_level.py tests/test_audition_level.py
git diff --cached --check
git commit -m "feat: compare Piper consonant tuning variants" -- scripts/audition_level.py tests/test_audition_level.py
```

### Task 3: Regression Verification and Audible Handoff

**Files:**

- Verify only: `scripts/audition_level.py`
- Verify only: `tests/test_audition_level.py`
- Verify unchanged: `config/pronunciation_overrides.json`
- Verify unchanged: `src/ella_bot/speech/tts/engines/piper.py`

**Interfaces:**

- Consumes: the completed `--compare-piper` audition mode.
- Produces: automated verification evidence and copy-pasteable commands for the user's audible comparison.

- [ ] **Step 1: Run audition, Piper, and pronunciation regression tests**

Run:

```bash
./.venv/bin/python -m pytest -q tests/test_audition_level.py tests/test_tts_piper.py tests/test_pronunciation_overrides.py
```

Expected: all selected tests pass.

- [ ] **Step 2: Confirm the normal dry-run path remains unchanged**

Run:

```bash
./.venv/bin/python scripts/audition_level.py 1b --dry-run
```

Expected: 21 phoneme mappings print once each, with no comparison-variant labels.

- [ ] **Step 3: Check scope and whitespace**

Run:

```bash
git diff --check f2a78ba..HEAD
git diff f2a78ba..HEAD -- scripts/audition_level.py tests/test_audition_level.py config/pronunciation_overrides.json src/ella_bot/speech/tts/engines/piper.py
```

Expected: no whitespace errors; task changes exist only in the script and its new test. The production override and Piper engine files have no task-related diff.

- [ ] **Step 4: Audition representative consonant classes on the ELLA audio device**

Run one command at a time and note whether `current`, `clean`, `relaxed`, or `class-tuned` is clearest:

```bash
./.venv/bin/python scripts/audition_level.py 1b --compare-piper --only b
./.venv/bin/python scripts/audition_level.py 1b --compare-piper --only f
./.venv/bin/python scripts/audition_level.py 1b --compare-piper --only j
./.venv/bin/python scripts/audition_level.py 1b --compare-piper --only x
```

Expected: each command plays four labeled variants through the same `en_US-hfc_female-medium.onnx` voice. This step gathers user judgment; it does not claim a winning profile automatically.

- [ ] **Step 5: Audition all level 1B consonants only if a representative variant is acceptable**

Run:

```bash
./.venv/bin/python scripts/audition_level.py 1b --compare-piper
```

Expected: all 21 consonants play with the four labeled variants. Record the preferred variant or report that none is acceptable. Do not modify production playback in this plan.
