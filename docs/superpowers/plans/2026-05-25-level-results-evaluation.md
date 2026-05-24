# Level Results & Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-sub-level and per-tier completion/results screens with an A–F fluency evaluation, gated progression, and durable JSONL session logging that survives a Raspberry Pi 5 power-off.

**Architecture:** A new pygame-free `EvaluationService` owns attempt accumulation, scoring (fluency + A–F rating + pass/fail), and append-only JSONL persistence. `SessionManager` gains pure tier-boundary helpers. `AttemptRunner` records every attempt and, at sub-level/tier boundaries, posts new events that route the GUI to a reusable `ResultsScene` (sub-level + tier kinds) or a `FinalEvaluationScene`. Progression that used to auto-advance silently is now user-triggered via a "Next" button.

**Tech Stack:** Python 3, pygame (GUI), pytest. Source under `src/ella_bot/`, tests under `tests/`. Tests put `src/` on `sys.path` via `tests/conftest.py`. Run tests with `python -m pytest`.

**Spec:** `docs/superpowers/specs/2026-05-25-level-results-evaluation-design.md`

---

## File Structure

| File | Responsibility |
|------|----------------|
| `src/ella_bot/core/constants.py` | **Modify** — add `TIER_SUBLEVELS` dict + `tier_of()` pure helper |
| `src/ella_bot/services/evaluation.py` | **New** — result dataclasses, `rating_for()`, `EvaluationService` (accumulate, score, persist) |
| `src/ella_bot/services/session_manager.py` | **Modify** — tier helpers; stop calling `try_level_up` in the runtime path |
| `src/ella_bot/core/events.py` | **Modify** — add `SubLevelCompleted`, `SessionCompleted` |
| `src/ella_bot/services/attempt_runner.py` | **Modify** — record attempts; detect boundaries; post new events |
| `src/ella_bot/ui/pygame_gui/config.py` | **Modify** — add `session_log_path`, `pass_bar` to `GUIConfig` |
| `src/ella_bot/ui/pygame_gui/app.py` | **Modify** — build `EvaluationService`; register `results` + `final_eval` scenes; hold `latest_result`/`latest_result_kind` |
| `src/ella_bot/ui/pygame_gui/scenes/results.py` | **New** — `ResultsScene` (sublevel + tier) |
| `src/ella_bot/ui/pygame_gui/scenes/final_eval.py` | **New** — `FinalEvaluationScene` |
| `src/ella_bot/ui/pygame_gui/scenes/reading_prompt.py` | **Modify** — handle new events in `_drain_event_queue` |
| `src/ella_bot/config/app_config.py` | **Modify** — parse `[System] session_log` |
| `src/ella_bot/cli/main.py` | **Modify** — `--session-log` arg; resolve + pass to `GUIConfig` |
| `config/settings.ini` | **Modify** — add `session_log` under `[System]` |
| `tests/test_constants.py` | **Modify** — tier mapping tests |
| `tests/test_evaluation.py` | **New** — scoring + persistence tests |
| `tests/test_session_manager.py` | **Modify** — tier-helper tests |
| `tests/test_events.py` | **Modify** — new event payload tests |
| `tests/test_results_scene.py` | **New** — `ResultsScene` handler tests |
| `tests/test_final_eval_scene.py` | **New** — `FinalEvaluationScene` handler tests |
| `tests/test_attempt_runner.py` | **New** — boundary-detection integration test |

---

## Task 1: Tier constants + `tier_of` helper

**Files:**
- Modify: `src/ella_bot/core/constants.py`
- Test: `tests/test_constants.py`

- [ ] **Step 1: Write the failing tests** — append to `tests/test_constants.py`

```python
def test_tier_sublevels_cover_all_levels_once():
    seen = []
    for subs in constants.TIER_SUBLEVELS.values():
        seen.extend(subs)
    assert seen == list(constants.LEVEL_ORDER)
    assert sorted(constants.TIER_SUBLEVELS.keys()) == [1, 2, 3, 4]
    assert constants.TIER_SUBLEVELS[1] == ["1a", "1b", "1c", "1d", "1e", "1f", "1g"]


def test_tier_of_maps_each_level_to_its_tier():
    assert constants.tier_of("1a") == 1
    assert constants.tier_of("1g") == 1
    assert constants.tier_of("2c") == 2
    assert constants.tier_of("3") == 3
    assert constants.tier_of("4") == 4


def test_tier_of_returns_zero_for_unknown_level():
    assert constants.tier_of("hard") == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_constants.py -v`
Expected: FAIL with `AttributeError: module ... has no attribute 'TIER_SUBLEVELS'`

- [ ] **Step 3: Implement** — append to `src/ella_bot/core/constants.py`

```python
TIER_SUBLEVELS: Dict[int, List[str]] = {
    1: ["1a", "1b", "1c", "1d", "1e", "1f", "1g"],
    2: ["2a", "2b", "2c", "2d"],
    3: ["3"],
    4: ["4"],
}


def tier_of(level: str) -> int:
    """Return the tier number (1-4) a sub-level belongs to, or 0 if unknown."""
    for tier, subs in TIER_SUBLEVELS.items():
        if level in subs:
            return tier
    return 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_constants.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add src/ella_bot/core/constants.py tests/test_constants.py
git commit -m "feat: add tier groupings and tier_of helper to constants"
```

---

## Task 2: EvaluationService — dataclasses, `rating_for`, `record_attempt`, `finish_sublevel`

**Files:**
- Create: `src/ella_bot/services/evaluation.py`
- Test: `tests/test_evaluation.py`

- [ ] **Step 1: Write the failing tests** — create `tests/test_evaluation.py`

