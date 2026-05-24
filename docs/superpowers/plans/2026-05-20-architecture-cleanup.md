# E.L.L.A. Architecture Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the E.L.L.A. codebase into the layered architecture its migration plan intended (services, interfaces, components, central logging) while preserving 100% of current user-facing behavior.

**Architecture:** Pull domain/runtime logic out of the two god-objects (`EllaGUIApp`, `ReadingPromptScene`) into focused, testable modules: `services/session_manager.py` (level progression), `services/attempt_runner.py` (the read→listen→score→speak worker), `ui/pygame_gui/bot_sprite.py` and `ui/pygame_gui/components/pause_modal.py` (UI units), plus `core/constants.py`, `core/events.py`, `speech/interfaces.py`, and `speech/asr/factory.py`. A characterization test suite is built **first** so every extraction is verified against locked-in behavior.

**Tech Stack:** Python 3.9+, pygame-ce, Vosk, pytest (new), dataclasses, typing.Protocol.

**Non-breaking contract:** This is a behavior-preserving refactor. The only intentional behavior change is `config/level_pools.json` resolving via project root instead of CWD (strictly more permissive — see Phase 3). Every other task must leave the running app visually and functionally identical. The inverted-fullscreen bug (`app.py:178`) is **out of scope** because fixing it changes launch behavior; it is tracked separately.

**Verification discipline:** Never claim a task passes without running its command and reading the output. After UI-affecting phases (4, 6, 7, 8, 9, 10) run the manual smoke test in the Appendix before committing.

**Deferred (intentionally out of scope):**
- **Typed `AppConfig`** (replacing the `argparse.Namespace` threaded through `cli/main.py` → `run_gui` → `EllaGUIApp` → `build_tts`/`build_asr`). It is the most invasive non-breaking change — it touches every wiring seam at once and is risky to land without the engine/UI smoke coverage we don't yet have. Do it as a dedicated follow-up plan after this cleanup gives us the `services`/factory seams to lean on.
- **`ui/interfaces.py`** is left as-is (an empty stub). There is only one UI shell today, so a `UIShell` Protocol would be speculative (YAGNI). Revisit if a console UI path is reactivated.
- **Pi performance tuning** (gradient surface caching, 16 kHz Vosk downsampling, int8 Kokoro default, sprite pre-scaling) and the **inverted-fullscreen bug** — these change runtime/behavior characteristics and belong in a separate perf/bugfix plan, not this behavior-preserving refactor.

---

## File Structure

**New files**
- `tests/conftest.py` — pytest path setup
- `tests/test_validators.py`, `tests/test_feedback.py`, `tests/test_config.py` — characterization tests for unchanged pure logic
- `tests/test_session_manager.py`, `tests/test_constants.py`, `tests/test_asr_factory.py`, `tests/test_events.py`, `tests/test_bot_sprite.py` — tests for extracted units
- `src/ella_bot/core/constants.py` — single source of truth for level order + thresholds
- `src/ella_bot/core/events.py` — typed event dataclasses for the worker→render queue
- `src/ella_bot/services/session_manager.py` — level/progression state machine
- `src/ella_bot/services/attempt_runner.py` — attempt worker + `AttemptViewModel`
- `src/ella_bot/speech/interfaces.py` — `ASREngine` / `TTSEngine` Protocols (fills existing stub)
- `src/ella_bot/speech/asr/factory.py` — `build_asr` (fills existing stub; mirrors `tts/factory.py`)
- `src/ella_bot/ui/pygame_gui/bot_sprite.py` — bot animation state machine + rendering
- `src/ella_bot/ui/pygame_gui/components/pause_modal.py` — pause/confirm modal (fills component stubs)
- `src/ella_bot/utils/logging.py` — central `get_logger` (fills existing stub)

**Modified files**
- `src/ella_bot/ui/pygame_gui/app.py` — delegate level state to `SessionManager`, use constants
- `src/ella_bot/ui/pygame_gui/scenes/reading_prompt.py` — delegate to runner / bot_sprite / pause_modal, use session + events
- `src/ella_bot/cli/main.py` — use `build_asr` factory
- `pyproject.toml` — add `[project.optional-dependencies] dev` (pytest), declare missing runtime deps
- `.gitignore` — ignore `*.egg-info/`

**Deleted files** (verified dead in Phase 1 / 11)
- `src/ella_bot/speech/asr/base.py` (duplicate, imported nowhere)
- `src/ella_bot/validation/alignment.py`, `src/ella_bot/validation/confidence.py` (logic lives in `validators.py`)
- `src/ella_bot/utils/audio.py`, `src/ella_bot/config/base.py`, `src/ella_bot/config/defaults.py`, `src/ella_bot/services/app_service.py` (untouched `pass` stubs)
- `src/ella_bot/ui/pygame_gui/components/button.py`, `dialog.py`, `menu.py` (replaced by `pause_modal.py`)

---

## Phase 1 — Safety net & dead code

### Task 1: Add pytest and the test skeleton

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/conftest.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Add a dev dependency group to `pyproject.toml`**

Replace the `[project]` dependencies block region by appending an optional-dependencies table after the `dependencies = [...]` list (insert before `[project.scripts]`):

```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0",
]
```

- [ ] **Step 2: Create `tests/__init__.py`** (empty file)

```python
```

- [ ] **Step 3: Create `tests/conftest.py`** so `src/` layout imports resolve under pytest

```python
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
```

- [ ] **Step 4: Install the dev extra**

Run: `pip install -e ".[dev]"`
Expected: installs pytest; `pip show pytest` succeeds.

- [ ] **Step 5: Verify collection works (no tests yet)**

Run: `python -m pytest tests/ -q`
Expected: `no tests ran` (exit code 5) — collection succeeds with zero tests.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml tests/__init__.py tests/conftest.py
git commit -m "test: add pytest dev dependency and test harness skeleton"
```

### Task 2: Characterization tests for `validation/validators.py`

**Files:**
- Create: `tests/test_validators.py`

- [ ] **Step 1: Write the tests** capturing current behavior of the alignment/scoring code

```python
from ella_bot.validation.validators import (
    normalize,
    align_words,
    validate_spoken_text,
    build_highlighted_expected,
    spoken_word_confidence_map,
)


def test_normalize_lowercases_and_strips_punctuation():
    assert normalize("The CAT, sat!") == ["the", "cat", "sat"]


def test_perfect_match_is_full_accuracy():
    result = validate_spoken_text("the cat sat", "the cat sat")
    assert result.accuracy == 1.0
    assert result.wer == 0.0
    assert result.missing_words == []
    assert result.incorrect_words == []
    assert result.extra_words == []


def test_single_letter_homophone_counts_as_match():
    # "see" is a registered homophone of "c"
    result = validate_spoken_text("c", "see")
    assert result.accuracy == 1.0


def test_missing_word_is_detected():
    result = validate_spoken_text("the cat sat", "the sat")
    assert result.missing_words == ["cat"]
    assert result.wer == 1 / 3


def test_substitution_is_detected():
    result = validate_spoken_text("the cat sat", "the dog sat")
    assert result.incorrect_words == [("cat", "dog")]


def test_extra_word_is_detected():
    result = validate_spoken_text("the cat", "the cat now")
    assert result.extra_words == ["now"]


def test_highlight_brackets_non_matching_expected_words():
    result = validate_spoken_text("the cat sat", "the dog sat")
    assert build_highlighted_expected(result.alignment) == "the [cat] sat"


def test_confidence_map_pairs_tokens_to_scores():
    assert spoken_word_confidence_map(["a", "b"], [0.1, 0.9]) == {"a": 0.1, "b": 0.9}
```

- [ ] **Step 2: Run and verify all pass**

Run: `python -m pytest tests/test_validators.py -v`
Expected: 8 passed. (If any fail, the assertion encodes a wrong assumption — read the source and correct the *test* to match current behavior; do not change `validators.py`.)

- [ ] **Step 3: Commit**

```bash
git add tests/test_validators.py
git commit -m "test: characterize validators alignment and scoring behavior"
```

### Task 3: Characterization tests for `validation/feedback.py`

**Files:**
- Create: `tests/test_feedback.py`

- [ ] **Step 1: Write the tests** (randomized phrase pickers are asserted by membership, not exact string)

```python
from ella_bot.validation import feedback as fb
from ella_bot.validation.validators import validate_spoken_text


def test_score_to_level_bands():
    assert fb.score_to_level(0.99) in fb._CORRECT_PHRASES
    assert fb.score_to_level(0.80) in fb._ALMOST_PHRASES
    assert fb.score_to_level(0.10) in fb._RETRY_PHRASES


def test_build_feedback_reports_missing_and_incorrect():
    validation = validate_spoken_text("the cat sat", "the dog")
    result = fb.build_feedback(validation=validation, spoken_confidence_by_word={})
    joined = " ".join(result.detailed_messages)
    assert "Incorrect words" in joined
    assert "Missing words" in joined


def test_apply_pronunciation_overrides_replaces_whole_words_case_insensitive():
    out = fb.apply_pronunciation_overrides("The CAT sat", {"cat": "kat"})
    assert out == "The kat sat"


