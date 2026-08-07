# Touchscreen Profile Keyboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a touchscreen QWERTY keyboard to ELLA's Create Profile and Rename Profile modals while retaining physical-keyboard support.

**Architecture:** A focused `OnScreenKeyboard` Pygame component owns responsive key layout, pressed state, shift state, drawing, and touch hit testing. `ProfilesScene` owns the profile-name string, translates semantic keyboard actions into edits, and lays out the expanded name modal around the keyboard.

**Tech Stack:** Python 3.10+, pygame-ce, pytest, `unittest.mock`

## Global Constraints

- The embedded keyboard appears only in Create Profile and Rename Profile modals.
- Preserve Pygame `TEXTINPUT` and `KEYDOWN` handling for physical keyboards.
- Preserve the existing profile-name limit of 20 characters and all `ProfileStore` validation.
- Provide QWERTY letters, Shift, Space, apostrophe, hyphen, and Backspace.
- Shift capitalizes only the next alphabetic key, then automatically returns to
  lowercase.
- A key activates only when press and release occur on the same key.
- Do not launch or configure Squeekboard, `wvkbd`, or Matchbox Keyboard.
- Keep the complete modal inside the configured 1280x720 screen.
- Do not alter unrelated profile selection, reset, delete, or persistence behavior.

---

## File Structure

- Create `src/ella_bot/ui/pygame_gui/components/on_screen_keyboard.py`: keyboard action type, responsive key geometry, rendering, shift state, and pointer handling.
- Create `tests/test_on_screen_keyboard.py`: isolated component layout and interaction tests.
- Modify `src/ella_bot/ui/pygame_gui/scenes/profiles.py`: own the keyboard instance, route touch actions into `name_input`, reset/cancel state with modal lifecycle, and expand the name modal.
- Modify `tests/test_profiles_scene.py`: cover Create/Rename touch input, character limits, modal lifecycle, cancellation, and retained physical input.

---

### Task 1: Reusable On-Screen Keyboard Component

**Files:**
- Create: `src/ella_bot/ui/pygame_gui/components/on_screen_keyboard.py`
- Create: `tests/test_on_screen_keyboard.py`

**Interfaces:**
- Consumes: `pygame.Rect`, `pygame.Surface`, and a Pygame font with `render(text, antialias, color)`.
- Produces: `KeyboardAction(kind: Literal["text", "backspace", "shift"], text: str = "")`.
- Produces: `OnScreenKeyboard(font)`, `.draw(screen, rect)`, `.handle_mouse_down(pos) -> bool`, `.handle_mouse_up(pos) -> KeyboardAction | None`, `.reset()`, `.cancel_press()`, `.uppercase`, and read-only `.key_rects` for scene tests.

- [ ] **Step 1: Write failing tests for layout and key activation**

Create `tests/test_on_screen_keyboard.py`:

```python
from __future__ import annotations

import pygame

from ella_bot.ui.pygame_gui.components.on_screen_keyboard import (
    KeyboardAction,
    OnScreenKeyboard,
)


def _keyboard():
    pygame.font.init()
    return OnScreenKeyboard(pygame.font.SysFont(None, 28))


def _draw(keyboard, rect=pygame.Rect(40, 30, 1000, 260)):
    screen = pygame.Surface((1280, 720))
    keyboard.draw(screen, rect)
    return screen


def test_keyboard_draws_all_keys_inside_supplied_rect():
    keyboard = _keyboard()
    bounds = pygame.Rect(40, 30, 1000, 260)

    _draw(keyboard, bounds)

    assert set("qwertyuiopasdfghjklzxcvbnm") <= set(keyboard.key_rects)
    assert {"shift", "space", "apostrophe", "hyphen", "backspace"} <= set(
        keyboard.key_rects
    )
    assert all(bounds.contains(rect) for rect in keyboard.key_rects.values())


def test_press_and_release_on_letter_emits_text_action():
    keyboard = _keyboard()
    _draw(keyboard)
    point = keyboard.key_rects["q"].center

    assert keyboard.handle_mouse_down(point) is True
    assert keyboard.handle_mouse_up(point) == KeyboardAction("text", "q")


def test_release_outside_pressed_key_cancels_action():
    keyboard = _keyboard()
    _draw(keyboard)

    keyboard.handle_mouse_down(keyboard.key_rects["q"].center)

    assert keyboard.handle_mouse_up(keyboard.key_rects["w"].center) is None
```

