# Session Item Limit for Tier 2+ Levels — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tier 1 levels (1a–1g) play every item in the pool; tier 2–4 levels (2a, 2b, 2c, 2d, 3, 4) play a fresh random sample of 10 items per session.

**Architecture:** A `TIER2_PLUS_SESSION_LIMIT = 10` constant drives the cap. `SessionManager` gains a `_session_pools` dict (built by `_build_session_pool`) that replaces direct `level_pools` access in all item-selection methods. `_build_session_pool` returns the full pool for tier 1 and a `random.sample` of 10 for tier 2–4. Every method that starts or resets a sublevel rebuilds the relevant entry in `_session_pools` so a fresh random draw happens each session.

**Tech Stack:** Python 3.13, pytest (`.venv/bin/python -m pytest`), `random.sample` from stdlib.

---

### Task 1: Add `TIER2_PLUS_SESSION_LIMIT` constant

**Files:**
- Modify: `src/ella_bot/core/constants.py`
- Test: `tests/test_constants.py`

- [ ] **Step 1: Write the failing test**

Add at the bottom of `tests/test_constants.py`:

```python
def test_tier2_plus_session_limit_is_10():
    assert constants.TIER2_PLUS_SESSION_LIMIT == 10
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_constants.py::test_tier2_plus_session_limit_is_10 -v
```

Expected: `FAILED` — `AttributeError: module has no attribute 'TIER2_PLUS_SESSION_LIMIT'`

- [ ] **Step 3: Add the constant to `constants.py`**

Add after `TIER_SUBLEVELS` and before `tier_of`:

```python
TIER2_PLUS_SESSION_LIMIT: int = 10
```

- [ ] **Step 4: Run all constants tests**

```bash
.venv/bin/python -m pytest tests/test_constants.py -v
```

Expected: all 10 tests `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add src/ella_bot/core/constants.py tests/test_constants.py
git commit -m "feat: add TIER2_PLUS_SESSION_LIMIT constant"
```

---

### Task 2: Add `_session_pools` and `_build_session_pool` to `SessionManager`

**Files:**
- Modify: `src/ella_bot/services/session_manager.py`
- Test: `tests/test_session_manager.py`

- [ ] **Step 1: Write the failing tests**

Add at the bottom of `tests/test_session_manager.py`:

```python
# ── Session item limit tests ──────────────────────────────────────────────────

def _tier2_pools(tier2_pool_size: int = 40) -> dict:
    """Full pool dict with a large tier-2 pool for limit testing."""
    return {
        "1a": ["a"], "1b": ["b"], "1c": ["c"], "1d": ["d"],
        "1e": ["e"], "1f": ["f"], "1g": ["g"],
        "2a": [str(i) for i in range(tier2_pool_size)],
        "2b": ["up"], "2c": ["in"], "2d": ["on"],
        "3": ["the cat"], "4": ["the big dog"],
    }


def test_tier1_level_goal_equals_full_pool_size():
    pool = [str(i) for i in range(15)]
    s = SessionManager(level_pools={"1a": pool}, start_level="1a")
    assert s.level_goal == 15


def test_tier2_level_goal_capped_at_session_limit():
    s = SessionManager(level_pools=_tier2_pools(40), start_level="2a")
    assert s.level_goal == 10


def test_tier2_small_pool_uses_full_pool_when_below_limit():
    pools = _tier2_pools()
    pools["2a"] = ["x", "y", "z"]
    s = SessionManager(level_pools=pools, start_level="2a")
    assert s.level_goal == 3


def test_tier2_session_items_are_drawn_from_full_pool():
    pools = _tier2_pools(40)
    s = SessionManager(level_pools=pools, start_level="2a")
    items = [s.expected_sentence]
    for _ in range(9):
        s.advance_to_next_sentence()
        items.append(s.expected_sentence)
    assert len(set(items)) == 10
    assert all(item in pools["2a"] for item in items)


def test_advance_to_higher_stage_builds_tier2_session_pool():
    s = SessionManager(level_pools=_tier2_pools(40), start_level="1g")
    s.advance_to_higher_stage()
    assert s.current_level == "2a"
    assert s.level_goal == 10


def test_reset_current_level_rebuilds_tier2_session_pool():
    s = SessionManager(level_pools=_tier2_pools(40), start_level="2a")
    s.completed_in_level = s.level_goal
    s.reset_current_level()
    assert s.level_goal == 10
    assert s.completed_in_level == 0


def test_retry_sublevel_rebuilds_tier2_session_pool():
    s = SessionManager(level_pools=_tier2_pools(40), start_level="2a")
    s.retry_sublevel("2a")
    assert s.level_goal == 10
    assert s.completed_in_level == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_session_manager.py -v -k "tier1_level_goal or tier2"
```

Expected: 7 new tests `FAILED`.

- [ ] **Step 3: Update imports in `session_manager.py`**

Replace the existing import block at the top of `src/ella_bot/services/session_manager.py`:

```python
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Dict, List

from ella_bot.core.constants import (
    LEVEL_ORDER, LEVEL_THRESHOLDS, TIER_SUBLEVELS,
    TIER2_PLUS_SESSION_LIMIT, tier_of,
)
from ella_bot.utils.file_utils import resolve_config_path
```

- [ ] **Step 4: Add `_build_session_pool` method**

Add this method to `SessionManager` directly after `from_config_file`:

```python
    def _build_session_pool(self, level: str) -> List[str]:
        pool = self.level_pools.get(level, [])
        if tier_of(level) == 1:
            return list(pool)
        return random.sample(pool, min(TIER2_PLUS_SESSION_LIMIT, len(pool)))
```

- [ ] **Step 5: Update `__init__` to initialise `_session_pools`**

Replace the `__init__` method:

```python
    def __init__(self, level_pools: Dict[str, List[str]], start_level: str = "1a") -> None:
        self.level_order = list(LEVEL_ORDER)
        self.level_thresholds = dict(LEVEL_THRESHOLDS)
        self.level_pools = level_pools

        if start_level not in self.level_order:
            start_level = "1a"
        self.current_level = start_level
        self.level_indices: Dict[str, int] = {level: 0 for level in self.level_order}
        self._session_pools: Dict[str, List[str]] = {}
        self._session_pools[self.current_level] = self._build_session_pool(self.current_level)
        self.expected_sentence = self.pick_sentence_for_level(self.current_level)
        self.completed_in_level = 0
        self.level_goal = len(self._session_pools.get(self.current_level, []))
        self.last_announced_sentence = ""
```

- [ ] **Step 6: Update `pick_sentence_for_level` to use `_session_pools`**

Replace:

```python
    def pick_sentence_for_level(self, level: str) -> str:
        pool = self.level_pools.get(level, [])
        if not pool:
            return ""
        if level == "hard":
            return random.choice(pool)
        index = self.level_indices.get(level, 0)
        index = max(0, min(index, len(pool) - 1))
        return pool[index]
```

With:

```python
    def pick_sentence_for_level(self, level: str) -> str:
        if level == "hard":
            pool = self.level_pools.get(level, [])
            return random.choice(pool) if pool else ""
        pool = self._session_pools.get(level, [])
        if not pool:
            return ""
        index = self.level_indices.get(level, 0)
        index = max(0, min(index, len(pool) - 1))
        return pool[index]
```

- [ ] **Step 7: Update `current_pool_size` to use `_session_pools`**

Replace:

```python
    def current_pool_size(self) -> int:
        return len(self.level_pools.get(self.current_level, []))
```

With:

```python
    def current_pool_size(self) -> int:
        return len(self._session_pools.get(self.current_level, []))
```

- [ ] **Step 8: Update `advance_to_next_sentence` to use `_session_pools`**

Replace:

```python
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
```

With:

```python
    def advance_to_next_sentence(self) -> None:
        if self.current_level == "hard":
            self.expected_sentence = self.pick_sentence_for_level(self.current_level)
            return
        pool = self._session_pools.get(self.current_level, [])
        if not pool:
            self.expected_sentence = ""
            return
        next_index = min(self.level_indices.get(self.current_level, 0) + 1, len(pool) - 1)
        self.level_indices[self.current_level] = next_index
        self.expected_sentence = pool[next_index]
```

- [ ] **Step 9: Update `reset_current_level` to rebuild session pool**

Replace:

```python
    def reset_current_level(self) -> None:
        self.completed_in_level = 0
        self.level_goal = self.current_pool_size()
        self.level_indices[self.current_level] = 0
        self.expected_sentence = self.pick_sentence_for_level(self.current_level)
        self.last_announced_sentence = ""
```

With:

```python
    def reset_current_level(self) -> None:
        self._session_pools[self.current_level] = self._build_session_pool(self.current_level)
        self.completed_in_level = 0
        self.level_goal = self.current_pool_size()
        self.level_indices[self.current_level] = 0
        self.expected_sentence = self.pick_sentence_for_level(self.current_level)
        self.last_announced_sentence = ""
```

- [ ] **Step 10: Update `reset_to_start` to rebuild session pool for 1a**

Replace:

```python
    def reset_to_start(self) -> None:
        self.current_level = "1a"
        self.level_indices = {level: 0 for level in self.level_order}
        self.completed_in_level = 0
        self.level_goal = len(self.level_pools.get("1a", []))
        self.expected_sentence = self.pick_sentence_for_level("1a")
        self.last_announced_sentence = ""
```

With:

```python
    def reset_to_start(self) -> None:
        self.current_level = "1a"
        self.level_indices = {level: 0 for level in self.level_order}
        self.completed_in_level = 0
        self._session_pools["1a"] = self._build_session_pool("1a")
        self.level_goal = len(self._session_pools.get("1a", []))
        self.expected_sentence = self.pick_sentence_for_level("1a")
        self.last_announced_sentence = ""
```

- [ ] **Step 11: Update `retry_tier` to rebuild session pool for the first sublevel**

Replace:

```python
    def retry_tier(self, tier: int) -> None:
        subs = TIER_SUBLEVELS.get(tier, [])
        for sub in subs:
            self.level_indices[sub] = 0
        if subs:
            self.current_level = subs[0]
        self.completed_in_level = 0
        self.level_goal = self.current_pool_size()
        self.expected_sentence = self.pick_sentence_for_level(self.current_level)
        self.last_announced_sentence = ""
```

With:

```python
    def retry_tier(self, tier: int) -> None:
        subs = TIER_SUBLEVELS.get(tier, [])
        for sub in subs:
            self.level_indices[sub] = 0
        if subs:
            self.current_level = subs[0]
            self._session_pools[subs[0]] = self._build_session_pool(subs[0])
        self.completed_in_level = 0
        self.level_goal = self.current_pool_size()
        self.expected_sentence = self.pick_sentence_for_level(self.current_level)
        self.last_announced_sentence = ""
```

- [ ] **Step 12: Run all session manager tests**

```bash
.venv/bin/python -m pytest tests/test_session_manager.py -v
```

Expected: all tests (original + 7 new) `PASSED`.

- [ ] **Step 13: Run full suite for regressions**

```bash
.venv/bin/python -m pytest tests/ -v --ignore=tests/test_gui_e2e.py 2>&1 | tail -30
```

Expected: all tests `PASSED`.

- [ ] **Step 14: Commit**

```bash
git add src/ella_bot/services/session_manager.py tests/test_session_manager.py
git commit -m "feat: random 10-item session pool for tier 2+ levels"
```