def test_sanitize_converts_arrow_and_colon():
    out = fb.apply_pronunciation_overrides("cat->dog: now", {})
    assert "->" not in out
    assert ":" not in out


def test_auto_pronunciation_coaching_returns_function_words_verbatim():
    assert fb.auto_pronunciation_coaching("the") == "the"


def test_build_spoken_feedback_with_coaching_starts_with_level_message():
    validation = validate_spoken_text("the cat sat", "the cat sat")
    result = fb.build_feedback(validation=validation, spoken_confidence_by_word={})
    lines = fb.build_spoken_feedback_with_coaching(
        feedback=result, overrides={}, expected_sentence="the cat sat", max_hints=2
    )
    assert lines[0] == result.level_message
    assert any("let me read the sentence" in line.lower() for line in lines)
```

- [ ] **Step 2: Run and verify all pass**

Run: `python -m pytest tests/test_feedback.py -v`
Expected: 6 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/test_feedback.py
git commit -m "test: characterize feedback and pronunciation-coaching behavior"
```

### Task 4: Characterization test for `config/app_config.py`

**Files:**
- Create: `tests/test_config.py`

- [ ] **Step 1: Write a test** that load_settings parses an ini into argparse-style defaults

```python
import configparser

from ella_bot.config import app_config


def test_load_settings_maps_ini_sections(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    ini = config_dir / "settings.ini"
    ini.write_text(
        "[System]\nstart_level = 2a\n"
        "[Speech]\nuse_mic = true\nlisten_seconds = 6\n"
        "[TTS]\naudio_feedback = true\ntts_rate = 170\n"
        "[GUI]\nfullscreen = false\ngui_width = 800\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(app_config, "get_project_root", lambda: tmp_path)

    settings = app_config.load_settings()

    assert settings["start_level"] == "2a"
    assert settings["use_mic"] is True
    assert settings["listen_seconds"] == 6
    assert settings["audio_feedback"] is True
    assert settings["tts_rate"] == 170
    assert settings["fullscreen"] is False
    assert settings["gui_width"] == 800


def test_load_settings_missing_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "get_project_root", lambda: tmp_path)
    assert app_config.load_settings() == {}
```

- [ ] **Step 2: Run and verify**

Run: `python -m pytest tests/test_config.py -v`
Expected: 2 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/test_config.py
git commit -m "test: characterize settings.ini loading"
```

### Task 5: Delete the dead duplicate `speech/asr/base.py`

**Files:**
- Delete: `src/ella_bot/speech/asr/base.py`

- [ ] **Step 1: Confirm nothing in source imports it**

Run: `grep -rn "asr.base\|asr import base\|from .base import" src/ || echo "NO SOURCE IMPORTS"`
Expected: `NO SOURCE IMPORTS` (only an egg-info reference exists, which Phase 11 removes).

- [ ] **Step 2: Delete the file**

```bash
git rm src/ella_bot/speech/asr/base.py
```

- [ ] **Step 3: Verify imports + tests still work**

Run: `python -c "import ella_bot.cli.main" && python -m pytest tests/ -q`
Expected: import OK; all tests pass.

- [ ] **Step 4: Commit**

```bash
git commit -m "refactor: remove dead duplicate speech/asr/base.py"
```

---

## Phase 2 — Centralize the level catalog

### Task 6: Create `core/constants.py` and route `app.py` through it

**Files:**
- Create: `src/ella_bot/core/constants.py`
- Create: `tests/test_constants.py`
- Modify: `src/ella_bot/ui/pygame_gui/app.py:34-49`

- [ ] **Step 1: Write the failing test**

```python
from ella_bot.core import constants


def test_level_order_is_canonical():
    assert constants.LEVEL_ORDER[0] == "1a"
    assert constants.LEVEL_ORDER[-1] == "4"
    assert len(constants.LEVEL_ORDER) == 13


def test_every_level_has_a_threshold():
    for level in constants.LEVEL_ORDER:
        assert level in constants.LEVEL_THRESHOLDS


def test_top_levels_are_unreachable_by_threshold():
    assert constants.LEVEL_THRESHOLDS["3"] == 1.01
    assert constants.LEVEL_THRESHOLDS["4"] == 1.01
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_constants.py -v`
Expected: FAIL with `ModuleNotFoundError` / `AttributeError` (constants module is an empty stub).

- [ ] **Step 3: Write `core/constants.py`** (values copied verbatim from `app.py`)

```python
from __future__ import annotations

from typing import Dict, List

LEVEL_ORDER: List[str] = [
    "1a", "1b", "1c", "1d", "1e", "1f", "1g",
    "2a", "2b", "2c", "2d", "3", "4",
]

LEVEL_THRESHOLDS: Dict[str, float] = {
    "1a": 0.85,
    "1b": 0.85,
    "1c": 0.85,
    "1d": 0.85,
    "1e": 0.85,
    "1f": 0.85,
    "1g": 0.85,
    "2a": 0.88,
    "2b": 0.90,
    "2c": 0.92,
    "2d": 0.95,
    "3": 1.01,
    "4": 1.01,
}
```

- [ ] **Step 4: Run to verify the test passes**

Run: `python -m pytest tests/test_constants.py -v`
Expected: 3 passed.

- [ ] **Step 5: Route `app.py` through the constants.** In `app.py`, add the import near the other imports (after line 6):

```python
from ella_bot.core.constants import LEVEL_ORDER, LEVEL_THRESHOLDS
```

Then replace the inline lists at `app.py:34-49` (the `self.level_order = [...]` and `self.level_thresholds = {...}` blocks) with:

```python
        self.level_order = list(LEVEL_ORDER)
        self.level_thresholds = dict(LEVEL_THRESHOLDS)
```

- [ ] **Step 6: Verify import + tests**

Run: `python -c "from ella_bot.ui.pygame_gui.app import EllaGUIApp" && python -m pytest tests/ -q`
Expected: import OK; all tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/ella_bot/core/constants.py tests/test_constants.py src/ella_bot/ui/pygame_gui/app.py
git commit -m "refactor: centralize level order and thresholds in core/constants"
```

---

## Phase 3 — Fix the `level_pools.json` path resolution

### Task 7: Resolve `level_pools.json` from project root

**Files:**
- Modify: `src/ella_bot/ui/pygame_gui/app.py:51`

**Why this is non-breaking:** Today `open("config/level_pools.json")` only works when the process CWD is the project root. Using `resolve_config_path` makes it work from the project root *and* anywhere else — strictly more permissive, no path that worked before stops working.

- [ ] **Step 1: Add the import** to `app.py` (after the constants import added in Task 6)

```python
from ella_bot.utils.file_utils import resolve_config_path
```

- [ ] **Step 2: Replace the hard-coded open** at `app.py:51`

Replace:

```python
        with open("config/level_pools.json", "r") as f:
            self.level_pools = json.load(f)
```

with:

```python
        with open(resolve_config_path("level_pools.json"), "r") as f:
            self.level_pools = json.load(f)
```

- [ ] **Step 3: Verify it loads from a non-root CWD**

Run: `cd /tmp && python -c "from ella_bot.ui.pygame_gui.app import EllaGUIApp" && cd - >/dev/null && echo OK`
Expected: `OK` (import side-effect free; the real load is exercised in the smoke test).

- [ ] **Step 4: Smoke test** — launch the app from a non-root directory per Appendix; confirm the prompt card shows a sentence.

- [ ] **Step 5: Commit**

```bash
git add src/ella_bot/ui/pygame_gui/app.py
git commit -m "fix: resolve level_pools.json relative to project root, not CWD"
```

---

## Phase 4 — Extract the session/progression state machine

### Task 8: Create `services/session_manager.py` with full test coverage

**Files:**
- Create: `src/ella_bot/services/session_manager.py`
- Create: `tests/test_session_manager.py`

- [ ] **Step 1: Write the failing tests** (a fixed pools dict, no pygame, no disk)

