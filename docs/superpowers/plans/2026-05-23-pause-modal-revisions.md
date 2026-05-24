# Pause Modal Revisions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply four visual revisions to PauseModal: SVG close icon with button borders, smaller "Options" title, pink footer section housing action buttons, and responsive modal height during confirmation.

**Architecture:** All changes are confined to `pause_modal.py`. The modal computes its height dynamically at render time based on `show_confirm`, adds a pink footer band (mirror of the header) for action buttons, and loads `ic_close.svg` the same way as the ± icons.

**Tech Stack:** pygame-ce, Python 3.14, `io.BytesIO` for SVG loading

---

### Task 1: Close button — use ic_close.svg with button border style

**Files:**
- Modify: `src/ella_bot/ui/pygame_gui/components/pause_modal.py`

Currently the close button draws raw diagonal lines for the ×. Replace with:
- Load `ic_close.svg` at 28px via `_load_assets`
- Draw the close button using the shadow-rect button style (`_DANGER` fill, `_BTN_OUTLINE` 2px stroke, shadow-rect shifted 4px right/down in `_BTN_OUTLINE`)

- [ ] **Step 1: Add `_icon_close` attribute to `__init__`**

In `__init__`, after the existing `self._icon_remove = None` line, add:
```python
self._icon_close = None
```

- [ ] **Step 2: Add ic_close.svg to `_load_assets`**

In `_load_assets`, extend the loop list to include:
```python
for attr, filename, size in [
    ("_icon_add", "assets/ic_add.svg", 32),
    ("_icon_remove", "assets/ic_remove.svg", 32),
    ("_icon_close", "assets/ic_close.svg", 28),
]:
```

- [ ] **Step 3: Rewrite the close button draw in `render`**

Replace the current close button block (the `pygame.draw.rect(_DANGER...)` and two `pygame.draw.line` calls) with:

```python
close_w, close_h = 44, 44
close_rect = pygame.Rect(modal_rect.right - 16 - close_w, modal_rect.top + 14, close_w, close_h)
self.close_rect = close_rect
# Shadow-rect style with danger fill
pygame.draw.rect(screen, _BTN_OUTLINE,
                 pygame.Rect(close_rect.left + 4, close_rect.top + 4, close_w, close_h),
                 border_radius=12)
pygame.draw.rect(screen, _DANGER, close_rect, border_radius=12)
pygame.draw.rect(screen, _BTN_OUTLINE, close_rect, width=2, border_radius=12)
if self._icon_close:
    screen.blit(self._icon_close, self._icon_close.get_rect(center=close_rect.center))
```

- [ ] **Step 4: Run tests**

```bash
source .venv/bin/activate && python -m pytest --ignore=tests/test_tts_piper.py -q
```
Expected: 51 passed

- [ ] **Step 5: Commit**

```bash
git add src/ella_bot/ui/pygame_gui/components/pause_modal.py
git commit -m "fix: use ic_close.svg with button border style for modal close button"
```

---

### Task 2: Scale down "Options" title

**Files:**
- Modify: `src/ella_bot/ui/pygame_gui/components/pause_modal.py`

`font_title` is 64px (set by the user). The modal header is only 72px tall so "Options" at 64px is too large. Create a dedicated 36px font lazily inside `_load_assets` so the size is contained to the modal and doesn't affect any other scene.

- [ ] **Step 1: Add `_modal_title_font` attribute to `__init__`**

After `self._icon_close = None`, add:
```python
self._modal_title_font = None
```

- [ ] **Step 2: Lazily create the font in `_load_assets`**

After the SVG loading loop in `_load_assets`, add:
```python
if self._modal_title_font is None:
    try:
        self._modal_title_font = pygame.font.SysFont(
            ["Changa One", "Avenir Next", "Segoe UI", "Arial", "Verdana", "sans-serif"],
            36
        )
    except Exception:
        self._modal_title_font = self.app.font_body
```

- [ ] **Step 3: Use `_modal_title_font` for the "Options" title in `render`**

Replace:
```python
title_surf = self.app.font_title.render("Options", True, _WHITE)
```
With:
```python
title_surf = self._modal_title_font.render("Options", True, _WHITE)
```

