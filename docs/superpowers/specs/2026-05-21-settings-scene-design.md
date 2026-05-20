# Settings Scene Design

## Overview

Add a SettingsScene accessible from the main menu that lets students and teachers adjust three non-technical options: volume level, listening duration, and progress reset. Settings take effect immediately and are persisted to `settings.ini` on every tap (live + auto-save).

Tutorial button is removed from MainMenuScene entirely.

---

## Architecture

**New file:** `src/ella_bot/ui/pygame_gui/scenes/settings.py` — `SettingsScene(BaseScene)`

**Modified files:**
- `src/ella_bot/ui/pygame_gui/scenes/main_menu.py` — remove Tutorial button, wire Settings → `switch_scene("settings")`
- `src/ella_bot/ui/pygame_gui/app.py` — register `SettingsScene` in `self.scenes`
- `src/ella_bot/speech/tts/base.py` — add `volume: float = 1.0` to `TTSConfig`
- `src/ella_bot/speech/tts/engines/piper.py` — add `set_volume(fraction: float)` method
- `src/ella_bot/services/session_manager.py` — add `reset_to_start()` method
- `src/ella_bot/config/app_config.py` — load `volume` from `[TTS]` section
- `config/settings.ini` — add `volume = 6` to `[TTS]` section

---

## Controls

### 1. Volume — 6-step segmented bar

- **Label:** "Volume"
- **Range:** 1–6 (integer steps, stored as integer in `settings.ini`)
- **Display:** horizontal row of 6 segments; filled segments use `(248, 111, 150)`, empty segments use `(210, 170, 185)` outline-only
- **Interaction:** `[-]` taps down 1 step (min 1), `[+]` taps up 1 step (max 6)
- **Live effect:** on each tap, compute `fraction = level / 6.0`, call `app.tts.set_volume(fraction)`
- **Persistence:** write `volume = <level>` to `[TTS]` in `settings.ini` on each tap

**Volume fraction map:**

| Level | Fraction |
|-------|----------|
| 1 | 0.167 |
| 2 | 0.333 |
| 3 | 0.500 |
| 4 | 0.667 |
| 5 | 0.833 |
| 6 | 1.000 |

`PiperTTS.set_volume(fraction)` rebuilds `self._syn_config` with the new volume value. Other TTS engines (EspeakTTS, MacSayTTS, etc.) receive a no-op `set_volume` from `BaseTTS`.

### 2. Listen Duration — +/− stepper

- **Label:** "Listen Time"
- **Range:** 5–10 seconds (integer steps)
- **Display:** centered value label, e.g. "7 sec"
- **Interaction:** `[-]` decrements (min 5), `[+]` increments (max 10)
- **Live effect:** on each tap, set `app.asr.listen_seconds = value`
- **Persistence:** write `listen_seconds = <value>` to `[Speech]` in `settings.ini` on each tap

### 3. Reset Progress — danger button + confirmation overlay

- **Display:** single button labelled "Reset Progress", danger styling (red fill `(220, 70, 90)`, white text)
- **On tap:** show a modal overlay (same pattern as the exit-confirm in MainMenuScene)
  - Message: "Reset all progress to Level 1?"
  - `[Yes]` — calls `app.session.reset_to_start()` and `app.switch_scene("main_menu")`
  - `[No]` — dismisses overlay, stays in SettingsScene
- No persistence needed (session state lives in memory; it was already at Level 1a on boot if settings.ini `start_level = 1a`)

`SessionManager.reset_to_start()` sets `current_level = "1a"`, clears all `level_indices` to 0, resets `completed_in_level = 0`, updates `expected_sentence`.

---

## Back Button

- Bottom-left corner of screen, labelled "← Back", same button style as main menu
- On tap: `app.switch_scene("main_menu")`

---

## Layout (1280 × 720)

```
┌───────────────────────────────────────────────────┐
│                    Settings                        │  ← font_title, centered, y=60
│                                                    │
│   Volume                                           │  ← label, y=200
│   [−]  [■][■][■][■][□][□]  [+]                    │  ← segments + buttons, y=245
│                                                    │
│   Listen Time                                      │  ← label, y=360
│   [−]        7 sec         [+]                     │  ← stepper, y=405
│                                                    │
│          [ Reset Progress ]                        │  ← danger button, y=510
│                                                    │
│  [← Back]                                          │  ← bottom-left, y=630
└───────────────────────────────────────────────────┘
```

**Color palette** (matches existing main menu):
- Background: `(245, 205, 214)` — same as `menu_bg_color`
- Button fill: `(248, 111, 150)` — same as `button_bg_color`
- Button text: `(255, 255, 255)`
- Button outline: `(0, 0, 0)`
- Pressed tint: `(251, 165, 193)`
- Segment filled: `(248, 111, 150)`
- Segment empty: `(210, 170, 185)`
- Danger button fill: `(220, 70, 90)`

**Fonts:** reuse `app.font_title` (42px), `app.font_button` (48px), `app.font_body` (30px)

**Button sizes:**
- `[-]` / `[+]` buttons: 70 × 70 px, border-radius 12
- Volume segments: 52 × 36 px each, 8px gap, border-radius 8
- Reset Progress button: 320 × 90 px, border-radius 15
- Back button: 180 × 70 px, border-radius 15

---

## Persistence Helper

Add `save_setting(section: str, key: str, value: str) -> None` to `app_config.py`. Reads `settings.ini`, updates the key in-place using `configparser`, and writes back. Called by SettingsScene on every tap — synchronous, fast on Pi 5 for a tiny file.

---

## Settings.ini Changes

Add `volume = 6` to the `[TTS]` section (default full volume). `app_config.py` loads it as an int.

---

## MainMenuScene Changes

- Remove `self.menu_tutorial_button` and all Tutorial rendering/event-handling code
- Reflow remaining buttons: Start, Settings, Exit — vertically centered in the same area
- Wire Settings button to `app.switch_scene("settings")`

---

## Error Handling

- `set_volume` is a no-op on non-Piper engines (base class default returns `None`)
- `save_setting` silently skips if `settings.ini` doesn't exist (defensive)
- `app.asr` may be `None` if `use_mic = False`; guard with `if app.asr is not None`

---

## Testing

- `tests/test_settings_scene.py` — unit tests using `object.__new__(SettingsScene)` to bypass pygame:
  - Volume clamping (tap below 1 stays at 1, tap above 6 stays at 6)
  - Listen duration clamping (below 5 stays at 5, above 10 stays at 10)
  - `reset_to_start()` on SessionManager returns state to level 1a
- `tests/test_config.py` — `save_setting` round-trip test (write + read back)
- No pygame display required for any test (all use mock or `object.__new__`)
