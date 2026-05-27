# Failed Level Retry & Main Menu Navigation Design

**Date:** 2026-05-27
**Scope:** `results.py`, `tests/test_results_scene.py`

---

## Problem

Two bugs when a player fails a sublevel (e.g. Level 1A with rating D):

1. The "Continue/Next Level" button is greyed out with no way to retry — the player is stuck.
2. Clicking "Main Menu" then "Start" resumes from the last item of the failed level rather than restarting it from item 1.

---

## Solution Overview

All changes are contained in `ResultsScene` (`results.py`). No new files or components are needed.

---

## Section 1 — Button Row

The right button adapts based on `result.passed`:

| Result | Left button | Right button |
|---|---|---|
| Failed (`passed=False`) | "Main Menu" (active) | "Retry" (active, pink) |
| Passed (`passed=True`) | "Main Menu" (active) | "Continue" / "Next Level" (active, pink) |

The disabled greyed-out state is removed. On failure, the right button label becomes "Retry" and is always active. The existing `_do_retry()` method handles the correct reset logic — it is wired to the button click.

**Button label rules (right button):**
- `passed=False` → "Retry"
- `passed=True` and `kind == "tier"` → "Next Level"
- `passed=True` and `kind == "sublevel"` → "Continue"

---

## Section 2 — "Main Menu" Button Behaviour

### On failure
`_do_main_menu()` calls `_do_retry()` first (resets session + evaluation for the failed level/tier back to item 1), then switches to `main_menu`. No modal. Failure always restarts.

`_do_retry()` already handles both kinds:
- `kind == "tier"` → `session.retry_tier(tier)` + `evaluation.reset_tier(tier)`
- `kind == "sublevel"` → `session.retry_sublevel(level)` + `evaluation.reset_sublevel(level)`

### On success
`_do_main_menu()` sets `self._show_menu_confirm = True`, which triggers an inline confirmation overlay. The overlay presents two choices:

- **"Continue"** — calls `session.advance_to_higher_stage()`, then switches to `main_menu`. Pressing Start from main menu begins item 1 of the next sublevel.
- **"Restart from Start"** — calls `session.reset_to_start()` and `evaluation.reset_all()` (new method, clears `_attempts` and `_tier_results`), then switches to `main_menu`. Pressing Start from main menu begins Level 1A item 1.

The overlay is drawn identically to the exit-confirm dialog in `MainMenuScene`: semi-transparent black overlay + white rounded dialog box with two pink buttons. `handle_event` routes all clicks to the confirm buttons while `_show_menu_confirm` is True.

---

## Section 3 — New State

```python
self._show_menu_confirm: bool = False
```

- Initialised to `False` in `__init__`
- Reset to `False` in `on_enter()` (prevents bleed across scene transitions)
- Set to `True` only when "Main Menu" is clicked on a passing result

No other new state is needed.

---

## Section 4 — Edge Cases

- `result.passed` defaults to `True` if the attribute is absent (safe for `TierResult`).
- `_show_menu_confirm` is always cleared in `on_enter()`, so it cannot persist across visits.
- `advance_to_higher_stage()` is only called at the point the player explicitly chooses "Continue" — not on scene entry — matching the existing pattern in `_do_next()`.

---

## Section 5 — Tests

Add three new test cases to `tests/test_results_scene.py`:

1. **Retry on failure** — clicking the right button on a failed result calls `_do_retry()` and routes to `reading_prompt`.
2. **Main Menu on failure** — clicking "Main Menu" on a failed result resets the session (calls `retry_sublevel` or `retry_tier`) and routes to `main_menu`.
3. **Main Menu on success — confirm overlay**:
   - Clicking "Main Menu" on a passed result opens the confirm overlay (`_show_menu_confirm == True`).
   - Clicking "Continue" in the overlay calls `advance_to_higher_stage()` and routes to `main_menu`.
   - Clicking "Restart from Start" calls `reset_to_start()` and routes to `main_menu`.

---

## Files Changed

| File | Change |
|---|---|
| `src/ella_bot/ui/pygame_gui/scenes/results.py` | Button row logic, `_show_menu_confirm` state, overlay rendering, updated `_do_main_menu()` |
| `src/ella_bot/services/evaluation.py` | Add `reset_all()` method |
| `tests/test_results_scene.py` | Three new test cases |
