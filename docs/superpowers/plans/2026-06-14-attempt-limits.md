# Attempt Limits Per Item by Tier — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Limit reading attempts per item to 1 on Tier 1 levels (1a–1g) and 3 on Tier 2–4 levels (2a–4); exhausted items advance automatically with an encouragement phrase.

**Architecture:** A `max_attempts_for_level` helper in `constants.py` drives the limit. `AttemptRunner` tracks per-item attempt count using two instance variables; when the limit is hit the item is treated as exhausted — `completed_in_level` still increments so the sublevel can finish, an encouragement phrase is spoken, and the session advances.

**Tech Stack:** Python 3.13, pytest (`.venv/bin/python -m pytest`), no new dependencies.

---

### Task 1: Add `max_attempts_for_level` to `constants.py`

**Files:**
- Modify: `src/ella_bot/core/constants.py`
- Test: `tests/test_constants.py`

- [ ] **Step 1: Write the failing test**

Add to the bottom of `tests/test_constants.py`:

```python
def test_max_attempts_for_level_tier1():
    for level in ["1a", "1b", "1c", "1d", "1e", "1f", "1g"]:
        assert constants.max_attempts_for_level(level) == 1


def test_max_attempts_for_level_tier2_to_4():
    for level in ["2a", "2b", "2c", "2d", "3", "4"]:
        assert constants.max_attempts_for_level(level) == 3


def test_max_attempts_for_level_unknown_defaults_to_3():
    assert constants.max_attempts_for_level("hard") == 3
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_constants.py::test_max_attempts_for_level_tier1 -v
```

Expected: `FAILED` — `AttributeError: module 'ella_bot.core.constants' has no attribute 'max_attempts_for_level'`

- [ ] **Step 3: Add helper to `constants.py`**

Add at the bottom of `src/ella_bot/core/constants.py`, after `tier_of`:

```python
def max_attempts_for_level(level: str) -> int:
    """Return the maximum attempts allowed per item for the given level."""
    return 1 if tier_of(level) == 1 else 3
```

- [ ] **Step 4: Run all three new tests**

```bash
.venv/bin/python -m pytest tests/test_constants.py -v
```

Expected: all 9 tests `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add src/ella_bot/core/constants.py tests/test_constants.py
git commit -m "feat: add max_attempts_for_level helper to constants"
```

---

### Task 2: Implement attempt tracking and exhaustion in `AttemptRunner`

**Files:**
- Modify: `src/ella_bot/services/attempt_runner.py`
- Test: `tests/test_attempt_runner.py`

- [ ] **Step 1: Write the failing tests**

Add to the bottom of `tests/test_attempt_runner.py`:

```python
import random as _random_mod


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
    """After exhaustion on item 1, item 2 gets a fresh 3-attempt budget."""
    call_count = {"n": 0}

    def alternating_validation(exp, got):
        call_count["n"] += 1
        # items 1-3 wrong (exhaust item one), item 4 wrong (first attempt on item two)
        return _FakeWrongValidation()

    monkeypatch.setattr(runner_mod, "validate_spoken_text", alternating_validation)
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_attempt_runner.py -v -k "tier1 or tier2"
```

Expected: 5 tests `FAILED` — `assert app.session.expected_sentence == "sentence two"` (and similar) because no limit logic exists yet.

- [ ] **Step 3: Add import and module-level constant to `attempt_runner.py`**

At the top of `src/ella_bot/services/attempt_runner.py`, add `import random` to the existing imports block and add the import from constants:

```python
from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass
from typing import Callable

from ella_bot.core.constants import max_attempts_for_level
from ella_bot.core.events import (
    StateChanged, MessageChanged, ErrorOccurred, AttemptReady,
    SubLevelCompleted, SessionCompleted,
)
from ella_bot.utils.logging import get_logger
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

logger = get_logger(__name__)

_EXHAUSTION_PHRASES = [
    "That's okay! Keep going, you're doing great!",
    "Nice try! Let's move to the next one.",
    "Don't worry, we'll come back to tricky ones. Keep it up!",
    "Good effort! Moving on.",
    "That one was tough! You're still doing amazing.",
]
```

- [ ] **Step 4: Add instance variables to `AttemptRunner.__init__`**

In `src/ella_bot/services/attempt_runner.py`, update `__init__`:

