# English Phonics for Levels 1A and 1B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make ELLA model standard beginner English phonics sounds for level 1A vowels and level 1B consonants without changing student grading.

**Architecture:** Keep the existing Tier 1 override pipeline and replace only the single-letter values in `config/pronunciation_overrides.json` with Piper-compatible IPA. Add a focused configuration regression test; do not modify `AttemptRunner`, `ASR_HOMOPHONES`, validation, scoring, or the level 1C–1G blend entries.

**Tech Stack:** Python 3.9+, pytest, JSON configuration, Piper TTS direct phoneme synthesis

## Global Constraints

- Level 1A uses standard short English vowel sounds: A /æ/, E /ɛ/, I /ɪ/, O /ɑ/ in American English, and U /ʌ/.
- Level 1B uses standard beginner consonant sounds without an added schwa.
- C uses /k/, G uses /ɡ/, Q uses /kw/, and X uses /ks/.
- `src/ella_bot/validation/validators.py`, including `ASR_HOMOPHONES`, remains unchanged.
- Existing accepted student pronunciations, scoring, thresholds, curriculum pools, and progression remain unchanged.
- All level 1C–1G consonant-vowel blend override values remain unchanged.
- No new dependencies or recorded audio assets.

---

## File Structure

- Modify `config/pronunciation_overrides.json`: replace only the five level 1A and twenty-one level 1B single-letter spoken forms.
- Create `tests/test_pronunciation_overrides.py`: assert the complete English single-letter mapping and protect representative level 1C blend values from regression.

### Task 1: Replace the 1A and 1B Spoken Forms

**Files:**

- Create: `tests/test_pronunciation_overrides.py`
- Modify: `config/pronunciation_overrides.json:2-27`

**Interfaces:**

- Consumes: the existing `phonemes:<IPA>.` convention recognized by `PiperTTS._speak_sync()`.
- Produces: a JSON mapping from each level 1A/1B target letter to its English phoneme form; the public structure and file location remain unchanged.

- [ ] **Step 1: Write the failing configuration regression tests**

Create `tests/test_pronunciation_overrides.py`:

```python
import json
from pathlib import Path


OVERRIDES_PATH = Path(__file__).resolve().parents[1] / "config" / "pronunciation_overrides.json"

LEVEL_1A_ENGLISH_PHONICS = {
    "a": "phonemes:ˈæ.",
    "e": "phonemes:ˈɛ.",
    "i": "phonemes:ˈɪ.",
    "o": "phonemes:ˈɑ.",
    "u": "phonemes:ˈʌ.",
}

LEVEL_1B_ENGLISH_PHONICS = {
    "b": "phonemes:b.",
    "c": "phonemes:k.",
    "d": "phonemes:d.",
    "f": "phonemes:f.",
    "g": "phonemes:ɡ.",
    "h": "phonemes:h.",
    "j": "phonemes:dʒ.",
    "k": "phonemes:k.",
    "l": "phonemes:l.",
    "m": "phonemes:m.",
    "n": "phonemes:n.",
    "p": "phonemes:p.",
    "q": "phonemes:kw.",
    "r": "phonemes:ɹ.",
    "s": "phonemes:s.",
    "t": "phonemes:t.",
    "v": "phonemes:v.",
    "w": "phonemes:w.",
    "x": "phonemes:ks.",
    "y": "phonemes:j.",
    "z": "phonemes:z.",
}


def _load_overrides() -> dict[str, str]:
    return json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))


def test_level_1a_uses_short_english_vowel_phonemes():
    overrides = _load_overrides()

    assert {letter: overrides[letter] for letter in LEVEL_1A_ENGLISH_PHONICS} == LEVEL_1A_ENGLISH_PHONICS


def test_level_1b_uses_beginner_english_consonant_phonemes():
    overrides = _load_overrides()

    assert {letter: overrides[letter] for letter in LEVEL_1B_ENGLISH_PHONICS} == LEVEL_1B_ENGLISH_PHONICS


def test_level_1c_blend_overrides_are_unchanged():
    overrides = _load_overrides()

    assert {key: overrides[key] for key in ("ba", "be", "bi", "bo", "bu")} == {
        "ba": "bah",
        "be": "phonemes:bˈɛ.",
        "bi": "bee",
        "bo": "phonemes:bˈɔ.",
        "bu": "phonemes:bˈuː.",
    }
```