- [ ] **Step 2: Run the new tests and verify they fail because the component is missing**

Run:

```bash
.venv/bin/pytest tests/test_on_screen_keyboard.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'ella_bot.ui.pygame_gui.components.on_screen_keyboard'`.

- [ ] **Step 3: Add failing tests for Shift and special actions**

Append to `tests/test_on_screen_keyboard.py`:

```python
def _tap(keyboard, key):
    point = keyboard.key_rects[key].center
    assert keyboard.handle_mouse_down(point) is True
    return keyboard.handle_mouse_up(point)


def test_shift_capitalizes_only_the_next_letter():
    keyboard = _keyboard()
    _draw(keyboard)

    assert _tap(keyboard, "shift") == KeyboardAction("shift")
    assert keyboard.uppercase is True
    assert _tap(keyboard, "q") == KeyboardAction("text", "Q")
    assert keyboard.uppercase is False
    assert _tap(keyboard, "w") == KeyboardAction("text", "w")

    keyboard.reset()

    assert keyboard.uppercase is False


def test_special_keys_emit_semantic_actions():
    keyboard = _keyboard()
    _draw(keyboard)

    assert _tap(keyboard, "space") == KeyboardAction("text", " ")
    assert _tap(keyboard, "apostrophe") == KeyboardAction("text", "'")
    assert _tap(keyboard, "hyphen") == KeyboardAction("text", "-")
    assert _tap(keyboard, "backspace") == KeyboardAction("backspace")


def test_cancel_press_prevents_a_later_release_from_activating():
    keyboard = _keyboard()
    _draw(keyboard)
    point = keyboard.key_rects["q"].center
    keyboard.handle_mouse_down(point)

    keyboard.cancel_press()

    assert keyboard.handle_mouse_up(point) is None
```

- [ ] **Step 4: Implement the keyboard component minimally**

Create `src/ella_bot/ui/pygame_gui/components/on_screen_keyboard.py` with this structure:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pygame


@dataclass(frozen=True)
class KeyboardAction:
    kind: Literal["text", "backspace", "shift"]
    text: str = ""


@dataclass(frozen=True)
class _Key:
    key_id: str
    label: str
    action: KeyboardAction
    weight: float = 1.0


