# Auto-Continue Reading Attempts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-start reading attempts on scene entry (after 1.5 s) and auto-continue after each attempt completes, removing the need for the user to tap between items.

**Architecture:** Two triggers are added to `ReadingPromptScene.update()`. A `_auto_start_at` float timestamp (set in `on_enter()`) handles the initial 1.5 s delay. A state check (`state == "listening"` and `not prompt_active`) handles every subsequent auto-advance. Manual taps still work — `_start_attempt()` already guards against double-starts. No changes to `attempt_runner.py` or any other file.

**Tech Stack:** Python 3, Pygame, `time.monotonic()`, `unittest.mock`.

---

## File Structure

| File | Role |
|---|---|
| `src/ella_bot/ui/pygame_gui/scenes/reading_prompt.py` | Add `_auto_start_at` field; update `__init__`, `on_enter`, `update` |
| `tests/test_reading_prompt_auto_continue.py` | New — 6 unit tests covering both triggers and all guard conditions |

---

### Task 1: Tests (write failing tests first)

**Files:**
- Create: `tests/test_reading_prompt_auto_continue.py`

The test helper builds a minimal `ReadingPromptScene` instance without invoking `__init__` (same pattern used in `tests/test_results_scene.py`). It mocks `_drain_event_queue`, `_start_attempt`, `bot`, `modal`, and `worker_thread`.

- [ ] **Step 1: Create the test file**

```python
# tests/test_reading_prompt_auto_continue.py
import time
from unittest.mock import MagicMock


def _make_scene(state="idle", prompt_active=False, is_paused=False,
                modal_visible=False, auto_start_at=None):
    from ella_bot.ui.pygame_gui.scenes.reading_prompt import ReadingPromptScene
    app = MagicMock()
    app.state = state
    app.prompt_active = prompt_active
    scene = object.__new__(ReadingPromptScene)
    scene.app = app
    scene.is_paused = is_paused
    scene._auto_start_at = auto_start_at
    scene.modal = MagicMock()
    scene.modal.visible = modal_visible
    scene.bot = MagicMock()
    scene.worker_thread = None
    scene._drain_event_queue = MagicMock()
    scene._start_attempt = MagicMock()
    return scene


def test_timer_fires_when_expired():
    """Timer trigger calls _start_attempt and clears _auto_start_at."""
    scene = _make_scene(auto_start_at=time.monotonic() - 0.1)
    scene.update(0)
    scene._start_attempt.assert_called_once()
    assert scene._auto_start_at is None


def test_timer_does_not_fire_before_expiry():
    """Timer trigger does not fire when timestamp is in the future."""
    scene = _make_scene(auto_start_at=time.monotonic() + 60.0)
    scene.update(0)
    scene._start_attempt.assert_not_called()


def test_state_trigger_fires_when_listening_no_prompt():
    """State trigger fires when state is listening and prompt is inactive."""
    scene = _make_scene(state="listening", prompt_active=False, auto_start_at=None)
    scene.update(0)
    scene._start_attempt.assert_called_once()


def test_state_trigger_does_not_fire_when_prompt_active():
    """State trigger is blocked while an attempt is already running."""
    scene = _make_scene(state="listening", prompt_active=True, auto_start_at=None)
    scene.update(0)
    scene._start_attempt.assert_not_called()


def test_neither_trigger_fires_when_paused():
    """Both triggers are blocked while the session is paused."""
    # Timer expired + listening state, but paused
    scene = _make_scene(
        state="listening",
        is_paused=True,
        auto_start_at=time.monotonic() - 0.1,
    )
    scene.update(0)
    scene._start_attempt.assert_not_called()


def test_neither_trigger_fires_when_modal_visible():
    """Both triggers are blocked while the pause modal is open."""
    scene = _make_scene(
        state="listening",
        modal_visible=True,
        auto_start_at=time.monotonic() - 0.1,
    )
    scene.update(0)
    scene._start_attempt.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they all fail**

```bash
python3 -m pytest tests/test_reading_prompt_auto_continue.py -v
```

Expected: All 6 tests FAIL (either `AttributeError: _auto_start_at` or `assert_called_once` failures, depending on which tests can even import the scene).

---

### Task 2: Implementation

**Files:**
- Modify: `src/ella_bot/ui/pygame_gui/scenes/reading_prompt.py`
  - `__init__` (lines 26–36): add `self._auto_start_at`
  - `on_enter` (lines 38–44): set `self._auto_start_at = time.monotonic() + 1.5`
  - `update` (lines 110–122): add both auto-start triggers

- [ ] **Step 1: Add `_auto_start_at` to `__init__`**

Find the `__init__` method. After the last attribute assignment (`self.runner = ...`), add one line:

```python
def __init__(self, app):
    super().__init__(app)
    self.worker_thread: Optional[threading.Thread] = None
    self.idle_timeout_seconds = 10
    self.last_activity_monotonic = time.monotonic()
    self.modal = PauseModal(self.app)
    self.is_paused = False
    self.menu_button_rect: Optional[pygame.Rect] = None
    self._icon_menu = None
    self.bot = BotSprite()
    self.runner = AttemptRunner(self.app, lambda: self.is_paused)
    self._auto_start_at: float | None = None