```python
import json
from pathlib import Path

import pytest

from ella_bot.services.evaluation import EvaluationService, rating_for


def make_service(tmp_path) -> EvaluationService:
    return EvaluationService(log_path=tmp_path / "sessions.jsonl", pass_bar=0.70)


@pytest.mark.parametrize(
    "fluency,expected",
    [(0.90, "A"), (0.895, "B"), (0.80, "B"), (0.799, "C"),
     (0.70, "C"), (0.699, "D"), (0.60, "D"), (0.599, "F"), (0.0, "F")],
)
def test_rating_for_bands(fluency, expected):
    assert rating_for(fluency) == expected


def test_finish_sublevel_computes_fluency_and_first_try(tmp_path):
    svc = make_service(tmp_path)
    # item 1: wrong then right (retry) ; item 2: right first try
    svc.record_attempt("1a", 1, "a", "uh", 0.40, 0.5, False)
    svc.record_attempt("1a", 1, "a", "a", 1.00, 0.0, True)
    svc.record_attempt("1a", 2, "the", "the", 1.00, 0.0, True)
    result = svc.finish_sublevel("1a")
    assert result.tier == 1
    assert result.level == "1a"
    assert result.items_total == 2
    assert result.first_try_correct == 1            # only item 2 right on first try
    assert result.attempts == 3
    assert result.fluency == pytest.approx((0.40 + 1.00 + 1.00) / 3)
    assert result.rating == rating_for(result.fluency)


def test_finish_sublevel_passed_flag_uses_bar(tmp_path):
    svc = make_service(tmp_path)
    svc.record_attempt("1a", 1, "a", "a", 0.69, 0.0, True)
    assert svc.finish_sublevel("1a").passed is False
    svc.record_attempt("1b", 1, "cat", "cat", 0.70, 0.0, True)
    assert svc.finish_sublevel("1b").passed is True


def test_finish_sublevel_appends_record_with_item_log(tmp_path):
    svc = make_service(tmp_path)
    svc.record_attempt("1a", 1, "a", "a", 1.0, 0.0, True)
    svc.finish_sublevel("1a")
    lines = (tmp_path / "sessions.jsonl").read_text().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["type"] == "sublevel"
    assert rec["level"] == "1a"
    assert rec["tier"] == 1
    assert rec["session_id"] == svc.session_id
    assert rec["items"][0]["expected"] == "a"
    assert rec["items"][0]["accuracy"] == 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_evaluation.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ella_bot.services.evaluation'`

- [ ] **Step 3: Implement** — create `src/ella_bot/services/evaluation.py`

```python
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from ella_bot.core.constants import TIER_SUBLEVELS, tier_of


@dataclass
class ItemAttempt:
    item: int
    expected: str
    heard: str
    accuracy: float
    wer: float
    correct: bool
    ts: str


@dataclass
class SubLevelResult:
    tier: int
    level: str
    items_total: int
    first_try_correct: int
    attempts: int
    fluency: float
    rating: str
    passed: bool


@dataclass
class TierResult:
    tier: int
    fluency: float
    rating: str
    items_total: int
    first_try_correct: int
    passed: bool


@dataclass
class CumulativeResult:
    overall_fluency: float
    overall_rating: str
    items_total: int
    first_try_correct: int
    tiers: List[TierResult]
    duration_s: float


def rating_for(fluency: float) -> str:
    pct = fluency * 100
    if pct >= 90:
        return "A"
    if pct >= 80:
        return "B"
    if pct >= 70:
        return "C"
    if pct >= 60:
        return "D"
    return "F"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class EvaluationService:
    """Accumulates reading attempts, scores them, and appends JSONL records.

    No pygame dependency. Attempts are kept in memory keyed by level so a
    Retry can drop a unit's attempts; already-written JSONL records are
    append-only history and are never rewritten.
    """

    def __init__(self, log_path: Path, pass_bar: float = 0.70) -> None:
        self.log_path = Path(log_path)
        self.pass_bar = pass_bar
        self.session_id = _now()
        self._started = datetime.now()
        self._attempts: Dict[str, List[ItemAttempt]] = {}
        self._tier_results: Dict[int, TierResult] = {}

    def record_attempt(self, level, item, expected, heard, accuracy, wer, correct) -> None:
        self._attempts.setdefault(level, []).append(
            ItemAttempt(
                item=item, expected=expected, heard=heard,
                accuracy=accuracy, wer=wer, correct=correct, ts=_now(),
            )
        )

    def _aggregate(self, levels):
        """Return (items_total, first_try_correct, fluency, attempts) over levels.

        Item numbers restart per level, so distinct items are counted per
        level and summed (avoids collapsing "item 1" across sub-levels).
        """
        items_total = first_try = attempts = 0
        accs: List[float] = []
        for level in levels:
            atts = self._attempts.get(level, [])
            if not atts:
                continue
            first_by_item: Dict[int, bool] = {}
            for a in atts:
                if a.item not in first_by_item:
                    first_by_item[a.item] = a.correct
                accs.append(a.accuracy)
            items_total += len(first_by_item)
            first_try += sum(1 for ok in first_by_item.values() if ok)
            attempts += len(atts)
        fluency = sum(accs) / len(accs) if accs else 0.0
        return items_total, first_try, fluency, attempts

    def _append(self, record: dict) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
            f.flush()

    def finish_sublevel(self, level: str) -> SubLevelResult:
        items_total, first_try, fluency, attempts = self._aggregate([level])
        result = SubLevelResult(
            tier=tier_of(level), level=level, items_total=items_total,
            first_try_correct=first_try, attempts=attempts,
            fluency=fluency, rating=rating_for(fluency), passed=fluency >= self.pass_bar,
        )
        self._append({
            "type": "sublevel", "session_id": self.session_id,
            "tier": result.tier, "level": result.level,
            "items_total": result.items_total, "first_try_correct": result.first_try_correct,
            "attempts": result.attempts, "fluency": round(result.fluency, 4),
            "rating": result.rating, "passed": result.passed,
            "items": [asdict(a) for a in self._attempts.get(level, [])],
            "ts": _now(),
        })
        return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_evaluation.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add src/ella_bot/services/evaluation.py tests/test_evaluation.py
git commit -m "feat: add EvaluationService scoring and sub-level persistence"
```

---

## Task 3: EvaluationService — `finish_tier`, `finish_session`, `reset_sublevel`, `reset_tier`

**Files:**
- Modify: `src/ella_bot/services/evaluation.py`
- Test: `tests/test_evaluation.py`

- [ ] **Step 1: Write the failing tests** — append to `tests/test_evaluation.py`

