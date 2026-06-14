# Attempt Limits Per Item by Tier

**Date:** 2026-06-14
**Status:** Approved

## Overview

Limit how many times a user can attempt each reading item before being automatically advanced to the next one. Tier 1 levels allow one attempt per item; Tier 2–4 levels allow three.

## Behaviour

### Tier 1 (levels 1a–1g) — 1 attempt per item

After the user reads the item once, Ella gives feedback and immediately moves to the next item regardless of whether the answer was correct or not. There is no retry loop.

### Tier 2–4 (levels 2a, 2b, 2c, 2d, 3, 4) — 3 attempts per item

Existing retry behaviour is preserved up to 3 attempts. On the 3rd wrong attempt, Ella speaks one of the encouragement phrases below and advances to the next item.

**Exhaustion phrases (picked at random):**

1. "That's okay! Keep going, you're doing great!"
2. "Nice try! Let's move to the next one."
3. "Don't worry, we'll come back to tricky ones. Keep it up!"
4. "Good effort! Moving on."
5. "That one was tough! You're still doing amazing."

## Level Completion

`session.completed_in_level` increments on **both** correct answers and exhausted items (attempt limit reached without a correct answer). This ensures the sublevel goal is always reachable and the results screen is shown after all items in the pool have been attempted.

Exhausted items are recorded in the evaluation log as incorrect (`correct=False`), so accuracy reporting is unaffected.

## Implementation Scope

### `src/ella_bot/core/constants.py`

Add a helper that returns the max attempts for a given level:

```python
def max_attempts_for_level(level: str) -> int:
    return 1 if tier_of(level) == 1 else 3
```

### `src/ella_bot/services/attempt_runner.py`

- Add two instance variables to `AttemptRunner.__init__`:
  - `self._item_attempt_count: int = 0`
  - `self._current_item_sentence: str = ""`
- At the start of the scoring block in `run()`, detect when the item has changed (i.e. `session.expected_sentence != self._current_item_sentence`) and reset the counter. Then increment the counter.
- After scoring, compute `exhausted = not correct and self._item_attempt_count >= max_attempts_for_level(level)`.
- When `correct or exhausted`:
  - Increment `session.completed_in_level`.
  - Reset `self._item_attempt_count = 0`.
  - If `exhausted` and audio feedback is enabled: speak a randomly chosen exhaustion phrase.
  - Advance to next sentence.
- When neither correct nor exhausted: existing "Give it another try!" retry path continues unchanged.

### No other files change

`session_manager.py`, `evaluation.py`, and all UI scenes are unaffected.