```

- [ ] **Step 2: Set the entry timer in `on_enter`**

Find `on_enter`. Add one line at the end:

```python
def on_enter(self) -> None:
    self.app.state = "idle"
    self.app.message = ""
    self.app.prompt_active = False
    self.modal.close()
    self.is_paused = False
    self._touch_activity()
    self.app.animator.set_state("idle", reset=True)
    self._auto_start_at = time.monotonic() + 1.5
```

- [ ] **Step 3: Add both triggers to `update`**

Find `update`. Insert the new auto-start block **after** the `bot.update` call and **before** the idle-timeout block:

```python
def update(self, now_ms: int) -> None:
    self._drain_event_queue()
    if not self.modal.visible:
        self.bot.update(now_ms, self.app.state)

    if self.modal.visible:
        return

    if not self.is_paused and not self.app.prompt_active:
        if self._auto_start_at is not None and time.monotonic() >= self._auto_start_at:
            self._auto_start_at = None
            self._start_attempt()
        elif self._auto_start_at is None and self.app.state == "listening":
            self._start_attempt()

    if self.app.state == "listening" and not self.app.prompt_active:
        if time.monotonic() - self.last_activity_monotonic >= self.idle_timeout_seconds:
            self.app.event_queue.put(StateChanged("idle"))
            self.app.event_queue.put(MessageChanged(""))
```

- [ ] **Step 4: Run the auto-continue tests — all 6 should pass**

```bash
python3 -m pytest tests/test_reading_prompt_auto_continue.py -v
```

Expected output:
```
PASSED tests/test_reading_prompt_auto_continue.py::test_timer_fires_when_expired
PASSED tests/test_reading_prompt_auto_continue.py::test_timer_does_not_fire_before_expiry
PASSED tests/test_reading_prompt_auto_continue.py::test_state_trigger_fires_when_listening_no_prompt
PASSED tests/test_reading_prompt_auto_continue.py::test_state_trigger_does_not_fire_when_prompt_active
PASSED tests/test_reading_prompt_auto_continue.py::test_neither_trigger_fires_when_paused
PASSED tests/test_reading_prompt_auto_continue.py::test_neither_trigger_fires_when_modal_visible
6 passed
```

- [ ] **Step 5: Run the full test suite to check for regressions**

```bash
python3 -m pytest tests/ --ignore=tests/test_tts_piper.py -q
```

Expected: no new failures (pre-existing failures in `test_feedback.py` and `test_validators.py` are known and unrelated).

- [ ] **Step 6: Commit**

```bash
git add src/ella_bot/ui/pygame_gui/scenes/reading_prompt.py \
        tests/test_reading_prompt_auto_continue.py
git commit -m "feat: auto-continue reading attempts without requiring tap"
```