```python
def test_finish_tier_aggregates_across_sublevels(tmp_path):
    svc = make_service(tmp_path)
    svc.record_attempt("1a", 1, "a", "a", 0.80, 0.0, True)
    svc.record_attempt("1b", 1, "cat", "cat", 1.00, 0.0, True)
    svc.record_attempt("1b", 2, "dog", "dog", 0.90, 0.0, True)
    result = svc.finish_tier(1)
    assert result.tier == 1
    assert result.items_total == 3
    assert result.first_try_correct == 3
    assert result.fluency == pytest.approx((0.80 + 1.00 + 0.90) / 3)
    assert result.passed is True


def test_finish_session_uses_latest_tier_results_and_writes_record(tmp_path):
    svc = make_service(tmp_path)
    svc.record_attempt("1a", 1, "a", "a", 0.80, 0.0, True)
    svc.finish_tier(1)
    svc.record_attempt("2a", 1, "go", "go", 0.60, 0.0, True)
    svc.finish_tier(2)
    cum = svc.finish_session()
    assert cum.overall_fluency == pytest.approx((0.80 + 0.60) / 2)
    assert [t.tier for t in cum.tiers] == [1, 2]
    assert cum.items_total == 2
    rec = json.loads((tmp_path / "sessions.jsonl").read_text().splitlines()[-1])
    assert rec["type"] == "session"
    assert rec["duration_s"] >= 0
    assert [t["tier"] for t in rec["tiers"]] == [1, 2]


def test_reset_sublevel_drops_its_attempts(tmp_path):
    svc = make_service(tmp_path)
    svc.record_attempt("1a", 1, "a", "uh", 0.30, 0.5, False)
    svc.reset_sublevel("1a")
    svc.record_attempt("1a", 1, "a", "a", 1.00, 0.0, True)
    result = svc.finish_sublevel("1a")
    assert result.attempts == 1
    assert result.fluency == pytest.approx(1.0)


def test_reset_tier_drops_all_sublevel_attempts(tmp_path):
    svc = make_service(tmp_path)
    svc.record_attempt("1a", 1, "a", "uh", 0.30, 0.5, False)
    svc.record_attempt("1b", 1, "cat", "cap", 0.40, 0.3, False)
    svc.reset_tier(1)
    _, _, fluency, attempts = svc._aggregate(["1a", "1b"])
    assert attempts == 0
    assert fluency == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_evaluation.py -v`
Expected: FAIL with `AttributeError: 'EvaluationService' object has no attribute 'finish_tier'`

- [ ] **Step 3: Implement** — append these methods inside `EvaluationService` in `src/ella_bot/services/evaluation.py`

```python
    def finish_tier(self, tier: int) -> TierResult:
        levels = TIER_SUBLEVELS.get(tier, [])
        items_total, first_try, fluency, _ = self._aggregate(levels)
        result = TierResult(
            tier=tier, fluency=fluency, rating=rating_for(fluency),
            items_total=items_total, first_try_correct=first_try,
            passed=fluency >= self.pass_bar,
        )
        self._tier_results[tier] = result
        self._append({
            "type": "tier", "session_id": self.session_id, "tier": tier,
            "fluency": round(result.fluency, 4), "rating": result.rating,
            "items_total": result.items_total, "first_try_correct": result.first_try_correct,
            "passed": result.passed, "ts": _now(),
        })
        return result

    def finish_session(self) -> CumulativeResult:
        items_total, first_try, fluency, _ = self._aggregate(list(self._attempts.keys()))
        tiers = [self._tier_results[t] for t in sorted(self._tier_results)]
        result = CumulativeResult(
            overall_fluency=fluency, overall_rating=rating_for(fluency),
            items_total=items_total, first_try_correct=first_try,
            tiers=tiers, duration_s=(datetime.now() - self._started).total_seconds(),
        )
        self._append({
            "type": "session", "session_id": self.session_id,
            "overall_fluency": round(result.overall_fluency, 4),
            "overall_rating": result.overall_rating,
            "items_total": result.items_total, "first_try_correct": result.first_try_correct,
            "tiers": [asdict(t) for t in tiers],
            "started_ts": self._started.isoformat(timespec="seconds"),
            "ended_ts": _now(), "duration_s": round(result.duration_s, 1), "ts": _now(),
        })
        return result

    def reset_sublevel(self, level: str) -> None:
        self._attempts[level] = []

    def reset_tier(self, tier: int) -> None:
        for level in TIER_SUBLEVELS.get(tier, []):
            self._attempts[level] = []
        self._tier_results.pop(tier, None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_evaluation.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add src/ella_bot/services/evaluation.py tests/test_evaluation.py
git commit -m "feat: add tier/session aggregation and retry resets to EvaluationService"
```

---

## Task 4: SessionManager tier helpers

**Files:**
- Modify: `src/ella_bot/services/session_manager.py`
- Test: `tests/test_session_manager.py`

- [ ] **Step 1: Write the failing tests** — append to `tests/test_session_manager.py`

```python
FULL_POOLS = {
    "1a": ["a"], "1b": ["b"], "1c": ["c"], "1d": ["d"],
    "1e": ["e"], "1f": ["f"], "1g": ["g"],
    "2a": ["go"], "2b": ["up"], "2c": ["in"], "2d": ["on"],
    "3": ["the cat"], "4": ["the big dog"],
}


def test_tier_of_and_is_last_sublevel_of_tier():
    s = SessionManager(level_pools=dict(FULL_POOLS), start_level="1a")
    assert s.tier_of("1a") == 1
    assert s.tier_of("2c") == 2
    assert s.is_last_sublevel_of_tier("1g") is True
    assert s.is_last_sublevel_of_tier("1a") is False
    assert s.is_last_sublevel_of_tier("2d") is True
    assert s.is_last_sublevel_of_tier("3") is True
    assert s.is_last_sublevel_of_tier("4") is True


def test_is_last_tier():
    s = SessionManager(level_pools=dict(FULL_POOLS), start_level="1a")
    assert s.is_last_tier(4) is True
    assert s.is_last_tier(1) is False


def test_current_sublevel_complete_does_not_depend_on_threshold():
    # Level 3 has threshold 1.01 (unreachable) but completion is goal-based.
    s = SessionManager(level_pools=dict(FULL_POOLS), start_level="3")
    assert s.current_sublevel_complete() is False
    s.completed_in_level = s.level_goal
    assert s.current_sublevel_complete() is True


def test_current_sublevel_complete_false_for_hard():
    s = SessionManager(level_pools={"1a": ["a"], "hard": ["x y"]}, start_level="1a")
    s.current_level = "hard"
    s.completed_in_level = 99
    assert s.current_sublevel_complete() is False


def test_advance_to_higher_stage_crosses_tier_boundary():
    s = SessionManager(level_pools=dict(FULL_POOLS), start_level="1g")
    assert s.advance_to_higher_stage() is True
    assert s.current_level == "2a"
    assert s.completed_in_level == 0


def test_retry_sublevel_resets_progress():
    s = SessionManager(level_pools=dict(FULL_POOLS), start_level="1c")
    s.completed_in_level = 1
    s.level_indices["1c"] = 0
    s.retry_sublevel("1c")
    assert s.current_level == "1c"
    assert s.completed_in_level == 0


def test_retry_tier_returns_to_first_sublevel():
    s = SessionManager(level_pools=dict(FULL_POOLS), start_level="1g")
    s.completed_in_level = 1
    s.retry_tier(1)
    assert s.current_level == "1a"
    assert s.completed_in_level == 0
    assert s.level_indices["1g"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_session_manager.py -v`
