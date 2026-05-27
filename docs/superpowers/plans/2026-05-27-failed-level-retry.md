# Failed Level Retry & Main Menu Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the greyed-out Continue button with an active Retry button on failure, and give the player a "Continue / Restart from Start" choice when navigating to the main menu after passing.

**Architecture:** All changes are confined to `ResultsScene` (render, event handling, new action methods) and `EvaluationService` (one new `reset_all()` method). A `_reset_for_retry()` helper is extracted from `_do_retry()` so the reset logic can be shared with `_do_main_menu()`. A `_show_menu_confirm` flag drives an inline overlay drawn on top of the results card when the player clicks Main Menu after a pass.

**Tech Stack:** Python, Pygame, pytest

---

## File Map

| File | Change |
|---|---|
| `src/ella_bot/services/evaluation.py` | Add `reset_all()` method |
| `src/ella_bot/ui/pygame_gui/scenes/results.py` | Extract `_reset_for_retry()`, update button row, update `_do_main_menu()`, add overlay state + render + event handling, add `_do_continue_to_menu()` / `_do_restart_to_menu()` |
| `tests/test_evaluation.py` | Add `test_reset_all_clears_all_state` |
| `tests/test_results_scene.py` | Update `_make_scene` helper, update `test_main_menu_switches_scene`, add 4 new tests |

---

### Task 1: Add `EvaluationService.reset_all()`

**Files:**
- Modify: `src/ella_bot/services/evaluation.py:179-185`
- Test: `tests/test_evaluation.py`

- [ ] **Step 1: Write the failing test**

Add to the bottom of `tests/test_evaluation.py`:

```python
def test_reset_all_clears_all_state(tmp_path):
    svc = make_service(tmp_path)
    svc.record_attempt("1a", 1, "a", "uh", 0.30, 0.5, False)
    svc.record_attempt("1b", 1, "cat", "cap", 0.40, 0.3, False)
    svc.finish_tier(1)
    svc.reset_all()
    assert svc._attempts == {}
    assert svc._tier_results == {}
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_evaluation.py::test_reset_all_clears_all_state -v
```

Expected: `FAILED` — `AttributeError: 'EvaluationService' object has no attribute 'reset_all'`

- [ ] **Step 3: Implement `reset_all()`**

Open `src/ella_bot/services/evaluation.py`. After the `reset_tier` method (currently the last method, around line 182), add:

```python
    def reset_all(self) -> None:
        self._attempts.clear()
        self._tier_results.clear()
```

- [ ] **Step 4: Run test to verify it passes**

```
pytest tests/test_evaluation.py::test_reset_all_clears_all_state -v
```

Expected: `PASSED`

- [ ] **Step 5: Run the full evaluation test suite**

```
pytest tests/test_evaluation.py -v
```

Expected: all tests `PASSED`

- [ ] **Step 6: Commit**

```bash
git add src/ella_bot/services/evaluation.py tests/test_evaluation.py
git commit -m "feat: add EvaluationService.reset_all() for full session reset"
```

---

### Task 2: Extract `_reset_for_retry()` and update ResultsScene button row

**Files:**
- Modify: `src/ella_bot/ui/pygame_gui/scenes/results.py`
- Test: `tests/test_results_scene.py`

- [ ] **Step 1: Update `_make_scene` helper in the test file**

Replace the existing `_make_scene` function in `tests/test_results_scene.py` with:

```python
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
    scene._show_menu_confirm = False
    scene._confirm_continue_button = None
    scene._confirm_restart_button = None
    scene.next_button = None
    scene.menu_button = None
    return scene
```

- [ ] **Step 2: Run existing tests to confirm they still pass**

```
pytest tests/test_results_scene.py -v
```

Expected: all 5 tests `PASSED`

- [ ] **Step 3: Extract `_reset_for_retry()` in `results.py`**