class OnScreenKeyboard:
    _LETTER_ROWS = ("qwertyuiop", "asdfghjkl", "zxcvbnm")

    def __init__(self, font) -> None:
        self.font = font
        self.uppercase = False
        self._pressed_key: str | None = None
        self._keys: dict[str, _Key] = {}
        self._key_rects: dict[str, pygame.Rect] = {}

    @property
    def key_rects(self) -> dict[str, pygame.Rect]:
        return dict(self._key_rects)

    def reset(self) -> None:
        self.uppercase = False
        self.cancel_press()

    def cancel_press(self) -> None:
        self._pressed_key = None

    def _rows(self) -> tuple[tuple[_Key, ...], ...]:
        letter_rows = []
        for letters in self._LETTER_ROWS:
            row = tuple(
                _Key(
                    letter,
                    letter.upper() if self.uppercase else letter,
                    KeyboardAction(
                        "text", letter.upper() if self.uppercase else letter
                    ),
                )
                for letter in letters
            )
            letter_rows.append(row)
        controls = (
            _Key("shift", "Shift", KeyboardAction("shift"), 1.35),
            _Key("apostrophe", "'", KeyboardAction("text", "'"), 0.75),
            _Key("space", "Space", KeyboardAction("text", " "), 4.0),
            _Key("hyphen", "-", KeyboardAction("text", "-"), 0.75),
            _Key("backspace", "Back", KeyboardAction("backspace"), 1.6),
        )
        return (*letter_rows, controls)

    def _layout(self, bounds: pygame.Rect) -> None:
        rows = self._rows()
        row_gap = max(4, min(8, bounds.height // 30))
        key_gap = max(4, min(8, bounds.width // 120))
        key_height = (bounds.height - row_gap * (len(rows) - 1)) // len(rows)
        self._keys = {}
        self._key_rects = {}
        for row_index, row in enumerate(rows):
            total_weight = sum(key.weight for key in row)
            usable_width = bounds.width - key_gap * (len(row) - 1)
            unit = usable_width / total_weight
            widths = [int(unit * key.weight) for key in row]
            widths[-1] += usable_width - sum(widths)
            row_width = sum(widths) + key_gap * (len(row) - 1)
            x = bounds.centerx - row_width // 2
            y = bounds.top + row_index * (key_height + row_gap)
            for key, width in zip(row, widths):
                self._keys[key.key_id] = key
                self._key_rects[key.key_id] = pygame.Rect(
                    x, y, width, key_height
                )
                x += width + key_gap

    def draw(self, screen: pygame.Surface, bounds: pygame.Rect) -> None:
        self._layout(pygame.Rect(bounds))
        for key_id, rect in self._key_rects.items():
            pressed = key_id == self._pressed_key
            active_shift = key_id == "shift" and self.uppercase
            fill = (200, 160, 20) if pressed else (242, 210, 20)
            if active_shift and not pressed:
                fill = (255, 232, 90)
            pygame.draw.rect(screen, (25, 5, 35), rect.move(3, 3), border_radius=10)
            pygame.draw.rect(screen, fill, rect, border_radius=10)
            pygame.draw.rect(screen, (175, 141, 55), rect, width=2, border_radius=10)
            label = self.font.render(self._keys[key_id].label, True, (35, 10, 45))
            screen.blit(label, label.get_rect(center=rect.center))

    def _key_at(self, pos) -> str | None:
        return next(
            (key_id for key_id, rect in self._key_rects.items() if rect.collidepoint(pos)),
            None,
        )

    def handle_mouse_down(self, pos) -> bool:
        self._pressed_key = self._key_at(pos)
        return self._pressed_key is not None

    def handle_mouse_up(self, pos) -> KeyboardAction | None:
        pressed = self._pressed_key
        self._pressed_key = None
        if pressed is None or self._key_at(pos) != pressed:
            return None
        action = self._keys[pressed].action
        if action.kind == "shift":
            self.uppercase = not self.uppercase
            return action
        if len(pressed) == 1 and pressed.isalpha():
            letter = pressed.upper() if self.uppercase else pressed
            self.uppercase = False
            return KeyboardAction("text", letter)
        return action
```

Keep line lengths formatted consistently with the repository. Do not add desktop-keyboard dependencies or subprocess calls.

- [ ] **Step 5: Run component tests and verify they pass**

Run:

```bash
.venv/bin/pytest tests/test_on_screen_keyboard.py -q
```

Expected: `6 passed`.

- [ ] **Step 6: Commit the isolated component**

```bash
git add src/ella_bot/ui/pygame_gui/components/on_screen_keyboard.py tests/test_on_screen_keyboard.py
git commit -m "feat: add touchscreen keyboard component"
```

---

### Task 2: Integrate Touch Input into Create and Rename Modals

**Files:**
- Modify: `src/ella_bot/ui/pygame_gui/scenes/profiles.py`
- Modify: `tests/test_profiles_scene.py`

**Interfaces:**
- Consumes: `OnScreenKeyboard(font)` and `KeyboardAction` from Task 1.
- Produces: `ProfilesScene.keyboard`, `_apply_keyboard_action(action: KeyboardAction | None) -> None`, and name-modal touch behavior.

- [ ] **Step 1: Write failing scene tests for touchscreen typing and editing**

Update imports in `tests/test_profiles_scene.py`:

```python
from ella_bot.ui.pygame_gui.components.on_screen_keyboard import KeyboardAction
```

Add the helper and tests:

```python
def _tap_keyboard_key(scene, key_id):
    scene.render()
    point = scene.keyboard.key_rects[key_id].center
    scene.handle_event(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=point)
    )
    scene.handle_event(
        pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=point)
    )


def test_create_modal_accepts_touchscreen_keyboard_input():
    scene = _scene()
    scene._open_create()

    _tap_keyboard_key(scene, "shift")
    _tap_keyboard_key(scene, "l")
    _tap_keyboard_key(scene, "e")
    _tap_keyboard_key(scene, "o")

    assert scene.name_input == "Leo"


def test_rename_modal_accepts_space_and_backspace_from_touchscreen():
    scene = _scene()
    profile = _profile(1, "Ana")
    scene._open_rename(profile)

    _tap_keyboard_key(scene, "space")
    _tap_keyboard_key(scene, "m")
    _tap_keyboard_key(scene, "backspace")

    assert scene.name_input == "Ana "


def test_touchscreen_input_respects_twenty_character_limit():
    scene = _scene()
    scene._open_create()
    scene.name_input = "a" * 20

    _tap_keyboard_key(scene, "b")

    assert scene.name_input == "a" * 20


def test_keyboard_action_clears_stale_validation_error():
    scene = _scene()
    scene._open_create()
    scene.error_message = "Name is taken"

    scene._apply_keyboard_action(KeyboardAction("text", "a"))

    assert scene.name_input == "a"
    assert scene.error_message == ""
```

- [ ] **Step 2: Run the new integration tests and verify they fail**

Run:

```bash
.venv/bin/pytest tests/test_profiles_scene.py -q
```

Expected: failures because `ProfilesScene` has no `keyboard` or `_apply_keyboard_action`.

- [ ] **Step 3: Initialize and reset the keyboard with modal lifecycle**

In `src/ella_bot/ui/pygame_gui/scenes/profiles.py`, import:

```python
from ella_bot.ui.pygame_gui.components.on_screen_keyboard import (
    KeyboardAction,
    OnScreenKeyboard,
)
```

Initialize after the existing modal button fields in `__init__`:

```python
self.keyboard = OnScreenKeyboard(self.app.font_small)
```

In both `_open_create()` and `_open_rename()`, reset before starting text input:

```python
self.keyboard.reset()
pygame.key.start_text_input()
```

In `_close_modal()` and `on_exit()`, cancel keyboard press state:

```python
self.keyboard.cancel_press()
```

Do not reset `uppercase` during rendering; it changes only when the modal opens,
Shift is tapped, or an alphabetic key is tapped while Shift is active.

- [ ] **Step 4: Route modal pointer events through the keyboard**

Add this method beside the existing input helpers:

```python
def _apply_keyboard_action(self, action: KeyboardAction | None) -> None:
    if action is None or action.kind == "shift":
        return
    if action.kind == "backspace":
        self.name_input = self.name_input[:-1]
        self.error_message = ""
        return
    candidate = self.name_input + action.text
    if len(candidate) <= 20:
        self.name_input = candidate
        self.error_message = ""
```

In the `self.modal is not None` branch of `_handle_mouse_down()`, keep modal button checks first. If neither button was pressed and the modal is Create or Rename, call:

```python
elif self.modal in ("create", "rename"):
    self.keyboard.handle_mouse_down(mouse_pos)
```

In the modal branch of `_handle_mouse_up()`, retain all existing Save/Confirm/Cancel behavior. If no modal button action matched and the modal is Create or Rename, apply the keyboard result:

```python
elif self.modal in ("create", "rename"):
    self._apply_keyboard_action(self.keyboard.handle_mouse_up(mouse_pos))
```

Before returning after a modal-button action, call `self.keyboard.cancel_press()` so a release cannot leave a stale key pressed. A mouse-down on Save or Cancel must likewise cancel any prior keyboard press.

- [ ] **Step 5: Expand and render the name modal around the keyboard**

In `_draw_name_modal()`, replace the current 600x340 dialog with:

```python
dialog = pygame.Rect(
    0,
    0,
    min(1120, width - 80),
    min(640, height - 40),
)
dialog.center = (width // 2, height // 2)
```

Keep the title and prompt near the top, and size the input field relative to the wider dialog:

```python
input_rect = pygame.Rect(
    dialog.left + 80,
    dialog.top + 100,
    dialog.width - 160,
    48,
)
```

Place action buttons first so they establish the keyboard's lower boundary:

```python
button_width, button_height, gap = 180, 52, 20
button_y = dialog.bottom - button_height - 20
```

After drawing the input and any error, create and draw the keyboard between the input and buttons:

```python
keyboard_top = input_rect.bottom + 34
keyboard_bottom = button_y - 18
keyboard_rect = pygame.Rect(
    dialog.left + 35,
    keyboard_top,
    dialog.width - 70,
    max(1, keyboard_bottom - keyboard_top),
)
self.keyboard.draw(screen, keyboard_rect)
```

Render validation errors at `input_rect.bottom + 5`, above `keyboard_top`. Preserve existing button labels, variants, and save/cancel assignments. The keyboard must be drawn before the buttons so buttons remain visually dominant if edges ever meet.

- [ ] **Step 6: Add failing lifecycle and compatibility tests**

Append to `tests/test_profiles_scene.py`:

```python
def test_opening_name_modal_resets_keyboard_case():
    scene = _scene()
    scene._open_create()
    scene.keyboard.uppercase = True

    scene._close_modal()
    scene._open_create()

    assert scene.keyboard.uppercase is False


def test_closing_modal_cancels_pressed_keyboard_key():
    scene = _scene()
    scene._open_create()
    scene.render()
    point = scene.keyboard.key_rects["q"].center
    scene.keyboard.handle_mouse_down(point)

    scene._close_modal()

    assert scene.keyboard.handle_mouse_up(point) is None


def test_leaving_scene_cancels_pressed_keyboard_key(monkeypatch):
    scene = _scene()
    scene._open_create()
    scene.render()
    point = scene.keyboard.key_rects["q"].center
    scene.keyboard.handle_mouse_down(point)
    monkeypatch.setattr(pygame.key, "stop_text_input", lambda: None)

    scene.on_exit()

    assert scene.keyboard.handle_mouse_up(point) is None


def test_name_modal_keyboard_and_actions_fit_inside_screen():
    scene = _scene()
    scene._open_create()

    scene.render()

    screen_rect = scene.app.screen.get_rect()
    assert all(screen_rect.contains(rect) for rect in scene.keyboard.key_rects.values())
    assert screen_rect.contains(scene._modal_save_button)
    assert screen_rect.contains(scene._modal_cancel_button)


def test_physical_text_input_still_works_with_embedded_keyboard():
    scene = _scene()
    scene._open_create()

    scene.handle_event(pygame.event.Event(pygame.TEXTINPUT, text="Mia"))

    assert scene.name_input == "Mia"
```

- [ ] **Step 7: Run profile scene and component tests**

Run:

```bash
.venv/bin/pytest tests/test_on_screen_keyboard.py tests/test_profiles_scene.py -q
```

Expected: all tests pass.

- [ ] **Step 8: Run formatting and diff checks**

Run:

```bash
git diff --check -- src/ella_bot/ui/pygame_gui/components/on_screen_keyboard.py src/ella_bot/ui/pygame_gui/scenes/profiles.py tests/test_on_screen_keyboard.py tests/test_profiles_scene.py
```

Expected: no output and exit code 0.

- [ ] **Step 9: Commit profile integration**

```bash
git add src/ella_bot/ui/pygame_gui/scenes/profiles.py tests/test_profiles_scene.py
git commit -m "feat: add touchscreen profile name entry"
```

---

### Task 3: Regression Verification

**Files:**
- Verify: `src/ella_bot/ui/pygame_gui/components/on_screen_keyboard.py`
- Verify: `src/ella_bot/ui/pygame_gui/scenes/profiles.py`
- Verify: `tests/test_on_screen_keyboard.py`
- Verify: `tests/test_profiles_scene.py`

**Interfaces:**
- Consumes: completed component and Profiles scene integration from Tasks 1 and 2.
- Produces: verified touchscreen and physical-keyboard profile entry with no application-test regressions.

- [ ] **Step 1: Run focused tests verbosely**

Run:

```bash
.venv/bin/pytest tests/test_on_screen_keyboard.py tests/test_profiles_scene.py -v
```

Expected: every component and profile-scene test passes.

- [ ] **Step 2: Run the application test suite**

Run:

```bash
.venv/bin/pytest tests -q
```

Expected: all tests pass. Use `tests/` explicitly because repository-wide discovery also collects unrelated executable scripts under `scratch/` and `seeed-voicecard/tools/`.

- [ ] **Step 3: Inspect the final scoped diff**

Run:

```bash
git diff HEAD~2 --check
git diff HEAD~2 --stat
```

Expected: no whitespace errors; changes are limited to the keyboard component, Profiles scene, and their tests. Do not include the user's unrelated working-tree changes.

- [ ] **Step 4: Perform the device touch smoke test**

Launch ELLA on the Raspberry Pi and verify:

1. Open Profiles and tap Create Profile.
2. Enter a mixed-case name containing a space, apostrophe, or hyphen.
3. Use Backspace, then tap Create.
4. Rename the profile using only touch and tap Save.
5. Confirm Cancel closes the modal without changing a name.
6. Confirm all keys and both action buttons remain fully visible at 1280x720.
7. If a physical keyboard is available temporarily, confirm it can still type into the same modal.

Expected: touch and physical entry both work; no Raspberry Pi system keyboard is required or launched.

- [ ] **Step 5: Commit any smoke-test-only correction if required**

If the smoke test required a layout correction, first add a regression assertion to `tests/test_profiles_scene.py`, verify it fails, apply only the layout correction, rerun Tasks 3 Steps 1-3, then commit:

```bash
git add src/ella_bot/ui/pygame_gui/scenes/profiles.py tests/test_profiles_scene.py
git commit -m "fix: keep touchscreen keyboard within profile modal"
```

If no correction was required, do not create an empty commit.