Expected: FAIL with `AttributeError: 'SessionManager' object has no attribute 'tier_of'`

- [ ] **Step 3: Implement**

In `src/ella_bot/services/session_manager.py`, update the constants import (line 7):

```python
from ella_bot.core.constants import LEVEL_ORDER, LEVEL_THRESHOLDS, TIER_SUBLEVELS, tier_of
```

Then add these methods to the `SessionManager` class (e.g. after `advance_to_higher_stage`):

```python
    def tier_of(self, level: str) -> int:
        return tier_of(level)

    def is_last_sublevel_of_tier(self, level: str) -> bool:
        subs = TIER_SUBLEVELS.get(tier_of(level), [])
        return bool(subs) and level == subs[-1]

    def is_last_tier(self, tier: int) -> bool:
        return tier == max(TIER_SUBLEVELS)

    def current_sublevel_complete(self) -> bool:
        if self.current_level == "hard":
            return False
        return self.completed_in_level >= self.level_goal

    def retry_sublevel(self, level: str) -> None:
        self.current_level = level
        self.reset_current_level()

    def retry_tier(self, tier: int) -> None:
        subs = TIER_SUBLEVELS.get(tier, [])
        for sub in subs:
            self.level_indices[sub] = 0
        if subs:
            self.current_level = subs[0]
        self.completed_in_level = 0
        self.level_goal = self.current_pool_size()
        self.expected_sentence = self.pick_sentence_for_level(self.current_level)
```

> Note: `advance_to_higher_stage()` already exists and advances to the next level in `LEVEL_ORDER` (crossing tier boundaries) and resets it — it is reused as the "Next" action. `try_level_up()` is left unchanged but is **no longer called from the runtime path** (see Task 6).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_session_manager.py -v`
Expected: PASS (all tests, including the pre-existing ones)

- [ ] **Step 5: Commit**

```bash
git add src/ella_bot/services/session_manager.py tests/test_session_manager.py
git commit -m "feat: add tier-boundary helpers to SessionManager"
```

---

## Task 5: New events

**Files:**
- Modify: `src/ella_bot/core/events.py`
- Test: `tests/test_events.py`

- [ ] **Step 1: Write the failing tests** — append to `tests/test_events.py`

```python
def test_sublevel_and_session_events_carry_payload():
    from ella_bot.core.events import SubLevelCompleted, SessionCompleted
    r = object()
    evt = SubLevelCompleted(r, "tier")
    assert evt.result is r
    assert evt.kind == "tier"
    assert SessionCompleted(r).result is r


def test_new_events_are_frozen():
    from ella_bot.core.events import SubLevelCompleted
    evt = SubLevelCompleted(object(), "sublevel")
    with pytest.raises(dataclasses.FrozenInstanceError):
        evt.kind = "tier"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_events.py -v`
Expected: FAIL with `ImportError: cannot import name 'SubLevelCompleted'`

- [ ] **Step 3: Implement** — append to `src/ella_bot/core/events.py`

```python
@dataclass(frozen=True)
class SubLevelCompleted:
    result: Any
    kind: str  # "sublevel" | "tier"


@dataclass(frozen=True)
class SessionCompleted:
    result: Any
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_events.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add src/ella_bot/core/events.py tests/test_events.py
git commit -m "feat: add SubLevelCompleted and SessionCompleted events"
```

---

## Task 6: AttemptRunner — record attempts + boundary detection

**Files:**
- Modify: `src/ella_bot/services/attempt_runner.py`
- Test: `tests/test_attempt_runner.py`

- [ ] **Step 1: Write the failing test** — create `tests/test_attempt_runner.py`

```python
import queue
from unittest.mock import MagicMock

from ella_bot.services.attempt_runner import AttemptRunner
from ella_bot.services.session_manager import SessionManager
from ella_bot.services.evaluation import EvaluationService
from ella_bot.core.events import SubLevelCompleted
import ella_bot.services.attempt_runner as runner_mod


class _FakeValidation:
    accuracy = 1.0
    wer = 0.0
    alignment = []


class _FakeFeedback:
    level_message = "Correct!"


class _FakeASRResult:
    transcript = "a"
    words = []


def _make_app(tmp_path):
    app = MagicMock()
    app.audio_feedback = False
    app.tts = None
    app.pronunciation_overrides = {}
    app.event_queue = queue.Queue()
    app.session = SessionManager(level_pools={"1a": ["a"], "1b": ["b"]}, start_level="1a")
    app.evaluation = EvaluationService(log_path=tmp_path / "s.jsonl", pass_bar=0.70)
    app.asr = MagicMock()
    app.asr.transcribe.return_value = _FakeASRResult()
    return app


def test_completing_a_sublevel_posts_sublevel_completed(tmp_path, monkeypatch):
    monkeypatch.setattr(runner_mod, "validate_spoken_text", lambda exp, got: _FakeValidation())
    monkeypatch.setattr(runner_mod, "build_feedback", lambda **k: _FakeFeedback())
    monkeypatch.setattr(runner_mod, "build_highlighted_expected", lambda alignment: "")
    monkeypatch.setattr(runner_mod, "normalize", lambda t: ["a"])
    monkeypatch.setattr(runner_mod, "spoken_word_confidence_map", lambda toks, confs: {})

    app = _make_app(tmp_path)
    runner = AttemptRunner(app, is_paused=lambda: False)
    runner.run()

    events = []
    while not app.event_queue.empty():
        events.append(app.event_queue.get_nowait())
    assert any(isinstance(e, SubLevelCompleted) and e.kind == "sublevel" for e in events)
    # one attempt recorded and a sublevel record written
    assert (tmp_path / "s.jsonl").read_text().count('"type": "sublevel"') == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_attempt_runner.py -v`
Expected: FAIL (no `SubLevelCompleted` posted — current code calls `try_level_up` and posts `MessageChanged`/`StateChanged` only)

- [ ] **Step 3: Implement**

In `src/ella_bot/services/attempt_runner.py`, replace the events import (line 8):

```python
from ella_bot.core.events import (
    StateChanged, MessageChanged, ErrorOccurred, AttemptReady,
    SubLevelCompleted, SessionCompleted,
)
```

Then replace the entire block from `if feedback.level_message == "Correct!":` through the trailing `self.app.event_queue.put(MessageChanged(""))` (the success/level-up/advance block, currently lines ~126-154) with:

```python
            session = self.app.session
            evaluation = self.app.evaluation
            level = session.current_level
            correct = feedback.level_message == "Correct!"

            evaluation.record_attempt(
                level=level,
                item=session.current_item_number(),
                expected=session.expected_sentence,
                heard=asr_result.transcript,
                accuracy=validation.accuracy,
                wer=validation.wer,
                correct=correct,
            )

            if correct:
                session.completed_in_level = min(
                    session.completed_in_level + 1, session.level_goal
                )
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
                            self.app.tts.speak(
                                "Incredible! You finished every level. Let's see how you did!"
                            )
                        self.app.event_queue.put(SessionCompleted(cumulative))
                    else:
                        if self.app.audio_feedback and self.app.tts is not None and not self._is_paused():
                            self.app.tts.speak(
                                f"Wow, you finished Level {tier}! You're doing amazing!"
                            )
                        self.app.event_queue.put(SubLevelCompleted(tier_result, "tier"))
                else:
                    if self.app.audio_feedback and self.app.tts is not None and not self._is_paused():
                        self.app.tts.speak("Great job! Let's see how you did!")
                    self.app.event_queue.put(SubLevelCompleted(sub_result, "sublevel"))
                return

            if feedback.level_message.startswith(
                ("Excellent", "Great", "Wonderful", "That's right", "Perfect")
            ):
                session.advance_to_next_sentence()
                self.app.event_queue.put(MessageChanged("Nice work! Moving to the next one."))
            else:
                self.app.event_queue.put(MessageChanged("Give it another try!"))

            time.sleep(0.6)
            self.app.event_queue.put(StateChanged("listening"))
            self.app.event_queue.put(MessageChanged(""))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_attempt_runner.py tests/test_session_manager.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/ella_bot/services/attempt_runner.py tests/test_attempt_runner.py