```python
def __init__(self, app, is_paused: Callable[[], bool]) -> None:
    self.app = app
    self._is_paused = is_paused
    self.error_log: list[str] = []
    self.max_errors = 5
    self._item_attempt_count: int = 0
    self._current_item_sentence: str = ""
```

- [ ] **Step 5: Update the scoring block in `run()`**

Replace the block starting at `session = self.app.session` through the end of the `if correct: ... else: "Give it another try!"` section. The full replacement (lines 147–208 of the current file) is:

```python
            session = self.app.session
            evaluation = self.app.evaluation
            level = session.current_level
            correct = validation.accuracy >= 0.95

            # Per-item attempt tracking — reset counter when the sentence changes
            if session.expected_sentence != self._current_item_sentence:
                self._current_item_sentence = session.expected_sentence
                self._item_attempt_count = 0
            self._item_attempt_count += 1
            max_attempts = max_attempts_for_level(level)
            exhausted = not correct and self._item_attempt_count >= max_attempts

            evaluation.record_attempt(
                level=level,
                item=session.current_item_number(),
                expected=session.expected_sentence,
                heard=asr_result.transcript,
                accuracy=validation.accuracy,
                wer=validation.wer,
                correct=correct,
            )

            if correct or exhausted:
                session.completed_in_level = min(
                    session.completed_in_level + 1, session.level_goal
                )
                self._item_attempt_count = 0

            if correct:
                self.app.event_queue.put(StateChanged("success"))
            else:
                self.app.event_queue.put(StateChanged("retry"))

            if session.current_sublevel_complete():
                tier = session.tier_of(level)
                sub_result = evaluation.finish_sublevel(level)
                if session.is_last_sublevel_of_tier(level):
                    tier_result = evaluation.finish_tier(tier)
                    if session.is_last_tier(tier):
                        cumulative = evaluation.finish_session()
                        if self.app.audio_feedback and self.app.tts is not None and not self._is_paused():
                            self.app.event_queue.put(StateChanged("speaking"))
                            self.app.tts.speak(
                                "Incredible! You finished every level. Let's see how you did!"
                            )
                            self.app.event_queue.put(StateChanged("idle"))
                        self.app.event_queue.put(SessionCompleted(cumulative))
                    else:
                        if self.app.audio_feedback and self.app.tts is not None and not self._is_paused():
                            self.app.event_queue.put(StateChanged("speaking"))
                            self.app.tts.speak(
                                f"Wow, you finished Level {tier}! You're doing amazing!"
                            )
                            self.app.event_queue.put(StateChanged("idle"))
                        self.app.event_queue.put(SubLevelCompleted(tier_result, "tier"))
                else:
                    if self.app.audio_feedback and self.app.tts is not None and not self._is_paused():
                        self.app.event_queue.put(StateChanged("speaking"))
                        self.app.tts.speak("Great job! Let's see how you did!")
                        self.app.event_queue.put(StateChanged("idle"))
                    self.app.event_queue.put(SubLevelCompleted(sub_result, "sublevel"))
                return

            if correct:
                session.advance_to_next_sentence()
                self.app.event_queue.put(MessageChanged("Nice work! Moving to the next one."))
            elif exhausted:
                if self.app.audio_feedback and self.app.tts is not None and not self._is_paused():
                    self.app.event_queue.put(StateChanged("speaking"))
                    self.app.tts.speak(random.choice(_EXHAUSTION_PHRASES))
                    self.app.event_queue.put(StateChanged("idle"))
                session.advance_to_next_sentence()
                self.app.event_queue.put(MessageChanged("Let's move on."))
            else:
                self.app.event_queue.put(MessageChanged("Give it another try!"))

            time.sleep(0.6)
            self.app.event_queue.put(StateChanged("listening"))
            self.app.event_queue.put(MessageChanged(""))
```

- [ ] **Step 6: Run all attempt_runner tests**

```bash
.venv/bin/python -m pytest tests/test_attempt_runner.py -v
```

Expected: all 6 tests `PASSED`.

- [ ] **Step 7: Run full test suite to check for regressions**

```bash
.venv/bin/python -m pytest tests/ -v --ignore=tests/test_gui_e2e.py 2>&1 | tail -30
```

Expected: all tests `PASSED` (excluding the GUI e2e test which requires a display).

- [ ] **Step 8: Commit**

```bash
git add src/ella_bot/services/attempt_runner.py tests/test_attempt_runner.py
git commit -m "feat: limit attempts per item by tier (1 for tier 1, 3 for tier 2-4)"
```
