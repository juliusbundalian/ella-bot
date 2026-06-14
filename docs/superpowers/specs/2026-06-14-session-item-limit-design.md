# Session Item Limit for Tier 2+ Levels

**Date:** 2026-06-14
**Status:** Approved

## Overview

Tier 1 levels (1a–1g) play every item in their pool each session. Tier 2–4 levels (2a, 2b, 2c, 2d, 3, 4) play a random sample of 10 items per session, picked fresh each time the level starts.

## Behaviour

### Tier 1 (1a–1g)

No change. All items in the pool are played in their existing sequential order. `level_goal` equals the full pool size.

### Tier 2–4 (2a, 2b, 2c, 2d, 3, 4)

At the start of each sublevel a random sample of `min(10, pool_size)` items is drawn without replacement from the full pool. Those items are played in the sampled order. `level_goal` equals 10 (or the full pool size if smaller than 10). Each new session draws a fresh sample, so the user sees different items every time.

## Architecture

`level_pools` (the full content dict loaded from `level_pools.json`) is never modified. A new `_session_pools: Dict[str, List[str]]` dict in `SessionManager` holds the items for the current session. All item-access methods read from `_session_pools`; `level_pools` remains the source of truth.

### `_build_session_pool(level: str) -> List[str]`

Private method that returns the item list for a given level:

```python
pool = self.level_pools.get(level, [])
if tier_of(level) == 1:
    return list(pool)
return random.sample(pool, min(TIER2_PLUS_SESSION_LIMIT, len(pool)))
```

Called whenever a sublevel starts or resets.

### Methods that call `_build_session_pool`

- `__init__` — initial level
- `reset_current_level` — retry / restart
- `advance_to_higher_stage` — moving to the next sublevel
- `retry_sublevel` — retry a specific sublevel
- `retry_tier` — retry all sublevels of a tier (rebuilds pool for each sublevel in the tier)

### Item-access methods that switch to `_session_pools`

- `pick_sentence_for_level(level)` — reads `_session_pools[level]`
- `advance_to_next_sentence()` — reads `_session_pools[current_level]`
- `current_pool_size()` — returns `len(_session_pools.get(current_level, []))`
- `level_goal` — set to `len(_session_pools[level])` wherever it is assigned

## Files Changed

### `src/ella_bot/core/constants.py`

Add:
```python
TIER2_PLUS_SESSION_LIMIT: int = 10
```

### `src/ella_bot/services/session_manager.py`

- Import `random` and `TIER2_PLUS_SESSION_LIMIT`
- Add `_build_session_pool(level)` method
- Add `_session_pools: Dict[str, List[str]]` instance variable, populated in `__init__` and every reset/advance method
- Switch `pick_sentence_for_level`, `advance_to_next_sentence`, `current_pool_size`, and all `level_goal` assignments to use `_session_pools`

No other files change.