git commit -m "feat: record attempts and post completion events at level boundaries"
```

---

## Task 7: GUIConfig — log path + pass bar

**Files:**
- Modify: `src/ella_bot/ui/pygame_gui/config.py`

- [ ] **Step 1: Implement** (config-only change; no separate unit test — exercised by Task 11 manual run)

In `src/ella_bot/ui/pygame_gui/config.py`, update the import (line 5):

```python
from ella_bot.utils.file_utils import resolve_asset_path, get_project_root
```

Add two fields to the `GUIConfig` dataclass (after `assets_dir`):

```python
    session_log_path: Path = get_project_root() / "data" / "sessions.jsonl"
    pass_bar: float = 0.70
```

- [ ] **Step 2: Verify it imports**

Run: `python -c "from ella_bot.ui.pygame_gui.config import GUIConfig; print(GUIConfig().session_log_path, GUIConfig().pass_bar)"`
Expected: prints a path ending in `data/sessions.jsonl` and `0.7`

> If the command fails with `ModuleNotFoundError`, run it with `PYTHONPATH=src` prepended.

- [ ] **Step 3: Commit**

```bash
git add src/ella_bot/ui/pygame_gui/config.py
git commit -m "feat: add session_log_path and pass_bar to GUIConfig"
```

---

## Task 8: EllaGUIApp — build EvaluationService, register scenes, hold latest result

**Files:**
- Modify: `src/ella_bot/ui/pygame_gui/app.py`

- [ ] **Step 1: Implement** (wiring; verified in Task 11)

Add imports near the other scene imports (after line 11):

```python
from ella_bot.ui.pygame_gui.scenes.results import ResultsScene
from ella_bot.ui.pygame_gui.scenes.final_eval import FinalEvaluationScene
from ella_bot.services.evaluation import EvaluationService
```

In `EllaGUIApp.__init__`, immediately after the `self.session = SessionManager.from_config_file(...)` block (after line 39), add:

```python
        self.evaluation = EvaluationService(
            log_path=self.config.session_log_path,
            pass_bar=self.config.pass_bar,
        )
        self.latest_result = None
        self.latest_result_kind = None
```

In `run()`, extend the `self.scenes = {...}` dict (around line 178) to include:

```python
        self.scenes = {
            "intro": IntroScene(self),
            "main_menu": MainMenuScene(self),
            "reading_prompt": ReadingPromptScene(self),
            "settings": SettingsScene(self),
            "results": ResultsScene(self),
            "final_eval": FinalEvaluationScene(self),
        }
```

> `self.config` is assigned before the session in `__init__`, so `self.config.session_log_path` is available when constructing `EvaluationService`.

- [ ] **Step 2: Defer verification** — this task cannot run standalone until Tasks 9 & 10 create the scenes. Verification happens in Task 11.

- [ ] **Step 3: Commit**

```bash
git add src/ella_bot/ui/pygame_gui/app.py
git commit -m "feat: construct EvaluationService and register results scenes"
```

---

## Task 9: ResultsScene (sub-level + tier)

**Files:**
- Create: `src/ella_bot/ui/pygame_gui/scenes/results.py`
- Test: `tests/test_results_scene.py`

- [ ] **Step 1: Write the failing tests** — create `tests/test_results_scene.py`

```python
from unittest.mock import MagicMock


def _make_scene(kind="sublevel", passed=True, level="1c", tier=1):
    from ella_bot.ui.pygame_gui.scenes.results import ResultsScene
    app = MagicMock()
    result = MagicMock()
    result.passed = passed
    result.level = level
    result.tier = tier
    app.latest_result = result
    app.latest_result_kind = kind
    scene = object.__new__(ResultsScene)
    scene.app = app
    scene.pressed_button = None
    return scene


def test_next_advances_when_passed():
    scene = _make_scene(passed=True)
    scene._do_next()
    scene.app.session.advance_to_higher_stage.assert_called_once()
    scene.app.switch_scene.assert_called_with("reading_prompt")


def test_next_does_nothing_when_not_passed():
    scene = _make_scene(passed=False)
    scene._do_next()
    scene.app.session.advance_to_higher_stage.assert_not_called()
    scene.app.switch_scene.assert_not_called()


def test_retry_sublevel_resets_sublevel():
    scene = _make_scene(kind="sublevel", level="1c")
    scene._do_retry()
    scene.app.session.retry_sublevel.assert_called_once_with("1c")
    scene.app.evaluation.reset_sublevel.assert_called_once_with("1c")
    scene.app.switch_scene.assert_called_with("reading_prompt")


def test_retry_tier_resets_tier():
    scene = _make_scene(kind="tier", tier=2)
    scene._do_retry()
    scene.app.session.retry_tier.assert_called_once_with(2)
    scene.app.evaluation.reset_tier.assert_called_once_with(2)