In `src/ella_bot/ui/pygame_gui/scenes/results.py`, replace `_do_retry` with:

```python
    def _reset_for_retry(self) -> None:
        result = self.app.latest_result
        if self.app.latest_result_kind == "tier":
            self.app.session.retry_tier(result.tier)
            self.app.evaluation.reset_tier(result.tier)
        else:
            self.app.session.retry_sublevel(result.level)
            self.app.evaluation.reset_sublevel(result.level)

    def _do_retry(self) -> None:
        self._reset_for_retry()
        self.app.switch_scene("reading_prompt")
        self.app.active_scene._start_attempt()
```

- [ ] **Step 4: Run existing tests to confirm they still pass**

```
pytest tests/test_results_scene.py -v
```

Expected: all 5 tests `PASSED`

- [ ] **Step 5: Update button row in `render()` in `results.py`**

Find the button-drawing block near the bottom of `render()`. Replace:

```python
        next_label = "Next Level" if kind == "tier" else "Continue"
        self._draw_button(screen, self.menu_button, "Main Menu", "menu")
        self._draw_button(screen, self.next_button, next_label, "next",
                          enabled=bool(getattr(result, "passed", True)))
```

With:

```python
        if getattr(result, "passed", True):
            next_label = "Next Level" if kind == "tier" else "Continue"
        else:
            next_label = "Retry"
        self._draw_button(screen, self.menu_button, "Main Menu", "menu")
        self._draw_button(screen, self.next_button, next_label, "next")
```

- [ ] **Step 6: Update `handle_event` to dispatch to `_do_retry()` when failed**

Replace the `MOUSEBUTTONUP` block in `handle_event`:

```python
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            key = self.pressed_button
            self.pressed_button = None
            if key == "next" and self.next_button and self.next_button.collidepoint(event.pos):
                self._do_next()
            elif key == "menu" and self.menu_button and self.menu_button.collidepoint(event.pos):
                self._do_main_menu()
```

With:

```python
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            key = self.pressed_button
            self.pressed_button = None
            if key == "next" and self.next_button and self.next_button.collidepoint(event.pos):
                if getattr(self.app.latest_result, "passed", True):
                    self._do_next()
                else:
                    self._do_retry()
            elif key == "menu" and self.menu_button and self.menu_button.collidepoint(event.pos):
                self._do_main_menu()
```

- [ ] **Step 7: Fix unused `letter_rect` variable in `render()`**

Find and remove this line in `render()` (it assigns a value that is never read):

```python
        letter_rect = letter_surf.get_rect(topleft=(letter_x, letter_y))
```

- [ ] **Step 8: Run existing tests**

```
pytest tests/test_results_scene.py -v
```

Expected: all 5 tests `PASSED`

- [ ] **Step 9: Commit**

```bash
git add src/ella_bot/ui/pygame_gui/scenes/results.py tests/test_results_scene.py
git commit -m "refactor: extract _reset_for_retry, activate retry button on failure"
```

---

### Task 3: Update `_do_main_menu()` — failure path resets session

**Files:**
- Modify: `src/ella_bot/ui/pygame_gui/scenes/results.py`
- Test: `tests/test_results_scene.py`

- [ ] **Step 1: Write the failing test for failure path**

Add to `tests/test_results_scene.py`:

```python
def test_main_menu_on_failure_resets_sublevel_and_switches_to_menu():
    scene = _make_scene(kind="sublevel", passed=False, level="1a")
    scene._do_main_menu()
    scene.app.session.retry_sublevel.assert_called_once_with("1a")
    scene.app.evaluation.reset_sublevel.assert_called_once_with("1a")
    scene.app.switch_scene.assert_called_once_with("main_menu")
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_results_scene.py::test_main_menu_on_failure_resets_sublevel_and_switches_to_menu -v
```

Expected: `FAILED` — `AssertionError: Expected call: retry_sublevel('1a') / Actual call: not called`