```python
import pytest

from ella_bot.services.session_manager import SessionManager

POOLS = {
    "1a": ["a", "the", "is"],
    "1b": ["cat", "dog"],
    "hard": ["the quick brown fox"],
}


def make_session(level="1a"):
    return SessionManager(level_pools=dict(POOLS, **{}), start_level=level)


def test_starts_on_first_sentence_of_level():
    s = SessionManager(level_pools={"1a": ["a", "the"]}, start_level="1a")
    assert s.current_level == "1a"
    assert s.expected_sentence == "a"
    assert s.level_goal == 2
    assert s.completed_in_level == 0


def test_invalid_start_level_falls_back_to_1a():
    s = SessionManager(level_pools={"1a": ["a"]}, start_level="zz")
    assert s.current_level == "1a"


def test_advance_to_next_sentence_walks_pool_and_clamps():
    s = SessionManager(level_pools={"1a": ["a", "the"]}, start_level="1a")
    s.advance_to_next_sentence()
    assert s.expected_sentence == "the"
    s.advance_to_next_sentence()  # clamp at last
    assert s.expected_sentence == "the"


def test_current_item_number_is_one_based():
    s = SessionManager(level_pools={"1a": ["a", "the"]}, start_level="1a")
    assert s.current_item_number() == 1
    s.advance_to_next_sentence()
    assert s.current_item_number() == 2


def test_display_level_name_titlecases():
    s = SessionManager(level_pools={"1a": ["a"]}, start_level="1a")
    assert s.display_level_name() == "1A"


def test_try_level_up_requires_goal_then_threshold():
    s = SessionManager(
        level_pools={"1a": ["a"], "1b": ["cat"]}, start_level="1a"
    )
    # goal not yet met -> no level up
    assert s.try_level_up(0.99) is False
    s.completed_in_level = s.level_goal
    # goal met but below 1a threshold (0.85) -> no level up
    assert s.try_level_up(0.50) is False
    # goal met and at/above threshold -> level up and reset
    assert s.try_level_up(0.90) is True
    assert s.current_level == "1b"
    assert s.completed_in_level == 0
    assert s.expected_sentence == "cat"


def test_hard_level_never_levels_up():
    s = SessionManager(level_pools=dict(POOLS), start_level="1a")
    s.current_level = "hard"
    assert s.try_level_up(1.0) is False


def test_build_start_announcement_mentions_level_item_and_sentence():
    s = SessionManager(level_pools={"1a": ["the cat"]}, start_level="1a")
    text = s.build_start_announcement()
    assert "1A" in text
    assert "item 1" in text.lower()
    assert "the cat" in text
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_session_manager.py -v`
Expected: FAIL with `ModuleNotFoundError` (stub is empty).

- [ ] **Step 3: Write `services/session_manager.py`** — logic copied verbatim from `app.py`, renamed to a clean public surface

```python
from __future__ import annotations

import json
import random
from typing import Dict, List

from ella_bot.core.constants import LEVEL_ORDER, LEVEL_THRESHOLDS
from ella_bot.utils.file_utils import resolve_config_path


class SessionManager:
    """Owns level progression, sentence selection, and announcement text."""

    def __init__(self, level_pools: Dict[str, List[str]], start_level: str = "1a") -> None:
        self.level_order = list(LEVEL_ORDER)
        self.level_thresholds = dict(LEVEL_THRESHOLDS)
        self.level_pools = level_pools

        if start_level not in self.level_order:
            start_level = "1a"
        self.current_level = start_level
        self.level_indices: Dict[str, int] = {level: 0 for level in self.level_order}
        self.expected_sentence = self.pick_sentence_for_level(self.current_level)
        self.completed_in_level = 0
        self.level_goal = len(self.level_pools.get(self.current_level, []))

    @classmethod
    def from_config_file(
        cls,
        start_level: str = "1a",
        hard_sentences: List[str] | None = None,
        seed_sentence: str = "",
    ) -> "SessionManager":
        with open(resolve_config_path("level_pools.json"), "r") as f:
            level_pools = json.load(f)
        if hard_sentences:
            level_pools["hard"] = hard_sentences
        elif seed_sentence and seed_sentence not in level_pools["hard"]:
            level_pools["hard"] = [seed_sentence]
        return cls(level_pools=level_pools, start_level=start_level)

    def current_item_number(self) -> int:
        return self.level_indices.get(self.current_level, 0) + 1

    def pick_sentence_for_level(self, level: str) -> str:
        pool = self.level_pools.get(level, [])
        if not pool:
            return ""
        if level == "hard":
            return random.choice(pool)
        index = self.level_indices.get(level, 0)
        index = max(0, min(index, len(pool) - 1))
        return pool[index]

    def display_level_name(self) -> str:
        return self.current_level.replace("-", " ").title()

    def current_pool_size(self) -> int:
        return len(self.level_pools.get(self.current_level, []))

    def advance_to_next_sentence(self) -> None:
        if self.current_level == "hard":
            self.expected_sentence = self.pick_sentence_for_level(self.current_level)
            return
        pool = self.level_pools.get(self.current_level, [])
        if not pool:
            self.expected_sentence = ""
            return
        next_index = min(self.level_indices.get(self.current_level, 0) + 1, len(pool) - 1)
        self.level_indices[self.current_level] = next_index
        self.expected_sentence = pool[next_index]

    def reset_current_level(self) -> None:
        self.completed_in_level = 0
        self.level_goal = self.current_pool_size()
        self.level_indices[self.current_level] = 0
        self.expected_sentence = self.pick_sentence_for_level(self.current_level)

    def advance_to_higher_stage(self) -> bool:
        idx = self.level_order.index(self.current_level)
        if idx + 1 >= len(self.level_order):
            return False
        self.current_level = self.level_order[idx + 1]
        self.reset_current_level()
        return True

    def try_level_up(self, accuracy: float) -> bool:
        if self.current_level == "hard":
            return False
        threshold = self.level_thresholds.get(self.current_level, 1.0)
        if self.completed_in_level < self.level_goal:
            return False
        if accuracy < threshold:
            return False
        return self.advance_to_higher_stage()

    def build_start_announcement(self) -> str:
        target_sentence = self.expected_sentence.strip() or "the next item"
        level = self.display_level_name()
        item = self.current_item_number()
        intros = [
            f"Alright! You're on the {level} level, item {item}. When you're ready, please read, {target_sentence}.",
            f"Okay, let's do this! {level} level, item {item}. Go ahead and read, {target_sentence}.",
            f"Here we go! Item {item} on the {level} level. Please read out loud, {target_sentence}.",
        ]
        return random.choice(intros)
```

- [ ] **Step 4: Run to verify all pass**

Run: `python -m pytest tests/test_session_manager.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/ella_bot/services/session_manager.py tests/test_session_manager.py
git commit -m "feat: add SessionManager with progression logic and tests"
```

### Task 9: Wire `EllaGUIApp` to delegate to `SessionManager`

**Files:**
- Modify: `src/ella_bot/ui/pygame_gui/app.py`

- [ ] **Step 1: Add the import** (after the constants/file_utils imports)

```python
from ella_bot.services.session_manager import SessionManager
```

- [ ] **Step 2: Replace the level-state construction** in `__init__`. Remove these now-redundant blocks (originally `app.py:34-64`): the `self.level_order = ...`, `self.level_thresholds = ...`, the `with open(... level_pools.json ...)` block, the `if hard_sentences / elif expected_sentence` block, the `if start_level not in self.level_order` block, and the `self.current_level / self.level_indices / self.expected_sentence / self.completed_in_level / self.level_goal` assignments. Replace all of it with:

```python
        self.session = SessionManager.from_config_file(
            start_level=start_level,
            hard_sentences=hard_sentences,
            seed_sentence=expected_sentence,
        )
```

- [ ] **Step 3: Replace the delegating helper methods.** Replace the method bodies `_current_item_number`, `_build_start_announcement`, `_pick_sentence_for_level`, `_display_level_name`, `_current_pool_size`, `_advance_to_next_sentence`, `_reset_current_level`, `_advance_to_higher_stage`, `_try_level_up` (originally `app.py:81-161`) with thin delegators, and delete the now-unused `import random`/`import json` at module top if no longer referenced (keep `json` only if still used elsewhere — it is not after this change; `random` is used by nothing else in app.py):

```python
    def _current_item_number(self) -> int:
        return self.session.current_item_number()

    def _build_start_announcement(self) -> str:
        return self.session.build_start_announcement()

    def _pick_sentence_for_level(self, level: str) -> str:
        return self.session.pick_sentence_for_level(level)

    def _display_level_name(self) -> str:
        return self.session.display_level_name()

    def _current_pool_size(self) -> int:
        return self.session.current_pool_size()

    def _advance_to_next_sentence(self) -> None:
        self.session.advance_to_next_sentence()

    def _reset_current_level(self) -> None:
        self.session.reset_current_level()

    def _advance_to_higher_stage(self) -> bool:
        return self.session.advance_to_higher_stage()

    def _try_level_up(self, accuracy: float) -> bool:
        return self.session.try_level_up(accuracy)
```

- [ ] **Step 4: Add property delegators** so existing `self.app.expected_sentence` / `completed_in_level` / `current_level` / `level_goal` reads and writes in the scene keep working unchanged. Add these inside `EllaGUIApp` (place right after `__init__`):

```python
    @property
    def expected_sentence(self) -> str:
        return self.session.expected_sentence

    @expected_sentence.setter
    def expected_sentence(self, value: str) -> None:
        self.session.expected_sentence = value

    @property
    def current_level(self) -> str:
        return self.session.current_level

    @property
    def completed_in_level(self) -> int:
        return self.session.completed_in_level

    @completed_in_level.setter
    def completed_in_level(self, value: int) -> None:
        self.session.completed_in_level = value

    @property
    def level_goal(self) -> int:
        return self.session.level_goal
```

> Note: `_prompt_font` (`app.py:102-109`) reads `self.expected_sentence` — it keeps working via the property getter, no change needed.

- [ ] **Step 5: Verify import + full suite + manual smoke**

Run: `python -c "from ella_bot.ui.pygame_gui.app import EllaGUIApp" && python -m pytest tests/ -q`
Expected: import OK; all tests pass. Then run the Appendix smoke test: complete one attempt with `--spoken` matching the prompt and confirm the item advances and the level label is correct.