def test_main_menu_switches_scene():
    scene = _make_scene()
    scene._do_main_menu()
    scene.app.switch_scene.assert_called_once_with("main_menu")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_results_scene.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ella_bot.ui.pygame_gui.scenes.results'`

- [ ] **Step 3: Implement** — create `src/ella_bot/ui/pygame_gui/scenes/results.py`

```python
import pygame

from ella_bot.ui.pygame_gui.scene import BaseScene

_CARD_BG = (0, 0, 0)
_WHITE = (255, 255, 255)
_OUTER_BORDER = (94, 42, 59)
_INNER_BORDER = (255, 185, 207)
_BTN_FILL = (255, 182, 193)
_BTN_OUTLINE = (94, 42, 59)
_BTN_PRESSED = (251, 165, 193)
_BTN_DISABLED = (210, 210, 210)
_TEXT_DARK = (56, 56, 56)
_TITLE_COLOR = (230, 127, 159)
_RATING_COLORS = {"A": (60, 160, 90), "B": (60, 160, 90), "C": (210, 150, 40),
                  "D": (200, 70, 80), "F": (200, 70, 80)}

_SUBTEXT = {"A": "Amazing reading!", "B": "Great job!", "C": "Nice work!",
            "D": "Keep practicing — you've got this!", "F": "Keep practicing — you've got this!"}


class ResultsScene(BaseScene):
    def __init__(self, app):
        super().__init__(app)
        self.pressed_button = None
        self._rating_font = None
        self.next_button = None
        self.retry_button = None
        self.menu_button = None

    def on_enter(self) -> None:
        self.pressed_button = None

    # --- actions (unit-tested) ---

    def _do_next(self) -> None:
        result = self.app.latest_result
        if not getattr(result, "passed", False):
            return
        self.app.session.advance_to_higher_stage()
        self.app.switch_scene("reading_prompt")
        self.app.active_scene._start_attempt()

    def _do_retry(self) -> None:
        result = self.app.latest_result
        if self.app.latest_result_kind == "tier":
            self.app.session.retry_tier(result.tier)
            self.app.evaluation.reset_tier(result.tier)
        else:
            self.app.session.retry_sublevel(result.level)
            self.app.evaluation.reset_sublevel(result.level)
        self.app.switch_scene("reading_prompt")
        self.app.active_scene._start_attempt()

    def _do_main_menu(self) -> None:
        self.app.switch_scene("main_menu")

    # --- input ---

    def handle_event(self, event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for key, rect in (("next", self.next_button), ("retry", self.retry_button),
                              ("menu", self.menu_button)):
                if rect and rect.collidepoint(event.pos):
                    self.pressed_button = key
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            key = self.pressed_button
            self.pressed_button = None
            if key == "next" and self.next_button and self.next_button.collidepoint(event.pos):
                self._do_next()
            elif key == "retry" and self.retry_button and self.retry_button.collidepoint(event.pos):
                self._do_retry()
            elif key == "menu" and self.menu_button and self.menu_button.collidepoint(event.pos):
                self._do_main_menu()

    # --- rendering ---

    def _draw_button(self, screen, rect, label, key, enabled=True) -> None:
        if not enabled:
            pygame.draw.rect(screen, _BTN_DISABLED, rect, border_radius=20)
            pygame.draw.rect(screen, _BTN_OUTLINE, rect, width=2, border_radius=20)
            surf = self.app.font_body.render(label, True, _WHITE)
            screen.blit(surf, surf.get_rect(center=rect.center))
            return
        is_pressed = self.pressed_button == key
        bg = _BTN_PRESSED if is_pressed else _BTN_FILL
        if not is_pressed:
            pygame.draw.rect(screen, _BTN_OUTLINE,
                             pygame.Rect(rect.left + 4, rect.top + 4, rect.width, rect.height),
                             border_radius=20)
        pygame.draw.rect(screen, bg, rect, border_radius=20)
        pygame.draw.rect(screen, _BTN_OUTLINE, rect, width=2, border_radius=20)
        surf = self.app.font_body.render(label, True, _WHITE)
        screen.blit(surf, surf.get_rect(center=rect.center))

    def render(self) -> None:
        screen = self.app.screen
        width, height = screen.get_size()
        result = self.app.latest_result
        kind = self.app.latest_result_kind

        prompt_rect = pygame.Rect(0, 0, width, height)
        pygame.draw.rect(screen, _CARD_BG, prompt_rect, border_radius=0)
        inner_rect = prompt_rect.inflate(-64, -64)
        pygame.draw.rect(screen, _WHITE, prompt_rect.inflate(-24, -24), border_radius=56)
        pygame.draw.rect(screen, _WHITE, inner_rect, border_radius=36)

        if kind == "tier":
            headline = f"Level {result.tier} Complete — Level Up!"
            next_label = "Next Level"
        else:
            headline = f"Sub-Level {result.level.upper()} Complete!"
            next_label = "Continue"

        title = self.app.font_title.render(headline, True, _TITLE_COLOR)
        screen.blit(title, title.get_rect(centerx=inner_rect.centerx, top=inner_rect.top + 36))

        sub = self.app.font_body.render(_SUBTEXT.get(result.rating, ""), True, _TEXT_DARK)
        screen.blit(sub, sub.get_rect(centerx=inner_rect.centerx, top=inner_rect.top + 120))

        if self._rating_font is None:
            self._rating_font = self.app._get_sys_font(160, bold=True)
        letter = self._rating_font.render(result.rating, True, _RATING_COLORS.get(result.rating, _TEXT_DARK))
        screen.blit(letter, letter.get_rect(center=(inner_rect.centerx, inner_rect.centery - 20)))

        fluency = self.app.font_body.render(f"Fluency: {round(result.fluency * 100)}%", True, _TEXT_DARK)
        screen.blit(fluency, fluency.get_rect(centerx=inner_rect.centerx, centery=inner_rect.centery + 90))

        correct = self.app.font_body.render(
            f"Read first try: {result.first_try_correct} / {result.items_total}", True, _TEXT_DARK)
        screen.blit(correct, correct.get_rect(centerx=inner_rect.centerx, centery=inner_rect.centery + 140))

        btn_w, btn_h, gap = 280, 80, 24
        total_w = btn_w * 3 + gap * 2
        x0 = inner_rect.centerx - total_w // 2
        y = inner_rect.bottom - btn_h - 48
        self.next_button = pygame.Rect(x0, y, btn_w, btn_h)
        self.retry_button = pygame.Rect(x0 + btn_w + gap, y, btn_w, btn_h)
        self.menu_button = pygame.Rect(x0 + (btn_w + gap) * 2, y, btn_w, btn_h)
        self._draw_button(screen, self.next_button, next_label, "next", enabled=bool(result.passed))
        self._draw_button(screen, self.retry_button, "Try Again", "retry")
        self._draw_button(screen, self.menu_button, "Main Menu", "menu")

        pygame.draw.rect(screen, _OUTER_BORDER, prompt_rect, width=12, border_radius=68)
        pygame.draw.rect(screen, _INNER_BORDER, inner_rect, width=12, border_radius=36)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_results_scene.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add src/ella_bot/ui/pygame_gui/scenes/results.py tests/test_results_scene.py
git commit -m "feat: add ResultsScene for sub-level and tier completion"
```

