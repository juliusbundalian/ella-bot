# Auto-Continue Reading Attempts Design

**Date:** 2026-05-27
**Scope:** `reading_prompt.py`, `tests/test_reading_prompt_auto_continue.py`

---

## Problem

After each reading attempt (correct or incorrect), the app transitions to the "listening" state but waits for the user to tap the screen before starting the next attempt. Users must tap between every item, which interrupts the flow. The reading session should advance automatically.

---

## Solution Overview

Two conditions in `ReadingPromptScene.update()` auto-trigger `_start_attempt()`. No changes needed to `attempt_runner.py`, `session`, `evaluation`, or any other file.

---

## Section 1 — New State

```python
self._auto_start_at: float | None = None
```

- Initialised to `None` in `__init__`
- Set to `time.monotonic() + 1.5` in `on_enter()` on every scene entry
- Cleared (set to `None`) as soon as the timer fires and `_start_attempt()` is called
- Remains `None` for the rest of the session; post-attempt auto-continue uses the state check instead

---

## Section 2 — Trigger Logic in `update()`

Two triggers, both gated by the same preconditions:

**Preconditions (both triggers):**
- `not self.is_paused`
- `not self.modal.visible`
- `not self.app.prompt_active`

**Trigger 1 — Initial entry timer:**
```python
if self._auto_start_at is not None and time.monotonic() >= self._auto_start_at:
    self._auto_start_at = None
    self._start_attempt()
```

Fires once, 1.5 seconds after `on_enter()`. Handles the very first attempt of a session or sublevel.

**Trigger 2 — Post-attempt state check:**
```python
elif self._auto_start_at is None and self.app.state == "listening":
    self._start_attempt()
```

Fires when `attempt_runner.py` finishes its 0.6 s sleep and posts `StateChanged("listening")`. The `_auto_start_at is None` guard ensures this branch is inactive during the initial 1.5 s entry window (prevents a spurious trigger if state somehow reaches "listening" before the timer fires).

---

## Section 3 — Manual Tap Preserved

`handle_event()` still calls `_start_attempt()` on `MOUSEBUTTONDOWN`. `_start_attempt()` already guards against double-starts:

```python
if self.worker_thread and self.worker_thread.is_alive():
    return
```

Users can tap at any time to start immediately (e.g., before the 1.5 s timer expires on first entry).

---

## Section 4 — Idle Timeout Preserved

The existing 10-second idle timeout in `update()` remains unchanged. With auto-continue it will never fire in normal use, but it acts as a safety net if `_start_attempt()` ever fails silently.

---

## Section 5 — Edge Cases

- **Pause:** `is_paused` check blocks both triggers while the pause modal is open.
- **Modal visible:** `modal.visible` check blocks both triggers.
- **Sublevel complete:** `SubLevelCompleted` switches to ResultsScene before `StateChanged("listening")` is ever posted, so neither trigger fires.
- **Return from ResultsScene:** `on_enter()` is called again, resetting `_auto_start_at = now + 1.5`. First attempt of the new sublevel auto-starts after 1.5 s.
- **Worker still alive during 0.6 s sleep:** `worker_thread.is_alive()` is True during the sleep, so a tap or a stray trigger during those 0.6 s is safely ignored by `_start_attempt()`.

---

## Section 6 — Tests

New file `tests/test_reading_prompt_auto_continue.py`:

1. **Timer trigger fires after delay** — `_auto_start_at` set to an already-expired time, `update()` called; verify `_start_attempt()` is invoked and `_auto_start_at` becomes `None`.
2. **Timer trigger does not fire before delay** — `_auto_start_at` set to future time; verify `_start_attempt()` is NOT invoked.
3. **Post-attempt trigger fires when listening, no prompt active** — `_auto_start_at = None`, `state = "listening"`, `prompt_active = False`; verify `_start_attempt()` is invoked.
4. **Post-attempt trigger does not fire when prompt is active** — `_auto_start_at = None`, `state = "listening"`, `prompt_active = True`; verify NOT invoked.
5. **Neither trigger fires when paused** — both timer expired and state listening; `is_paused = True`; verify NOT invoked.
6. **Neither trigger fires when modal visible** — both timer expired and state listening; `modal.visible = True`; verify NOT invoked.

---

## Files Changed

| File | Change |
|---|---|
| `src/ella_bot/ui/pygame_gui/scenes/reading_prompt.py` | Add `_auto_start_at`, update `on_enter()`, update `update()` |
| `tests/test_reading_prompt_auto_continue.py` | New — 6 test cases |