- [ ] **Step 3: Update `_do_main_menu()` in `results.py`**

Replace the current `_do_main_menu` method:

```python
    def _do_main_menu(self) -> None:
        self.app.switch_scene("main_menu")
```

With:

```python
    def _do_main_menu(self) -> None:
        result = self.app.latest_result
        if not getattr(result, "passed", True):
            self._reset_for_retry()
            self.app.switch_scene("main_menu")
        else:
            self._show_menu_confirm = True
```

- [ ] **Step 4: Update the existing `test_main_menu_switches_scene` test**

The existing test called `_do_main_menu()` with `passed=True` (default) and expected `switch_scene("main_menu")`. That behaviour has changed — on success it now shows the confirm overlay instead. Rename and update the test:

Replace:

```python
def test_main_menu_switches_scene():
    scene = _make_scene()
    scene._do_main_menu()
    scene.app.switch_scene.assert_called_once_with("main_menu")
```

With:

```python
def test_main_menu_on_success_shows_confirm_overlay():
    scene = _make_scene(passed=True)
    scene._do_main_menu()
    assert scene._show_menu_confirm is True
    scene.app.switch_scene.assert_not_called()
```

- [ ] **Step 5: Run tests**

```
pytest tests/test_results_scene.py -v
```

Expected: all tests `PASSED` (the renamed test + the new failure-path test)

- [ ] **Step 6: Commit**

```bash
git add src/ella_bot/ui/pygame_gui/scenes/results.py tests/test_results_scene.py
git commit -m "feat: main menu on failure resets level, on success shows confirm overlay"
```

---

### Task 4: Success confirm overlay — render, events, actions

**Files:**
- Modify: `src/ella_bot/ui/pygame_gui/scenes/results.py`
- Test: `tests/test_results_scene.py`

- [ ] **Step 1: Write failing tests for the two confirm actions**

Add to `tests/test_results_scene.py`:

```python
def test_confirm_continue_advances_stage_and_goes_to_menu():
    scene = _make_scene(passed=True)
    scene._do_continue_to_menu()
    scene.app.session.advance_to_higher_stage.assert_called_once()
    scene.app.switch_scene.assert_called_once_with("main_menu")


def test_confirm_restart_resets_to_start_and_goes_to_menu():
    scene = _make_scene(passed=True)
    scene._do_restart_to_menu()
    scene.app.session.reset_to_start.assert_called_once()
    scene.app.evaluation.reset_all.assert_called_once()
    scene.app.switch_scene.assert_called_once_with("main_menu")
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_results_scene.py::test_confirm_continue_advances_stage_and_goes_to_menu tests/test_results_scene.py::test_confirm_restart_resets_to_start_and_goes_to_menu -v
```

Expected: both `FAILED` — `AttributeError: ... has no attribute '_do_continue_to_menu'`

- [ ] **Step 3: Add new state to `__init__` in `results.py`**

In `ResultsScene.__init__`, after `self.menu_button = None` add:

```python
        self._show_menu_confirm = False
        self._confirm_continue_button = None
        self._confirm_restart_button = None
```

- [ ] **Step 4: Reset state in `on_enter()` in `results.py`**

In `ResultsScene.on_enter`, after `self.pressed_button = None` add:

```python
        self._show_menu_confirm = False
```

- [ ] **Step 5: Add `_do_continue_to_menu()` and `_do_restart_to_menu()` in `results.py`**

After `_do_main_menu`, add:

```python
    def _do_continue_to_menu(self) -> None:
        self.app.session.advance_to_higher_stage()
        self.app.switch_scene("main_menu")

    def _do_restart_to_menu(self) -> None:
        self.app.session.reset_to_start()
        self.app.evaluation.reset_all()
        self.app.switch_scene("main_menu")
```

- [ ] **Step 6: Run new tests to verify they pass**