- [ ] **Step 6: Commit**

```bash
git add src/ella_bot/ui/pygame_gui/app.py
git commit -m "refactor: delegate EllaGUIApp level state to SessionManager"
```

---

## Phase 5 — Speech interfaces & ASR factory

### Task 10: Define `speech/interfaces.py` Protocols

**Files:**
- Modify: `src/ella_bot/speech/interfaces.py` (currently a `pass` stub)

- [ ] **Step 1: Write the Protocols** (structural typing — no runtime change to engines)

```python
from __future__ import annotations

from typing import List, Optional, Protocol, runtime_checkable


@runtime_checkable
class ASREngine(Protocol):
    """Anything that can turn speech into a transcript with per-word scores."""

    def transcribe(self, expected_sentence: Optional[str] = None): ...


@runtime_checkable
class TTSEngine(Protocol):
    """Anything that can speak text and be interrupted."""

    def speak(self, text: str) -> None: ...

    def stop(self) -> None: ...
```

- [ ] **Step 2: Verify existing engines satisfy the Protocols at runtime**

Run:
```bash
python -c "
from ella_bot.speech.interfaces import ASREngine, TTSEngine
from ella_bot.speech.asr.simulated import SimulatedASR
from ella_bot.speech.tts.base import EspeakTTS
assert isinstance(SimulatedASR(simulated_text='hi'), ASREngine)
assert isinstance(EspeakTTS(), TTSEngine)
print('OK')
"
```
Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add src/ella_bot/speech/interfaces.py
git commit -m "feat: define ASREngine and TTSEngine Protocols"
```

### Task 11: Create `speech/asr/factory.py` and use it from the CLI

**Files:**
- Modify: `src/ella_bot/speech/asr/factory.py` (currently a `pass` stub)
- Create: `tests/test_asr_factory.py`
- Modify: `src/ella_bot/cli/main.py:128-137`

- [ ] **Step 1: Write the failing test** (model resolution stays in the CLI, so the factory takes an already-resolved path)

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_asr_factory.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_asr'`.

- [ ] **Step 3: Write `speech/asr/factory.py`**

```python
from __future__ import annotations

from typing import Optional

from ella_bot.speech.asr.simulated import SimulatedASR
from ella_bot.speech.asr.vosk_engine import VoskASR


def build_asr(
    *,
    use_mic: bool,
    spoken: str = "",
    vosk_model_path: str = "",
    sample_rate: Optional[int] = None,
    listen_seconds: int = 4,
    input_device: Optional[int] = None,
):
    """Construct the ASR engine. Mirrors speech/tts/factory.build_tts.

    Model-path resolution stays with the caller (the CLI), so this factory
    receives an already-resolved `vosk_model_path`.
    """
    if use_mic:
        return VoskASR(
            model_path=str(vosk_model_path),
            sample_rate=sample_rate,
            listen_seconds=listen_seconds,
            input_device=input_device,
        )
    return SimulatedASR(simulated_text=spoken)
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_asr_factory.py -v`
Expected: 2 passed.

- [ ] **Step 5: Use the factory from the CLI.** In `cli/main.py`, add to the imports (after line 9):

```python
from ella_bot.speech.asr.factory import build_asr as build_asr_engine
```

Replace the existing `build_asr` function (`cli/main.py:128-137`) with one that resolves the path then delegates (behavior identical):

```python
def build_asr(args: argparse.Namespace):
    model_path = ""
    if args.use_mic:
        model_path = str(resolve_existing_path(args.vosk_model, fallback_dir="models"))
    return build_asr_engine(
        use_mic=args.use_mic,
        spoken=args.spoken,
        vosk_model_path=model_path,
        sample_rate=args.sample_rate,
        listen_seconds=args.listen_seconds,
        input_device=args.input_device,
    )
```

> The unused `SimulatedASR` / `VoskASR` imports at `cli/main.py:8-9` can be removed since construction now lives in the factory.

- [ ] **Step 6: Verify import + suite**

Run: `python -c "import ella_bot.cli.main" && python -m pytest tests/ -q`
Expected: import OK; all tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/ella_bot/speech/asr/factory.py tests/test_asr_factory.py src/ella_bot/cli/main.py
git commit -m "refactor: add build_asr factory mirroring build_tts and use it from CLI"
```

---

## Phase 6 — Typed worker events

### Task 12: Create `core/events.py` and migrate the event queue

**Files:**
- Create: `src/ella_bot/core/events.py`
- Create: `tests/test_events.py`
- Modify: `src/ella_bot/ui/pygame_gui/scenes/reading_prompt.py` (producer `_attempt_worker`, `_speak_last_feedback`, consumer `_drain_event_queue`, and `update`)

**Why now:** doing this before extracting the worker (Phase 8) means the worker code that moves later is already on the typed events, avoiding a second rewrite.

- [ ] **Step 1: Write the failing test**

```python
from ella_bot.core.events import StateChanged, MessageChanged, ErrorOccurred, AttemptReady


def test_events_carry_their_payload():
    assert StateChanged("listening").state == "listening"
    assert MessageChanged("hi").message == "hi"
    assert ErrorOccurred("boom").error == "boom"
    vm = object()
    assert AttemptReady(vm).view_model is vm


def test_events_are_frozen():
    import dataclasses
    import pytest

    evt = StateChanged("idle")
    with pytest.raises(dataclasses.FrozenInstanceError):
        evt.state = "speaking"
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_events.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `core/events.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StateChanged:
    state: str


@dataclass(frozen=True)
class MessageChanged:
    message: str


@dataclass(frozen=True)
class ErrorOccurred:
    error: str


@dataclass(frozen=True)
class AttemptReady:
    view_model: Any
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_events.py -v`
Expected: 2 passed.

- [ ] **Step 5: Migrate the consumer.** In `reading_prompt.py`, add the import:

```python
from ella_bot.core.events import StateChanged, MessageChanged, ErrorOccurred, AttemptReady
```

Replace `_drain_event_queue` (`reading_prompt.py:398-415`) with:

```python
    def _drain_event_queue(self) -> None:
        while True:
            try:
                event = self.app.event_queue.get_nowait()
            except queue.Empty:
                break

            if isinstance(event, StateChanged):
                self.app.state = event.state
                self._touch_activity()
                if event.state in {"idle", "warmup", "listening", "processing", "speaking", "success", "retry"}:
                    self.app.animator.set_state(event.state, reset=True)
            elif isinstance(event, MessageChanged):
                self.app.message = event.message
            elif isinstance(event, ErrorOccurred):
                pass
            elif isinstance(event, AttemptReady):
                self.app.latest_attempt = event.view_model
```

- [ ] **Step 6: Migrate the producers.** Replace every `self.app.event_queue.put((...))` tuple in `reading_prompt.py` with the typed events. The mapping is mechanical:
  - `("state", X)` → `StateChanged(X)`
  - `("message", X)` → `MessageChanged(X)`
  - `("error", X)` → `ErrorOccurred(X)`
  - `("attempt_ready", vm)` → `AttemptReady(vm)`

This affects `update` (lines 136-137), `_attempt_worker` (239-340, 358-360), and `_speak_last_feedback` (382-390). For example, lines 239-240 become:

```python
        self.app.event_queue.put(StateChanged("speaking"))
        self.app.event_queue.put(MessageChanged(""))
```

and line 296 becomes:

```python
            self.app.event_queue.put(AttemptReady(view_model))
```

Apply the same substitution to all remaining `put((...))` calls in the file.

- [ ] **Step 7: Confirm no tuple puts remain**

Run: `grep -n 'event_queue.put((' src/ella_bot/ui/pygame_gui/scenes/reading_prompt.py || echo "ALL MIGRATED"`
Expected: `ALL MIGRATED`.

- [ ] **Step 8: Verify + smoke**

Run: `python -c "import ella_bot.ui.pygame_gui.scenes.reading_prompt" && python -m pytest tests/ -q`
Expected: import OK; tests pass. Then run the Appendix smoke test — confirm state transitions still drive the animator (bot changes between idle/listening/speaking) and feedback message text appears.

- [ ] **Step 9: Commit**

```bash
git add src/ella_bot/core/events.py tests/test_events.py src/ella_bot/ui/pygame_gui/scenes/reading_prompt.py
git commit -m "refactor: replace event-queue tuples with typed event dataclasses"
```

---

## Phase 7 — Extract the bot sprite

### Task 13: Move bot animation into `ui/pygame_gui/bot_sprite.py`

**Files:**
- Create: `src/ella_bot/ui/pygame_gui/bot_sprite.py`
- Create: `tests/test_bot_sprite.py`
- Modify: `src/ella_bot/ui/pygame_gui/scenes/reading_prompt.py`

- [ ] **Step 1: Write the failing test** for the pure state-mapping logic (no pygame surface needed)