---

## Task 10: FinalEvaluationScene

**Files:**
- Create: `src/ella_bot/ui/pygame_gui/scenes/final_eval.py`
- Test: `tests/test_final_eval_scene.py`

- [ ] **Step 1: Write the failing tests** — create `tests/test_final_eval_scene.py`

```python
from unittest.mock import MagicMock


def _make_scene(tmp_path):
    from ella_bot.ui.pygame_gui.scenes.final_eval import FinalEvaluationScene
    from ella_bot.services.evaluation import EvaluationService
    app = MagicMock()
    app.evaluation = EvaluationService(log_path=tmp_path / "s.jsonl", pass_bar=0.70)
    app.latest_result = MagicMock()
    scene = object.__new__(FinalEvaluationScene)
    scene.app = app
    scene.pressed_button = None
    return scene


def test_play_again_resets_and_restarts(tmp_path):
    scene = _make_scene(tmp_path)
    old_session_id = scene.app.evaluation.session_id
    scene._do_play_again()
    scene.app.session.reset_to_start.assert_called_once()
    assert scene.app.evaluation.session_id != old_session_id  # fresh evaluation session
    scene.app.switch_scene.assert_called_with("reading_prompt")


def test_main_menu_switches_scene(tmp_path):
    scene = _make_scene(tmp_path)
    scene._do_main_menu()
    scene.app.switch_scene.assert_called_once_with("main_menu")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_final_eval_scene.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ella_bot.ui.pygame_gui.scenes.final_eval'`

- [ ] **Step 3: Implement** — create `src/ella_bot/ui/pygame_gui/scenes/final_eval.py`

```python
import pygame

from ella_bot.ui.pygame_gui.scene import BaseScene
from ella_bot.services.evaluation import EvaluationService

_CARD_BG = (0, 0, 0)
_WHITE = (255, 255, 255)
_OUTER_BORDER = (94, 42, 59)
_INNER_BORDER = (255, 185, 207)
_BTN_FILL = (255, 182, 193)
_BTN_OUTLINE = (94, 42, 59)
_BTN_PRESSED = (251, 165, 193)
_TEXT_DARK = (56, 56, 56)
_TITLE_COLOR = (230, 127, 159)
_RATING_COLORS = {"A": (60, 160, 90), "B": (60, 160, 90), "C": (210, 150, 40),
                  "D": (200, 70, 80), "F": (200, 70, 80)}


class FinalEvaluationScene(BaseScene):
    def __init__(self, app):
        super().__init__(app)
        self.pressed_button = None
        self._rating_font = None
        self.play_button = None
        self.menu_button = None

    def on_enter(self) -> None:
        self.pressed_button = None

    # --- actions (unit-tested) ---

    def _do_play_again(self) -> None:
        self.app.session.reset_to_start()
        self.app.evaluation = EvaluationService(
            log_path=self.app.evaluation.log_path,
            pass_bar=self.app.evaluation.pass_bar,
        )
        self.app.switch_scene("reading_prompt")
        self.app.active_scene._start_attempt()

    def _do_main_menu(self) -> None:
        self.app.switch_scene("main_menu")

    # --- input ---

    def handle_event(self, event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for key, rect in (("play", self.play_button), ("menu", self.menu_button)):
                if rect and rect.collidepoint(event.pos):
                    self.pressed_button = key
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            key = self.pressed_button
            self.pressed_button = None
            if key == "play" and self.play_button and self.play_button.collidepoint(event.pos):
                self._do_play_again()
            elif key == "menu" and self.menu_button and self.menu_button.collidepoint(event.pos):
                self._do_main_menu()

    # --- rendering ---

    def _draw_button(self, screen, rect, label, key) -> None:
        is_pressed = self.pressed_button == key
        bg = _BTN_PRESSED if is_pressed else _BTN_FILL
        if not is_pressed:
            pygame.draw.rect(screen, _BTN_OUTLINE,
                             pygame.Rect(rect.left + 4, rect.top + 4, rect.width, rect.height),
                             border_radius=20)
        pygame.draw.rect(screen, bg, rect, border_radius=20)
        pygame.draw.rect(screen, _BTN_OUTLINE, rect, width=2, border_radius=20)
        surf = self.app.font_body.render(label, True, _WHITE)
        screen.blit(surf, surf.get_rect(center=rect.center))

    def render(self) -> None:
        screen = self.app.screen
        width, height = screen.get_size()
        result = self.app.latest_result

        prompt_rect = pygame.Rect(0, 0, width, height)
        pygame.draw.rect(screen, _CARD_BG, prompt_rect, border_radius=0)
        inner_rect = prompt_rect.inflate(-64, -64)
        pygame.draw.rect(screen, _WHITE, prompt_rect.inflate(-24, -24), border_radius=56)
        pygame.draw.rect(screen, _WHITE, inner_rect, border_radius=36)

        title = self.app.font_title.render("All Levels Complete!", True, _TITLE_COLOR)
        screen.blit(title, title.get_rect(centerx=inner_rect.centerx, top=inner_rect.top + 32))

        if self._rating_font is None:
            self._rating_font = self.app._get_sys_font(120, bold=True)
        letter = self._rating_font.render(
            result.overall_rating, True, _RATING_COLORS.get(result.overall_rating, _TEXT_DARK))
        screen.blit(letter, letter.get_rect(centerx=inner_rect.centerx, top=inner_rect.top + 110))

        fluency = self.app.font_body.render(
            f"Overall Fluency: {round(result.overall_fluency * 100)}%", True, _TEXT_DARK)
        screen.blit(fluency, fluency.get_rect(centerx=inner_rect.centerx, top=inner_rect.top + 250))

        row_y = inner_rect.top + 300
        for tier in result.tiers:
            row = self.app.font_body.render(
                f"Level {tier.tier}   ·   {tier.rating}   ·   {round(tier.fluency * 100)}%",
                True, _TEXT_DARK)
            screen.blit(row, row.get_rect(centerx=inner_rect.centerx, top=row_y))
            row_y += 40

        totals = self.app.font_body.render(
            f"Read first try: {result.first_try_correct} / {result.items_total}", True, _TEXT_DARK)
        screen.blit(totals, totals.get_rect(centerx=inner_rect.centerx, top=row_y + 12))

        btn_w, btn_h, gap = 300, 80, 28
        total_w = btn_w * 2 + gap
        x0 = inner_rect.centerx - total_w // 2
        y = inner_rect.bottom - btn_h - 48
        self.play_button = pygame.Rect(x0, y, btn_w, btn_h)
        self.menu_button = pygame.Rect(x0 + btn_w + gap, y, btn_w, btn_h)
        self._draw_button(screen, self.play_button, "Play Again", "play")
        self._draw_button(screen, self.menu_button, "Main Menu", "menu")

        pygame.draw.rect(screen, _OUTER_BORDER, prompt_rect, width=12, border_radius=68)
        pygame.draw.rect(screen, _INNER_BORDER, inner_rect, width=12, border_radius=36)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_final_eval_scene.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add src/ella_bot/ui/pygame_gui/scenes/final_eval.py tests/test_final_eval_scene.py
git commit -m "feat: add FinalEvaluationScene cumulative results screen"
```