- [ ] **Step 4: Run tests**

```bash
source .venv/bin/activate && python -m pytest --ignore=tests/test_tts_piper.py -q
```
Expected: 51 passed

- [ ] **Step 5: Commit**

```bash
git add src/ella_bot/ui/pygame_gui/components/pause_modal.py
git commit -m "fix: use 36px modal title font for Options header, independent of font_title"
```

---

### Task 3: Pink footer section housing action buttons

**Files:**
- Modify: `src/ella_bot/ui/pygame_gui/components/pause_modal.py`

The reference image shows action buttons ("Restart Level", "Back to Menu") sitting inside a pink band at the bottom of the modal — mirroring the pink header at the top. Restructure the modal into three zones: header (pink, top-rounded), body (white, flat), footer (pink, bottom-rounded).

New constants:
```python
_BODY_H = 310     # white middle zone height
_FOOTER_H = 54   # pink bottom zone height
# _MODAL_H = _HEADER_H + _BODY_H + _FOOTER_H = 72 + 310 + 160 = 542
```

Update `_MODAL_H = 542` (or keep and recalculate — see step below).

- [ ] **Step 1: Update module-level sizing constants**

Replace:
```python
_MODAL_W = 520
_MODAL_H = 560
_HEADER_H = 72
```
With:
```python
_MODAL_W = 520
_HEADER_H = 72
_BODY_H = 310
_FOOTER_H = 160
_MODAL_H = _HEADER_H + _BODY_H + _FOOTER_H   # 542
```

- [ ] **Step 2: Draw the footer band in `render`**

In `render`, after drawing the header, add footer geometry variables and draw the pink footer zone. Insert this block right after the header draw calls and before `# --- Header content ---`:

```python
footer_rect = pygame.Rect(
    modal_rect.left, modal_rect.bottom - _FOOTER_H,
    modal_rect.width, _FOOTER_H
)
body_rect = pygame.Rect(
    modal_rect.left, modal_rect.top + _HEADER_H,
    modal_rect.width, _BODY_H
)
# Draw modal base (white, fully rounded)
pygame.draw.rect(screen, _WHITE, modal_rect, border_radius=24)
# Header (pink, top corners only)
pygame.draw.rect(screen, _BTN_FILL, header_rect,
                 border_top_left_radius=24, border_top_right_radius=24,
                 border_bottom_left_radius=0, border_bottom_right_radius=0)
# Footer (pink, bottom corners only)
pygame.draw.rect(screen, _BTN_FILL, footer_rect,
                 border_top_left_radius=0, border_top_right_radius=0,
                 border_bottom_left_radius=24, border_bottom_right_radius=24)
# Outer border on top
pygame.draw.rect(screen, _BTN_OUTLINE, modal_rect, width=4, border_radius=24)
```

Note: Remove the old draw calls for modal base / header from `render` that are now replaced above.

- [ ] **Step 3: Move action buttons into `_draw_body`'s footer zone**

`_draw_body` currently places buttons relative to the divider position. Change it so buttons are positioned relative to `footer_rect` (passed as a new parameter). Update the `_draw_body` signature and call site.

New `_draw_body` signature:
```python
def _draw_body(self, screen, modal_rect, body_rect, footer_rect) -> None:
```

In `_draw_body`, replace the divider + action buttons block:

```python
# --- Divider (at bottom of body) ---
div_y = body_rect.bottom - 1
div_margin = int(modal_rect.width * 0.10)
pygame.draw.line(screen, _SEG_INACTIVE_BORDER,
                 (modal_rect.left + div_margin, div_y),
                 (modal_rect.right - div_margin, div_y), width=1)

# --- Action buttons (inside footer) ---
btn_w = int(modal_rect.width * 0.82)
btn_h = 56
stack_gap = 12
btn_x = modal_rect.centerx - btn_w // 2
btn_y = footer_rect.top + (footer_rect.height - 2 * btn_h - stack_gap) // 2

self.restart_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
self._draw_button(screen, self.restart_rect, "Restart Level", "restart", radius=18)

self.main_menu_rect = pygame.Rect(btn_x, btn_y + btn_h + stack_gap, btn_w, btn_h)
self._draw_button(screen, self.main_menu_rect, "Back to Menu", "main_menu", radius=18)
```