```python
from ella_bot.ui.pygame_gui.bot_sprite import bot_state_for_app


def test_processing_maps_to_thinking():
    assert bot_state_for_app("processing") == "thinking"


def test_retry_maps_to_error():
    assert bot_state_for_app("retry") == "error"


def test_success_maps_to_idle():
    assert bot_state_for_app("success") == "idle"


def test_passthrough_states():
    for s in ("idle", "listening", "speaking", "warmup"):
        assert bot_state_for_app(s) == s


def test_unknown_defaults_to_idle():
    assert bot_state_for_app("banana") == "idle"
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_bot_sprite.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `bot_sprite.py`** — the bot fields/methods from `reading_prompt.py` moved into a focused class plus a module-level pure function

```python
from __future__ import annotations

import pygame

from ella_bot.utils.file_utils import get_project_root


def bot_state_for_app(app_state: str) -> str:
    if app_state == "processing":
        return "thinking"
    if app_state == "retry":
        return "error"
    if app_state == "success":
        return "idle"
    if app_state in {"idle", "listening", "speaking", "warmup"}:
        return app_state
    return "idle"


class BotSprite:
    """Owns the reading-prompt bot frames, animation ticking, and rendering."""

    def __init__(self) -> None:
        self.frames = self._load_frames()
        self.state = "idle"
        self.frame_index = 0
        self.last_tick_ms = 0
        self.intervals_ms = {
            "idle": 1400,
            "listening": 320,
            "speaking": 160,
            "thinking": 200,
            "warmup": 200,
            "error": 1200,
        }

    def _load_frames(self) -> dict[str, list[pygame.Surface]]:
        base = get_project_root() / "bot"
        mapping = {
            "idle": base / "idle",
            "listening": base / "listening",
            "speaking": base / "speaking",
            "thinking": base / "thinking",
            "warmup": base / "warmup",
            "error": base / "error",
        }
        frames: dict[str, list[pygame.Surface]] = {}
        for state, folder in mapping.items():
            images: list[pygame.Surface] = []
            if folder.exists():
                for image_path in sorted(folder.glob("*.png")):
                    try:
                        image = pygame.image.load(str(image_path)).convert_alpha()
                        images.append(image)
                    except Exception:
                        continue
            if images:
                frames[state] = images
        return frames

    def update(self, now_ms: int, app_state: str) -> None:
        next_state = bot_state_for_app(app_state)
        if next_state != self.state:
            self.state = next_state
            self.frame_index = 0
            self.last_tick_ms = 0

        frames = self.frames.get(self.state, [])
        if len(frames) <= 1:
            return

        if self.last_tick_ms == 0:
            self.last_tick_ms = now_ms
            return

        interval_ms = self.intervals_ms.get(self.state, 240)
        if now_ms - self.last_tick_ms >= interval_ms:
            self.frame_index = (self.frame_index + 1) % len(frames)
            self.last_tick_ms = now_ms

    def draw(self, screen: pygame.Surface, prompt_rect: pygame.Rect) -> None:
        frames = self.frames.get(self.state) or self.frames.get("idle")
        if not frames:
            return
        frame = frames[self.frame_index % len(frames)]

        max_width = int(prompt_rect.width * 0.32)
        max_height = int(prompt_rect.height * 0.42)
        frame_w = max(1, frame.get_width())
        frame_h = max(1, frame.get_height())
        scale = min(max_width / frame_w, max_height / frame_h)
        target_size = (max(1, int(frame_w * scale)), max(1, int(frame_h * scale)))
        rendered = pygame.transform.smoothscale(frame, target_size)

        overlap = int(target_size[1] * 0.28)
        target_rect = rendered.get_rect(
            bottomright=(prompt_rect.right - 26, prompt_rect.bottom + overlap - 48)
        )

        old_clip = screen.get_clip()
        try:
            screen.set_clip(prompt_rect)
            screen.blit(rendered, target_rect)
        finally:
            screen.set_clip(old_clip)
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_bot_sprite.py -v`
Expected: 5 passed.

- [ ] **Step 5: Use `BotSprite` from the scene.** In `reading_prompt.py`:
  - Add import: `from ella_bot.ui.pygame_gui.bot_sprite import BotSprite`
  - In `__init__`, replace the bot field block (`reading_prompt.py:43-54`: `self.bot_frames`, `self.bot_state`, `self.bot_frame_index`, `self.bot_last_tick_ms`, `self.bot_intervals_ms`) with: `self.bot = BotSprite()`
  - In `update` (line 129), replace `self._update_bot_animation(now_ms)` with `self.bot.update(now_ms, self.app.state)`
  - In `render` (line 221), replace `self._draw_bot(screen, inner_rect)` with `self.bot.draw(screen, inner_rect)`
  - Delete the now-unused methods `_load_bot_frames`, `_bot_state_for_app`, `_update_bot_animation`, `_draw_bot` (`reading_prompt.py:417-500`)
  - Remove the now-unused `from ella_bot.utils.file_utils import get_project_root` import if nothing else in the file uses it.

- [ ] **Step 6: Verify + smoke**

Run: `python -c "import ella_bot.ui.pygame_gui.scenes.reading_prompt" && python -m pytest tests/ -q`
Expected: import OK; tests pass. Then smoke test: confirm the bot animates and changes pose across idle → listening → thinking → speaking.

- [ ] **Step 7: Commit**

```bash
git add src/ella_bot/ui/pygame_gui/bot_sprite.py tests/test_bot_sprite.py src/ella_bot/ui/pygame_gui/scenes/reading_prompt.py
git commit -m "refactor: extract bot animation into BotSprite"
```

---

## Phase 8 — Extract the attempt runner

### Task 14: Move the worker into `services/attempt_runner.py`

**Files:**
- Create: `src/ella_bot/services/attempt_runner.py`
- Modify: `src/ella_bot/ui/pygame_gui/scenes/reading_prompt.py`
- Modify: `src/ella_bot/ui/pygame_gui/app.py` (import location of `AttemptViewModel`)

**Design:** `AttemptRunner` owns the read→listen→score→speak pipeline and the replay path. It depends on `app` (for asr/tts/session/event_queue/state flags) and a `is_paused()` callable supplied by the scene, so it carries no pygame/scene coupling beyond that. `AttemptViewModel` moves here (it is the runner's output type). The scene keeps thread lifecycle.

- [ ] **Step 1: Write `services/attempt_runner.py`** — the bodies of `_attempt_worker` and `_speak_last_feedback` moved verbatim, with two substitutions: `self.app.X` level access goes through `self.app.session`, and `self.is_paused` becomes `self._is_paused()`.

```python
from __future__ import annotations

import re
import time
import traceback
from dataclasses import dataclass
from typing import Callable

from ella_bot.core.events import StateChanged, MessageChanged, ErrorOccurred, AttemptReady
from ella_bot.validation.feedback import (
    FeedbackResult,
    build_feedback,
    build_spoken_feedback_with_coaching,
)
from ella_bot.validation.validators import (
    ValidationResult,
    validate_spoken_text,
    normalize,
    spoken_word_confidence_map,
    build_highlighted_expected,
)


@dataclass
class AttemptViewModel:
    expected_sentence: str
    spoken_sentence: str
    highlighted_expected: str
    validation: ValidationResult
    feedback: FeedbackResult