---

## Task 11: Route completion events to the new scenes

**Files:**
- Modify: `src/ella_bot/ui/pygame_gui/scenes/reading_prompt.py`

- [ ] **Step 1: Implement** (wiring; verified by the manual run in Step 2)

In `src/ella_bot/ui/pygame_gui/scenes/reading_prompt.py`, update the events import (line 13):

```python
from ella_bot.core.events import (
    StateChanged, MessageChanged, ErrorOccurred, AttemptReady,
    SubLevelCompleted, SessionCompleted,
)
```

In `_drain_event_queue`, add two branches inside the `while True` loop, after the existing `elif isinstance(event, AttemptReady):` branch (around line 409):

```python
            elif isinstance(event, SubLevelCompleted):
                self.app.latest_result = event.result
                self.app.latest_result_kind = event.kind
                self.app.switch_scene("results")
                return
            elif isinstance(event, SessionCompleted):
                self.app.latest_result = event.result
                self.app.switch_scene("final_eval")
                return
```

> `return` stops draining and exits `update()` cleanly after the scene switch, so the now-inactive reading scene does not continue running its idle-timeout logic this frame.

- [ ] **Step 2: Manual integration verification**

Use the simulated ASR so a full run is deterministic and fast. From the project root:

```bash
PYTHONPATH=src python -m ella_bot.cli.main --gui --start-level 1a --spoken "a"
```

Verify:
1. After reading the first sub-level's item(s), a **ResultsScene** appears with a headline, an A–F letter, "Fluency: N%", and "Read first try: X / Y".
2. **Try Again** returns to reading and replays the same sub-level.
3. **Next / Continue** advances to the next sub-level (label says "Next Level" only at a tier boundary).
4. **Main Menu** returns to the main menu.
5. Reaching the end of level 4 shows the **FinalEvaluationScene** with the per-tier breakdown and **Play Again** / **Main Menu**.
6. A `data/sessions.jsonl` file is created and grows with `sublevel`/`tier`/`session` lines:

```bash
tail -n 3 data/sessions.jsonl
```

Expected: JSON lines whose `type` fields include `sublevel`, then `tier`, then `session`, all sharing one `session_id`.

> Note: with `--start-level 1a` a full run walks the real curriculum pools, which is long. To validate the tier/final screens quickly, temporarily set `--start-level 4` (single-item tier) to reach the FinalEvaluationScene after one item, then revert.

- [ ] **Step 3: Run the full unit suite**

Run: `python -m pytest`
Expected: PASS (no regressions)

- [ ] **Step 4: Commit**

```bash
git add src/ella_bot/ui/pygame_gui/scenes/reading_prompt.py
git commit -m "feat: route completion events to results and final evaluation scenes"
```

---

## Task 12: Config plumbing for the log path

**Files:**
- Modify: `config/settings.ini`
- Modify: `src/ella_bot/config/app_config.py`
- Modify: `src/ella_bot/cli/main.py`

- [ ] **Step 1: Implement — settings.ini**

In `config/settings.ini`, under the `[System]` section, add:

```ini
session_log = ./data/sessions.jsonl
```

- [ ] **Step 2: Implement — app_config.py**

In `src/ella_bot/config/app_config.py`, inside `load_settings()`'s `if parser.has_section("System"):` block, after the `start_level` lines, add:

```python
        if parser.has_option("System", "session_log"):
            defaults["session_log"] = parser.get("System", "session_log")
```

- [ ] **Step 3: Implement — cli/main.py**

In `parse_args()`, add an argument (after the `--start-level` argument):

```python
    parser.add_argument(
        "--session-log",
        default="./data/sessions.jsonl",
        help="Path to the JSONL evaluation log (relative paths resolve against the project root).",
    )
```

In `run_gui()`, before constructing `EllaGUIApp`, resolve the path and pass it into `GUIConfig`:

```python
    session_log = Path(args.session_log)
    if not session_log.is_absolute():
        session_log = get_project_root() / args.session_log
```

Then add `session_log_path=session_log` to the `GUIConfig(...)` call:

```python
        config=GUIConfig(
            width=args.gui_width,
            height=args.gui_height,
            fullscreen=args.fullscreen,
            session_log_path=session_log,
        ),
```

> `Path` and `get_project_root` are already imported at the top of `cli/main.py`.

- [ ] **Step 4: Verify the override is read**

Run: `PYTHONPATH=src python -c "from ella_bot.config.app_config import load_settings; print(load_settings().get('session_log'))"`
Expected: prints `./data/sessions.jsonl`

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add config/settings.ini src/ella_bot/config/app_config.py src/ella_bot/cli/main.py
git commit -m "feat: make evaluation log path configurable via settings.ini"
```

---

## Final Verification

- [ ] Run the whole suite: `python -m pytest` → all green.
- [ ] Do a manual GUI pass per Task 11 Step 2 (including the quick `--start-level 4` check of the FinalEvaluationScene).
- [ ] Confirm `data/sessions.jsonl` accumulates records and that pulling power between sub-levels leaves all completed sub-level/tier records intact on disk.
- [ ] Confirm `.gitignore` excludes `data/sessions.jsonl` if these runtime logs should not be committed (add `data/` to `.gitignore` if desired — runtime artifact, not source).