- [ ] **Step 2: Run the focused tests and verify they fail for the old Filipino-style/schwa mappings**

Run:

```bash
./.venv/bin/python -m pytest -q tests/test_pronunciation_overrides.py
```

Expected: two failures showing mismatches such as `"a": "ah"` versus `"a": "phonemes:ˈæ."` and `"b": "buh"` versus `"b": "phonemes:b."`; the level 1C protection test passes.

- [ ] **Step 3: Replace only the single-letter entries in the override file**

Replace lines 2–27 of `config/pronunciation_overrides.json` with:

```json
  "a": "phonemes:ˈæ.",
  "e": "phonemes:ˈɛ.",
  "i": "phonemes:ˈɪ.",
  "o": "phonemes:ˈɑ.",
  "u": "phonemes:ˈʌ.",
  "b": "phonemes:b.",
  "c": "phonemes:k.",
  "d": "phonemes:d.",
  "f": "phonemes:f.",
  "g": "phonemes:ɡ.",
  "h": "phonemes:h.",
  "j": "phonemes:dʒ.",
  "k": "phonemes:k.",
  "l": "phonemes:l.",
  "m": "phonemes:m.",
  "n": "phonemes:n.",
  "p": "phonemes:p.",
  "q": "phonemes:kw.",
  "r": "phonemes:ɹ.",
  "s": "phonemes:s.",
  "t": "phonemes:t.",
  "v": "phonemes:v.",
  "w": "phonemes:w.",
  "x": "phonemes:ks.",
  "y": "phonemes:j.",
  "z": "phonemes:z.",
```

Do not edit any entry from `ba` onward.

- [ ] **Step 4: Run the focused tests and verify they pass**

Run:

```bash
./.venv/bin/python -m pytest -q tests/test_pronunciation_overrides.py
```

Expected: `3 passed`.

- [ ] **Step 5: Verify the application resolves the revised values for both levels**

Run:

```bash
./.venv/bin/python scripts/audition_level.py 1a --dry-run
./.venv/bin/python scripts/audition_level.py 1b --dry-run
```

Expected: every item is labeled `[phoneme]`; level 1A prints the five short-vowel mappings and level 1B prints the twenty-one consonant mappings from Step 3.

- [ ] **Step 6: Run regression tests for pronunciation, attempt playback, and grading**

Run:

```bash
./.venv/bin/python -m pytest -q tests/test_pronunciation_overrides.py tests/test_attempt_runner.py tests/test_feedback.py tests/test_validators.py
```

Expected: all selected tests pass. No validator snapshot changes are accepted; any failure in `tests/test_validators.py` must be investigated without editing `ASR_HOMOPHONES`.

- [ ] **Step 7: Run the complete automated suite**

Run:

```bash
./.venv/bin/python -m pytest -q
```

Expected: all tests pass. If a pre-existing unrelated failure occurs, record the exact test and failure output separately; do not broaden this task to fix it.

- [ ] **Step 8: Audition representative sounds through the configured Piper model**

Run in an environment with an audio output device:

```bash
./.venv/bin/python scripts/audition_level.py 1a --engine piper
./.venv/bin/python scripts/audition_level.py 1b --engine piper
```

Expected: A, E, I, O, and U use short English vowel sounds; consonants have no added `uh`; C and G are hard, Q is /kw/, and X is /ks/. Stop and revise only the relevant IPA value if Piper renders a sound incorrectly.

- [ ] **Step 9: Confirm scope and commit**

Run:

```bash
git diff --check
git diff -- config/pronunciation_overrides.json tests/test_pronunciation_overrides.py src/ella_bot/validation/validators.py
```

Expected: no whitespace errors; the diff contains the override and test changes only; `src/ella_bot/validation/validators.py` has no task-related diff.

Commit only the two implementation files:

```bash
git add config/pronunciation_overrides.json tests/test_pronunciation_overrides.py
git commit -m "fix: use English phonics for levels 1a and 1b" -- config/pronunciation_overrides.json tests/test_pronunciation_overrides.py
```

The explicit commit pathspec is required because the working tree contains unrelated staged changes that must remain staged and must not enter this commit.