class AttemptRunner:
    """Runs one reading attempt (announce -> listen -> score -> speak feedback)."""

    def __init__(self, app, is_paused: Callable[[], bool]) -> None:
        self.app = app
        self._is_paused = is_paused
        self.error_log: list[str] = []
        self.max_errors = 5

    def run(self) -> None:
        self.app.event_queue.put(StateChanged("speaking"))
        self.app.event_queue.put(MessageChanged(""))

        if self.app.audio_feedback and self.app.tts is not None:
            try:
                if self._is_paused():
                    return
                announcement = self.app.session.build_start_announcement()
                target_item = self.app.session.expected_sentence.strip()
                target_override = self.app.pronunciation_overrides.get(target_item.lower(), target_item)
                pattern = re.compile(rf'\b{re.escape(target_item)}\b', re.IGNORECASE)
                announcement_with_overrides = pattern.sub(target_override, announcement)
                self.app.tts.speak(announcement_with_overrides)
            except Exception as exc:
                print(f"[DEBUG] Intro TTS Error: {exc}")
                self.app.event_queue.put(ErrorOccurred(str(exc)))

        self.app.event_queue.put(StateChanged("listening"))
        self.app.event_queue.put(MessageChanged(""))

        try:
            target_sentence = self.app.session.expected_sentence
            print(f"[DEBUG] Starting ASR transcription for: {target_sentence}")
            asr_result = self.app.asr.transcribe(expected_sentence=target_sentence)
            print(f"[DEBUG] Transcription finished. Result: '{asr_result.transcript}'")

            if self._is_paused():
                self.app.prompt_active = False
                self.app.event_queue.put(StateChanged("idle"))
                self.app.event_queue.put(MessageChanged(""))
                return

            self.app.prompt_active = False
            self.app.event_queue.put(StateChanged("processing"))
            self.app.event_queue.put(MessageChanged("Validating your reading..."))

            print("[DEBUG] Starting validation...")
            validation = validate_spoken_text(target_sentence, asr_result.transcript)
            print(f"\n{'='*60}")
            print(f"Expected: {target_sentence}")
            print(f"You said:  {asr_result.transcript}")
            print(f"Accuracy: {validation.accuracy:.1%}, WER: {validation.wer:.2f}")
            print(f"{'='*60}\n")
            spoken_tokens = normalize(asr_result.transcript)
            confidences = [w.confidence for w in asr_result.words][: len(spoken_tokens)]
            conf_map = spoken_word_confidence_map(spoken_tokens, confidences)
            feedback = build_feedback(validation=validation, spoken_confidence_by_word=conf_map)
            print(f"[DEBUG] Validation finished. Accuracy: {validation.accuracy:.2f}")

            highlighted = build_highlighted_expected(validation.alignment)
            view_model = AttemptViewModel(
                expected_sentence=self.app.session.expected_sentence,
                spoken_sentence=asr_result.transcript,
                highlighted_expected=highlighted,
                validation=validation,
                feedback=feedback,
            )
            self.app.event_queue.put(AttemptReady(view_model))

            if self.app.audio_feedback and self.app.tts is not None:
                try:
                    spoken_lines = build_spoken_feedback_with_coaching(
                        feedback=feedback,
                        overrides=self.app.pronunciation_overrides,
                        expected_sentence=self.app.session.expected_sentence,
                        max_hints=2,
                    )
                except Exception:
                    spoken_lines = [feedback.level_message]

                for line in spoken_lines:
                    if self._is_paused():
                        break
                    self.app.event_queue.put(StateChanged("speaking"))
                    self.app.event_queue.put(MessageChanged("Speaking feedback..."))
                    print(f"[DEBUG] Speaking: {line}")
                    self.app.tts.speak(line)
                print("[DEBUG] Audio feedback finished.")

            if feedback.level_message == "Correct!":
                self.app.session.completed_in_level = min(
                    self.app.session.completed_in_level + 1, self.app.session.level_goal
                )
                self.app.event_queue.put(StateChanged("success"))
            else:
                self.app.event_queue.put(StateChanged("retry"))

            if self.app.session.try_level_up(validation.accuracy):
                level_name = self.app.session.display_level_name()
                if self.app.audio_feedback and self.app.tts is not None:
                    if self._is_paused():
                        return
                    self.app.tts.speak(
                        f"Wow, you leveled up! Welcome to the {level_name} level. You're doing amazing!"
                    )
                self.app.event_queue.put(MessageChanged(f"Level up! You reached {level_name}!"))
            else:
                if feedback.level_message.startswith(
                    ("Excellent", "Great", "Wonderful", "That's right", "Perfect")
                ):
                    self.app.session.advance_to_next_sentence()
                    self.app.event_queue.put(MessageChanged("Nice work! Moving to the next one."))
                else:
                    self.app.event_queue.put(MessageChanged("Give it another try!"))

            time.sleep(0.6)
            self.app.event_queue.put(StateChanged("listening"))
            self.app.event_queue.put(MessageChanged(""))

        except Exception as exc:
            print("\n[!!!] WORKER THREAD CRITICAL ERROR:")
            traceback.print_exc()
            error_msg = str(exc)
            tb = traceback.format_exc()
            print(f"\n{'='*60}")
            print("ERROR DURING VALIDATION:")
            print(tb)
            print(f"{'='*60}\n")
            self.error_log.append(error_msg)
            if len(self.error_log) > self.max_errors:
                self.error_log.pop(0)

            self.app.prompt_active = False
            self.app.event_queue.put(StateChanged("retry"))
            self.app.event_queue.put(MessageChanged(f"Error: {error_msg}"))
            self.app.event_queue.put(ErrorOccurred(error_msg))
            print(f"DEBUG: Worker thread encountered error: {error_msg}")
        finally:
            self.app.prompt_active = False

    def replay(self) -> None:
        if (
            self._is_paused()
            or not self.app.audio_feedback
            or self.app.tts is None
            or self.app.latest_attempt is None
        ):
            return

        feedback = self.app.latest_attempt.feedback
        try:
            lines = build_spoken_feedback_with_coaching(
                feedback=feedback,
                overrides=self.app.pronunciation_overrides,
                expected_sentence=self.app.latest_attempt.expected_sentence,
                max_hints=2,
            )
        except Exception:
            lines = [feedback.level_message]

        for line in lines:
            self.app.event_queue.put(StateChanged("speaking"))
            self.app.event_queue.put(MessageChanged("Replaying feedback..."))
            self.app.tts.speak(line)

        if feedback.level_message == "Correct!":
            self.app.event_queue.put(StateChanged("success"))
        else:
            self.app.event_queue.put(StateChanged("retry"))
        self.app.event_queue.put(MessageChanged("Replay finished."))