```
pytest tests/test_results_scene.py::test_confirm_continue_advances_stage_and_goes_to_menu tests/test_results_scene.py::test_confirm_restart_resets_to_start_and_goes_to_menu -v
```

Expected: both `PASSED`

- [ ] **Step 7: Add `_draw_confirm_overlay()` to `results.py`**

After `_draw_button`, add:

```python
    def _draw_confirm_overlay(self, screen) -> None:
        width, height = screen.get_size()
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))

        dlg_w = int(width * 0.62)
        dlg_h = int(height * 0.36)
        dlg_x = (width - dlg_w) // 2
        dlg_y = (height - dlg_h) // 2
        dlg_rect = pygame.Rect(dlg_x, dlg_y, dlg_w, dlg_h)
        pygame.draw.rect(screen, _WHITE, dlg_rect, border_radius=20)
        pygame.draw.rect(screen, _BTN_OUTLINE, dlg_rect, width=4, border_radius=20)

        msg = self.app.font_body.render("Where would you like to go?", True, _TEXT_DARK)
        screen.blit(msg, msg.get_rect(center=(width // 2, dlg_y + int(dlg_h * 0.30))))

        btn_w, btn_h = 190, 62
        gap = 20
        total_w = btn_w * 2 + gap
        btn_y = dlg_y + dlg_h - btn_h - 24
        self._confirm_continue_button = pygame.Rect(
            width // 2 - total_w // 2, btn_y, btn_w, btn_h
        )
        self._confirm_restart_button = pygame.Rect(
            width // 2 - total_w // 2 + btn_w + gap, btn_y, btn_w, btn_h
        )
        self._draw_button(screen, self._confirm_continue_button, "Continue", "confirm_continue")
        self._draw_button(screen, self._confirm_restart_button, "Restart", "confirm_restart")
```

- [ ] **Step 8: Call `_draw_confirm_overlay()` at the end of `render()`**

In `render()`, after the two `pygame.draw.rect` border lines at the very end, add:

```python
        if self._show_menu_confirm:
            self._draw_confirm_overlay(screen)
```

- [ ] **Step 9: Update `handle_event()` to route clicks while overlay is visible**

Replace the entire `handle_event` method with:

```python
    def handle_event(self, event) -> None:
        if self._show_menu_confirm:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for key, rect in (
                    ("confirm_continue", self._confirm_continue_button),
                    ("confirm_restart", self._confirm_restart_button),
                ):
                    if rect and rect.collidepoint(event.pos):
                        self.pressed_button = key
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                key = self.pressed_button
                self.pressed_button = None
                if key == "confirm_continue" and self._confirm_continue_button and self._confirm_continue_button.collidepoint(event.pos):
                    self._do_continue_to_menu()
                elif key == "confirm_restart" and self._confirm_restart_button and self._confirm_restart_button.collidepoint(event.pos):
                    self._do_restart_to_menu()
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for key, rect in (("next", self.next_button), ("menu", self.menu_button)):
                if rect and rect.collidepoint(event.pos):
                    self.pressed_button = key
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            key = self.pressed_button
            self.pressed_button = None
            if key == "next" and self.next_button and self.next_button.collidepoint(event.pos):
                if getattr(self.app.latest_result, "passed", True):
                    self._do_next()
                else:
                    self._do_retry()
            elif key == "menu" and self.menu_button and self.menu_button.collidepoint(event.pos):
                self._do_main_menu()
```

- [ ] **Step 10: Run the full test suite**

```
pytest tests/test_results_scene.py tests/test_evaluation.py -v
```

Expected: all tests `PASSED`

- [ ] **Step 11: Run the full project test suite to check for regressions**

```
pytest -v
```

Expected: all tests `PASSED`

- [ ] **Step 12: Commit**

```bash
git add src/ella_bot/ui/pygame_gui/scenes/results.py tests/test_results_scene.py
git commit -m "feat: add continue/restart confirm overlay on results main-menu navigation"
```