Remove the old `div_y` and button placement code that was relative to the divider.

- [ ] **Step 4: Update the `_draw_body` call in `render`**

Change:
```python
self._draw_body(screen, modal_rect, body_rect)
```
To:
```python
self._draw_body(screen, modal_rect, body_rect, footer_rect)
```

- [ ] **Step 5: Update `_draw_confirm` to not pass footer_rect (it doesn't use one)**

`_draw_confirm` signature and call remain `_draw_confirm(screen, modal_rect, body_rect)` — confirm mode has no footer (see Task 4).

- [ ] **Step 6: Run tests**

```bash
source .venv/bin/activate && python -m pytest --ignore=tests/test_tts_piper.py -q
```
Expected: 51 passed

- [ ] **Step 7: Commit**

```bash
git add src/ella_bot/ui/pygame_gui/components/pause_modal.py
git commit -m "feat: add pink footer section to pause modal, move action buttons into footer"
```

---

### Task 4: Responsive modal height during confirmation

**Files:**
- Modify: `src/ella_bot/ui/pygame_gui/components/pause_modal.py`

Confirmation mode shows only a message + Yes/No buttons. The full 542px modal with its empty body looks wrong — shrink it to fit the content.

Confirm mode height: header (72) + confirm body (140) = 212px.

New constant: `_MODAL_H_CONFIRM = 212`

- [ ] **Step 1: Add `_MODAL_H_CONFIRM` constant**

After `_MODAL_H = _HEADER_H + _BODY_H + _FOOTER_H`, add:
```python
_MODAL_H_CONFIRM = _HEADER_H + 140   # 212 — header + message + yes/no buttons
```

- [ ] **Step 2: Compute `modal_h` dynamically in `render`**

In `render`, replace the fixed:
```python
modal_x = prompt_rect.centerx - _MODAL_W // 2
modal_y = prompt_rect.centery - _MODAL_H // 2
modal_rect = pygame.Rect(modal_x, modal_y, _MODAL_W, _MODAL_H)
```
With:
```python
modal_h = _MODAL_H_CONFIRM if self.show_confirm else _MODAL_H
modal_x = prompt_rect.centerx - _MODAL_W // 2
modal_y = prompt_rect.centery - modal_h // 2
modal_rect = pygame.Rect(modal_x, modal_y, _MODAL_W, modal_h)
```

- [ ] **Step 3: Gate footer drawing on normal mode**

In `render`, the `footer_rect` and footer draw calls should only run in normal mode. Wrap them:

```python
if not self.show_confirm:
    footer_rect = pygame.Rect(
        modal_rect.left, modal_rect.bottom - _FOOTER_H,
        modal_rect.width, _FOOTER_H
    )
    body_rect = pygame.Rect(
        modal_rect.left, modal_rect.top + _HEADER_H,
        modal_rect.width, _BODY_H
    )
else:
    footer_rect = None
    body_rect = pygame.Rect(
        modal_rect.left, modal_rect.top + _HEADER_H,
        modal_rect.width, modal_h - _HEADER_H
    )
```

Then draw the footer band only when `footer_rect is not None`:
```python
if footer_rect is not None:
    pygame.draw.rect(screen, _BTN_FILL, footer_rect,
                     border_top_left_radius=0, border_top_right_radius=0,
                     border_bottom_left_radius=24, border_bottom_right_radius=24)
```

- [ ] **Step 4: Update the body/confirm dispatch**

```python
if not self.show_confirm:
    self._draw_body(screen, modal_rect, body_rect, footer_rect)
else:
    self._draw_confirm(screen, modal_rect, body_rect)
```

- [ ] **Step 5: Run tests**

```bash
source .venv/bin/activate && python -m pytest --ignore=tests/test_tts_piper.py -q
```
Expected: 51 passed

- [ ] **Step 6: Commit**

```bash
git add src/ella_bot/ui/pygame_gui/components/pause_modal.py
git commit -m "feat: responsive modal height — shrink to fit during confirmation"
```