```

> Note: `replay` guards on `latest_attempt is None` up front, so the inner `feedback` access is safe — this matches the original `_speak_last_feedback`, which only spawned the worker after the same guard.

- [ ] **Step 2: Rewire the scene.** In `reading_prompt.py`:
  - Replace the `AttemptViewModel` definition (`reading_prompt.py:16-22`) and its import usages by importing from the runner: `from ella_bot.services.attempt_runner import AttemptRunner, AttemptViewModel`
  - Remove the now-unused imports at the top of the file that only the worker used: `re`, the `feedback`/`validators` imports, and `FeedbackResult`/`ValidationResult` (keep `AttemptViewModel` via the new import; `pygame`, `time`, `queue`, `threading` stay).
  - In `__init__`, add: `self.runner = AttemptRunner(self.app, lambda: self.is_paused)` (place after `self.error_log`/state init; you may drop the scene's own `self.error_log`/`self.max_errors` since the runner owns them now).
  - Replace `_start_attempt` (`reading_prompt.py:228-236`) thread target:

```python
    def _start_attempt(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            return
        if self.is_paused:
            return

        self.app.prompt_active = True
        self.worker_thread = threading.Thread(target=self.runner.run, daemon=True)
        self.worker_thread.start()
```

  - Replace `_speak_last_feedback` (`reading_prompt.py:365-396`) with a thin spawner:

```python
    def _speak_last_feedback(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            return
        self.worker_thread = threading.Thread(target=self.runner.replay, daemon=True)
        self.worker_thread.start()
```

  - Delete the old `_attempt_worker` method (`reading_prompt.py:238-363`).

- [ ] **Step 3: Update `app.py`'s import of `AttemptViewModel`.** Change `app.py:12` from:

```python
from ella_bot.ui.pygame_gui.scenes.reading_prompt import ReadingPromptScene, AttemptViewModel
```

to:

```python
from ella_bot.ui.pygame_gui.scenes.reading_prompt import ReadingPromptScene
from ella_bot.services.attempt_runner import AttemptViewModel
```

- [ ] **Step 4: Verify imports + suite**

Run:
```bash
python -c "import ella_bot.ui.pygame_gui.app, ella_bot.ui.pygame_gui.scenes.reading_prompt, ella_bot.services.attempt_runner" && python -m pytest tests/ -q
```
Expected: imports OK; all tests pass.

- [ ] **Step 5: Smoke test** the full attempt loop (Appendix): announce → listen → score → speak feedback → advance, plus the `R` replay key. Confirm pausing mid-attempt still halts TTS.

- [ ] **Step 6: Commit**

```bash
git add src/ella_bot/services/attempt_runner.py src/ella_bot/ui/pygame_gui/scenes/reading_prompt.py src/ella_bot/ui/pygame_gui/app.py
git commit -m "refactor: extract attempt worker into services/AttemptRunner"
```

---

## Phase 9 — Extract the pause/confirm modal

### Task 15: Move modal rendering + hit-testing into `components/pause_modal.py`

**Files:**
- Create: `src/ella_bot/ui/pygame_gui/components/pause_modal.py`
- Modify: `src/ella_bot/ui/pygame_gui/scenes/reading_prompt.py`

**Design:** `PauseModal` owns its visibility flags, confirm action, all button rects, rendering, and a `hit_test(pos)` that returns a semantic action string. The scene maps actions to app transitions (switch scene / quit), keeping navigation control in the scene.

- [ ] **Step 1: Write `components/pause_modal.py`** — render code moved verbatim from `_draw_pause_modal`, with rects stored on `self` and a `hit_test` consolidating the click logic from `handle_event`

```python
from __future__ import annotations

from typing import Optional

import pygame


class PauseModal:
    """Pause overlay with a nested confirm dialog. Owns its own rects."""

    def __init__(self) -> None:
        self.show_pause = False
        self.show_confirm = False
        self.confirm_action: Optional[str] = None  # "main_menu" | "exit"

        self.resume_rect: Optional[pygame.Rect] = None
        self.main_menu_rect: Optional[pygame.Rect] = None
        self.exit_rect: Optional[pygame.Rect] = None
        self.close_rect: Optional[pygame.Rect] = None
        self.confirm_yes_rect: Optional[pygame.Rect] = None
        self.confirm_no_rect: Optional[pygame.Rect] = None

    @property
    def visible(self) -> bool:
        return self.show_pause or self.show_confirm

    def open(self) -> None:
        self.show_pause = True

    def close(self) -> None:
        self.show_pause = False
        self.show_confirm = False
        self.confirm_action = None

    def hit_test(self, pos) -> Optional[str]:
        """Return a semantic action for a left-click, or None.

        Actions: "resume", "ask_main_menu", "ask_exit",
                 "confirm_yes", "confirm_no", "close".
        """
        if self.show_confirm:
            if self.close_rect and self.close_rect.collidepoint(pos):
                return "close"
            if self.confirm_yes_rect and self.confirm_yes_rect.collidepoint(pos):
                return "confirm_yes"
            if self.confirm_no_rect and self.confirm_no_rect.collidepoint(pos):
                return "confirm_no"
            return "consumed"

        if self.show_pause:
            if self.close_rect and self.close_rect.collidepoint(pos):
                return "resume"
            if self.resume_rect and self.resume_rect.collidepoint(pos):
                return "resume"
            if self.main_menu_rect and self.main_menu_rect.collidepoint(pos):
                return "ask_main_menu"
            if self.exit_rect and self.exit_rect.collidepoint(pos):
                return "ask_exit"
            return "consumed"

        return None

    def render(self, screen, font_body, font_small, prompt_rect) -> None:
        if not self.visible:
            return

        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        screen.blit(overlay, (0, 0))

        dialog_w = int(prompt_rect.width * 0.55)
        dialog_h = int(prompt_rect.height * 0.50)
        dialog_x = prompt_rect.centerx - dialog_w // 2
        dialog_y = prompt_rect.centery - dialog_h // 2
        dialog_rect = pygame.Rect(dialog_x, dialog_y, dialog_w, dialog_h)

        header_height = 92
        header_rect = pygame.Rect(dialog_rect.left, dialog_rect.top, dialog_rect.width, header_height)
        body_rect = pygame.Rect(
            dialog_rect.left, dialog_rect.top + header_height, dialog_rect.width, dialog_rect.height - header_height
        )

        outer_bg = (255, 240, 245)
        header_bg = (255, 217, 228)
        pygame.draw.rect(screen, outer_bg, dialog_rect, border_radius=24)
        pygame.draw.rect(screen, header_bg, header_rect, border_radius=24)
        pygame.draw.rect(screen, header_bg, header_rect, width=0, border_radius=24)
        pygame.draw.rect(screen, (255, 255, 255), body_rect, border_radius=24)
        pygame.draw.rect(screen, (230, 127, 159), dialog_rect, width=6, border_radius=24)

        title_text = "Paused" if not self.show_confirm else "Confirm"
        title_surf = font_body.render(title_text, True, (40, 40, 40))
        title_rect = title_surf.get_rect(topleft=(dialog_rect.left + 24, dialog_rect.top + 24))
        screen.blit(title_surf, title_rect)

        button_w = int(dialog_rect.width * 0.82)
        close_size = 48
        close_rect = pygame.Rect(dialog_rect.right - close_size - 20, dialog_rect.top + 22, close_size, close_size)
        self.close_rect = close_rect
        pygame.draw.rect(screen, (255, 255, 255), close_rect, border_radius=14)
        pygame.draw.rect(screen, (230, 127, 159), close_rect, width=4, border_radius=14)
        pygame.draw.line(
            screen, (230, 127, 159),
            (close_rect.left + 14, close_rect.top + 14), (close_rect.right - 14, close_rect.bottom - 14), width=4,
        )
        pygame.draw.line(
            screen, (230, 127, 159),
            (close_rect.left + 14, close_rect.bottom - 14), (close_rect.right - 14, close_rect.top + 14), width=4,
        )
        left_x = dialog_rect.centerx - button_w // 2

        if self.show_confirm:
            msg = "Return to main menu?" if self.confirm_action == "main_menu" else "Exit the app?"
            msg_surf = font_small.render(msg, True, (50, 50, 50))
            msg_rect = msg_surf.get_rect(center=(dialog_rect.centerx, header_rect.bottom + 44))
            screen.blit(msg_surf, msg_rect)

            button_h = 72
            yes_rect = pygame.Rect(left_x, header_rect.bottom + 88, button_w, button_h)
            no_rect = pygame.Rect(left_x, header_rect.bottom + 88 + button_h + 16, button_w, button_h)
            self.confirm_yes_rect = yes_rect
            self.confirm_no_rect = no_rect
            self.main_menu_rect = None
            self.exit_rect = None

            shadow = pygame.Surface((button_w, button_h), pygame.SRCALPHA)
            shadow.fill((0, 0, 0, 40))
            screen.blit(shadow, (yes_rect.left, yes_rect.top + 6))
            screen.blit(shadow, (no_rect.left, no_rect.top + 6))

            pygame.draw.rect(screen, (255, 255, 255), yes_rect, border_radius=18)
            pygame.draw.rect(screen, (230, 127, 159), yes_rect, width=4, border_radius=18)
            yes_text = font_small.render("Yes", True, (40, 40, 40))
            screen.blit(yes_text, yes_text.get_rect(center=yes_rect.center))

            pygame.draw.rect(screen, (255, 255, 255), no_rect, border_radius=18)
            pygame.draw.rect(screen, (230, 127, 159), no_rect, width=4, border_radius=18)
            no_text = font_small.render("No", True, (40, 40, 40))
            screen.blit(no_text, no_text.get_rect(center=no_rect.center))
            return

        button_h = 78
        stack_gap = 20
        resume_rect = pygame.Rect(left_x, header_rect.bottom + 40, button_w, button_h)
        main_rect = pygame.Rect(left_x, resume_rect.bottom + stack_gap, button_w, button_h)
        exit_rect = pygame.Rect(left_x, main_rect.bottom + stack_gap, button_w, button_h)

        self.resume_rect = resume_rect
        self.main_menu_rect = main_rect
        self.exit_rect = exit_rect
        self.confirm_yes_rect = None
        self.confirm_no_rect = None

        shadow = pygame.Surface((button_w, button_h), pygame.SRCALPHA)
        shadow.fill((0, 0, 0, 28))
        screen.blit(shadow, (resume_rect.left, resume_rect.top + 6))
        screen.blit(shadow, (main_rect.left, main_rect.top + 6))
        screen.blit(shadow, (exit_rect.left, exit_rect.top + 6))

        for rect, label in ((resume_rect, "Resume"), (main_rect, "Main Menu"), (exit_rect, "Exit")):
            pygame.draw.rect(screen, (255, 255, 255), rect, border_radius=22)
            pygame.draw.rect(screen, (230, 127, 159), rect, width=4, border_radius=22)
            text = font_small.render(label, True, (40, 40, 40))
            screen.blit(text, text.get_rect(center=rect.center))
```

- [ ] **Step 2: Rewire the scene to use `PauseModal`.** In `reading_prompt.py`:
  - Add import: `from ella_bot.ui.pygame_gui.components.pause_modal import PauseModal`
  - In `__init__`, remove the modal flag/rect fields (`reading_prompt.py:32-42`: `show_pause_modal`, `show_confirm_modal`, `confirm_action`, `pause_*_rect`, `confirm_*_rect`) and add `self.modal = PauseModal()`. Keep `self.is_paused`, `self.menu_button_rect`.
  - Replace `handle_event`'s modal branches. The mouse-button handler becomes:

```python
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.modal.visible:
                action = self.modal.hit_test(event.pos)
                if action == "close":
                    self.modal.show_confirm = False if self.modal.show_confirm else self.modal.show_confirm
                    if not self.modal.show_confirm:
                        self._set_paused(False)
                    return
                if action == "resume":
                    self._set_paused(False)
                    return
                if action == "ask_main_menu":
                    self.modal.show_confirm = True
                    self.modal.confirm_action = "main_menu"
                    return
                if action == "ask_exit":
                    self.modal.show_confirm = True
                    self.modal.confirm_action = "exit"
                    return
                if action == "confirm_yes":
                    if self.modal.confirm_action == "main_menu":
                        self.modal.close()
                        self.is_paused = False
                        self.app.switch_scene("main_menu")
                    elif self.modal.confirm_action == "exit":
                        self.app.running = False
                    return
                if action == "confirm_no":
                    self.modal.show_confirm = False
                    self.modal.confirm_action = None
                    return
                return  # "consumed"

            if self.menu_button_rect and self.menu_button_rect.collidepoint(event.pos):
                self._set_paused(True)
                return

            self._start_attempt()
```

> Behavior note: the original close (X) button inside the confirm dialog dismissed only the confirm and returned to pause; inside pause it resumed. To preserve that exactly, handle "close" by checking confirm first:

```python
                if action == "close":
                    if self.modal.show_confirm:
                        self.modal.show_confirm = False
                        self.modal.confirm_action = None
                    else:
                        self._set_paused(False)
                    return
```

Use this second form (it matches the original `pause_close_rect` behavior in both states).

  - In the `KEYDOWN` branch, replace `if self.show_pause_modal or self.show_confirm_modal:` with `if self.modal.visible:`.
  - In `update` (line 128 and 131), replace `if not self.show_pause_modal and not self.show_confirm_modal:` with `if not self.modal.visible:` and `if self.show_pause_modal or self.show_confirm_modal:` with `if self.modal.visible:`.
  - In `render`, replace the final `self._draw_pause_modal(screen, inner_rect)` (line 226) with:

```python
        self.modal.render(screen, self.app.font_body, self.app.font_small, inner_rect)
```

  - Delete the `_draw_pause_modal` method (`reading_prompt.py:502-618`).
  - Update `_set_paused` (`reading_prompt.py:620-633`) to drive the modal:

```python
    def _set_paused(self, paused: bool) -> None:
        self.is_paused = paused
        if paused:
            self.modal.open()
        else:
            self.modal.close()
        if paused and self.app.tts is not None:
            try:
                self.app.tts.stop()
            except Exception:
                pass
        self.app.prompt_active = False
        self.app.event_queue.put(StateChanged("idle"))
        self.app.event_queue.put(MessageChanged(""))
```

  - In `on_enter` (`reading_prompt.py:56-65`), replace the `self.show_pause_modal = False` / `self.show_confirm_modal = False` / `self.confirm_action = None` lines with `self.modal.close()`.

- [ ] **Step 3: Verify import + suite**

Run: `python -c "import ella_bot.ui.pygame_gui.scenes.reading_prompt" && python -m pytest tests/ -q`
Expected: import OK; tests pass.

- [ ] **Step 4: Smoke test the modal thoroughly** (Appendix modal checklist): open pause via the hamburger button; Resume; the X closes pause; Main Menu → confirm Yes returns to menu, No/X dismisses confirm; Exit → confirm Yes quits. Confirm TTS stops when pausing mid-feedback.

- [ ] **Step 5: Commit**

```bash
git add src/ella_bot/ui/pygame_gui/components/pause_modal.py src/ella_bot/ui/pygame_gui/scenes/reading_prompt.py
git commit -m "refactor: extract pause/confirm overlay into PauseModal component"
```

---

## Phase 10 — Central logging

### Task 16: Add `utils/logging.py` and replace `print()` in the hot modules

**Files:**
- Modify: `src/ella_bot/utils/logging.py` (currently a `pass` stub)
- Modify: `src/ella_bot/services/attempt_runner.py`
- Modify: `src/ella_bot/speech/asr/vosk_engine.py`

**Scope note:** Replace the `print()` calls in the two modules that spam during the attempt loop (runner, vosk). Leave `print()` in the TTS factory and CLI error handler for a follow-up — they are one-shot and low-noise. This keeps the task bounded and reviewable.

- [ ] **Step 1: Write `utils/logging.py`**

```python
from __future__ import annotations

import logging

_CONFIGURED = False


def get_logger(name: str) -> logging.Logger:
    """Return a module logger, configuring root formatting once."""
    global _CONFIGURED
    if not _CONFIGURED:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
        _CONFIGURED = True
    return logging.getLogger(name)
```

- [ ] **Step 2: Verify it works**

Run: `python -c "from ella_bot.utils.logging import get_logger; get_logger('t').info('hi')"`
Expected: a formatted `INFO ... t: hi` line on stderr.

- [ ] **Step 3: Use it in `attempt_runner.py`.** Add at top: `from ella_bot.utils.logging import get_logger` and module-level `logger = get_logger(__name__)`. Replace the `print(...)` debug/error lines with `logger.debug(...)` (the `[DEBUG] ...` lines) and `logger.error(...)` / `logger.exception(...)` for the crash block. Keep message content identical minus the `[DEBUG]` prefix. For the traceback block, replace the manual `traceback.print_exc()` + `print(tb)` with `logger.exception("Attempt worker crashed")`.

- [ ] **Step 4: Use it in `vosk_engine.py`.** Add the same import + `logger`. Replace the `print(...)` status/recording lines with `logger.info(...)` / `logger.debug(...)`. Keep the `RuntimeError` raising path unchanged (it does not print).

- [ ] **Step 5: Verify imports + suite**

Run: `python -c "import ella_bot.services.attempt_runner, ella_bot.speech.asr.vosk_engine" && python -m pytest tests/ -q`
Expected: imports OK; tests pass.

- [ ] **Step 6: Smoke test** one attempt; confirm log lines now carry timestamps/levels and the app behaves identically.

- [ ] **Step 7: Commit**

```bash
git add src/ella_bot/utils/logging.py src/ella_bot/services/attempt_runner.py src/ella_bot/speech/asr/vosk_engine.py
git commit -m "refactor: route attempt-loop diagnostics through central logger"
```

---

## Phase 11 — Final dead-code & packaging cleanup

### Task 17: Remove untouched placeholder stubs and unused component stubs

**Files:**
- Delete: `src/ella_bot/validation/alignment.py`, `src/ella_bot/validation/confidence.py`
- Delete: `src/ella_bot/utils/audio.py`, `src/ella_bot/config/base.py`, `src/ella_bot/config/defaults.py`, `src/ella_bot/services/app_service.py`
- Delete: `src/ella_bot/ui/pygame_gui/components/button.py`, `dialog.py`, `menu.py`

- [ ] **Step 1: Confirm each is an untouched stub and is imported nowhere**

Run:
```bash
for f in validation/alignment validation/confidence utils/audio config/base config/defaults services/app_service ui/pygame_gui/components/button ui/pygame_gui/components/dialog ui/pygame_gui/components/menu; do
  mod="ella_bot.${f//\//.}"
  echo "== $f =="
  grep -rn "import ${f##*/}\|$mod" src/ | grep -v "src/ella_bot/$f.py" || echo "  no imports"
done
```
Expected: every entry prints `no imports`.

- [ ] **Step 2: Delete the stubs**

```bash
git rm src/ella_bot/validation/alignment.py src/ella_bot/validation/confidence.py \
       src/ella_bot/utils/audio.py src/ella_bot/config/base.py src/ella_bot/config/defaults.py \
       src/ella_bot/services/app_service.py \
       src/ella_bot/ui/pygame_gui/components/button.py \
       src/ella_bot/ui/pygame_gui/components/dialog.py \
       src/ella_bot/ui/pygame_gui/components/menu.py
```

- [ ] **Step 3: Verify the whole package still imports and tests pass**

Run: `python -c "import ella_bot.cli.main" && python -m pytest tests/ -q`
Expected: import OK; all tests pass.

- [ ] **Step 4: Commit**

```bash
git commit -m "refactor: delete untouched placeholder and unused component stubs"
```

### Task 18: Stop tracking build artifacts and declare missing runtime deps

**Files:**
- Modify: `.gitignore`
- Modify: `pyproject.toml`
- Delete (from tracking): `src/ella_bot.egg-info/`

- [ ] **Step 1: Add the egg-info ignore.** Append to `.gitignore` (create it if absent):

```
*.egg-info/
__pycache__/
.pytest_cache/
```

- [ ] **Step 2: Untrack the egg-info directory**

Run: `git rm -r --cached src/ella_bot.egg-info`
Expected: removes it from the index without deleting the working copy.

- [ ] **Step 3: Declare the runtime deps that the code actually imports.** In `pyproject.toml`, update the `dependencies` list so a fresh install does not fail. Replace the current list with:

```toml
dependencies = [
    "vosk",
    "sounddevice",
    "pygame-ce",
    "pyttsx3",
    "pronouncing",
    "numpy",
]
```

> `kokoro-onnx` stays optional (large, platform-sensitive) — leave it for a dedicated `[project.optional-dependencies] kokoro` group in a future change; do not add it to core deps here.

- [ ] **Step 4: Verify a clean editable install still resolves**

Run: `pip install -e ".[dev]" && python -m pytest tests/ -q`
Expected: install succeeds; all tests pass.

- [ ] **Step 5: Commit**

```bash
git add .gitignore pyproject.toml
git commit -m "chore: ignore build artifacts and declare numpy runtime dependency"
```

---

## Appendix — Manual smoke test

Because the UI and threading paths are not unit-tested, run this after every UI-affecting phase (4, 6, 7, 8, 9, 10). Use the simulated ASR so the run is deterministic and offline.

**Launch (from a non-project-root directory to also exercise Task 7):**

```bash
cd /tmp && ella-bot --gui --gui-width 1280 --gui-height 720 \
  --audio-feedback --tts-engine say --spoken "the"
```

(Use `--tts-engine say` on macOS; on Linux use `espeak`. Drop `--audio-feedback` to test the silent path. `--spoken "the"` makes the simulated reader say "the" — set it to match the level 1A first item for a "Correct!" path, or something wrong for the retry path.)

**Golden path checklist:**
- [ ] Intro scene appears, then Main Menu, then Reading Prompt (the prompt card shows a sentence).
- [ ] Click the card (or press Space): bot goes idle → listening → thinking → speaking; feedback message text appears.
- [ ] A correct reading advances the item number / level label; a wrong reading shows "Give it another try!".
- [ ] Press `R`: last feedback replays.

**Modal checklist (Phase 9):**
- [ ] Hamburger button opens the Paused overlay; background dims.
- [ ] Resume and the X both close the overlay and resume.
- [ ] Main Menu opens the confirm dialog; Yes returns to the menu; No and X dismiss only the confirm.
- [ ] Exit opens the confirm dialog; Yes quits the app.
- [ ] Pausing while feedback is speaking stops the audio.

**Regression watch:** the level label, item number, prompt font sizing, bot clipping at the card edge, and gradient background should look identical to `main`.
```