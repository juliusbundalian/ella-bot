# Pause Modal Redesign

**Date:** 2026-05-23  
**Branch:** enh/ui-and-flow-enhancements  
**Reference:** `Reading Prompt with Menu Modal.png`

## Overview

Redesign `PauseModal` (`src/ella_bot/ui/pygame_gui/components/pause_modal.py`) to match the Figma reference. The new modal is called "Options" and replaces the current Resume/Main Menu/Exit button layout with inline Volume and Listening Time controls (reused from SettingsScene) plus Restart Level and Back to Menu action buttons.

## Visual Design

### Modal Container
- Size: ~520×560px, centered on screen
- Pink header band at top (fill `_BTN_FILL = (255, 182, 193)`), white body below
- Outer border: `_BTN_OUTLINE = (94, 42, 59)`, width=4, `border_radius=24`
- Semi-transparent dark overlay behind: `(0, 0, 0, 160)`

### Header
- "Options" title: `app.font_title`, white `(255, 255, 255)`, left-aligned with padding
- × close button: top-right corner, `_DANGER = (255, 99, 122)` fill, white × drawn with two lines, `~44×44`, `border_radius=12`
- Clicking × resumes (closes modal, returns to reading)

### Body — Volume Section
Reuse layout from SettingsScene exactly:
- "Volume" label: `app.font_body`, dark `(50, 50, 50)`, centered
- 6 segments: 48×24px, `border_radius=6`, `seg_gap=8`
  - Active: fill `_SEG_ACTIVE_FILL=(255,185,210)`, border `_BTN_OUTLINE`, shadow-shift 2px
  - Inactive: fill white, border `_SEG_INACTIVE_BORDER=(56,56,56)`, shadow-shift 2px
- SVG ± buttons: 56×56px, `border_radius=14`, `_BTN_FILL`/`_BTN_OUTLINE`, `ic_add.svg`/`ic_remove.svg` at 32px
- Full row centered horizontally in modal body

### Body — Listening Time Section
Reuse layout from SettingsScene exactly:
- "Listening Time" label: `app.font_body`, dark, centered
- Value `"{n} seconds"`: `app.font_body`, `_TITLE_COLOR=(230,127,159)`, centered
- SVG ± buttons: same as volume (56×56px)
- Full row centered horizontally in modal body

### Divider
- Thin horizontal line, color `_SEG_INACTIVE_BORDER=(56,56,56)`, width=1
- Spans 80% of modal body width, centered
- ~16px below the listening time row

### Action Buttons
Two full-width buttons, stacked with ~12px gap:
- "Restart Level" and "Back to Menu"
- Width: ~82% of modal width, height: 64px, `border_radius=18`
- Style: shadow-rect technique (4px shift), `_BTN_FILL` fill, `_BTN_OUTLINE` 2px stroke, `app.font_body` white text
- Each triggers a confirmation step

### Confirmation Overlay
Shown when either action button is tapped. Replaces the body content:
- Confirmation message: `app.font_body`, dark text, centered
  - Restart: "Restart this level?"
  - Back to Menu: "Return to main menu?"
- Yes / No buttons: same shadow-rect style, stacked below message
- × close button still visible (dismisses confirmation, returns to options)

## Architecture

### PauseModal Changes

**`__init__(self, app)`**  
Receives `app` reference. Initialises:
- `self.app = app`
- `self.volume_level: int` — loaded from settings on `open()`
- `self.listen_seconds: int` — loaded from `app.asr` or settings on `open()`
- `self._icon_add = None`, `self._icon_remove = None` — lazy-loaded SVGs
- All existing `*_rect` attributes preserved

**`open(self)`**  
Sync `volume_level` and `listen_seconds` from current app state before showing.

**`_load_assets(self)`**  
Load `ic_add.svg` and `ic_remove.svg` via BytesIO at 32px — identical pattern to SettingsScene.

**`_tap_volume(self, delta)`** / **`_tap_listen(self, delta)`**  
Same logic as SettingsScene: clamp, update `app.tts.set_volume()` / `app.asr.listen_seconds`, call `save_setting()`.

**`_draw_button(self, screen, rect, label, key, radius=18)`**  
Shadow-rect button helper, identical pattern to SettingsScene `_draw_button` (without icon support — action buttons are text-only).

**`render(self, screen, prompt_rect)`**  
Simplified signature — no longer receives `font_body`/`font_small` (uses `self.app`). Draws full modal.

**`hit_test(self, pos)`**  
New action added: `"ask_restart"`. Full action list:
- `"resume"` — × button
- `"ask_restart"` — Restart Level button (new)
- `"ask_main_menu"` — Back to Menu button
- `"confirm_yes"` / `"confirm_no"` — confirmation Yes/No
- `"consumed"` — click inside modal, no button hit

### ReadingPromptScene Changes

**`handle_event`** — add handling for `"ask_restart"`:
```python
if action == "ask_restart":
    self.modal.show_confirm = True
    self.modal.confirm_action = "restart"
    return
```

**`confirm_yes` handler** — add restart branch:
```python
if self.modal.confirm_action == "restart":
    self.modal.close()
    self._start_attempt()
```

**`render`** — update `modal.render()` call: remove `font_body, font_small` args.

**`PauseModal` instantiation** in `ReadingPromptScene.__init__`  
Change `self.modal = PauseModal()` → `self.modal = PauseModal(self.app)`.  
Note: `app` is available at `__init__` time since `ReadingPromptScene.__init__` receives `app`.

## Color Constants

Define at module level in `pause_modal.py` (same values as settings/main_menu):

```python
_WHITE = (255, 255, 255)
_BTN_FILL = (255, 182, 193)
_BTN_OUTLINE = (94, 42, 59)
_BTN_PRESSED = (251, 165, 193)
_DANGER = (255, 99, 122)
_TITLE_COLOR = (230, 127, 159)
_SEG_ACTIVE_FILL = (255, 185, 210)
_SEG_INACTIVE_BORDER = (56, 56, 56)
```

## Files Changed

| File | Change |
|------|--------|
| `src/ella_bot/ui/pygame_gui/components/pause_modal.py` | Full redesign |
| `src/ella_bot/ui/pygame_gui/scenes/reading_prompt.py` | Pass `app` to PauseModal, handle `ask_restart` and `confirm restart` |

## Out of Scope

- No changes to SettingsScene
- No changes to MainMenuScene
- No Exit button in new modal (removed per design)
- No audio/haptic feedback
