# Settings Scene Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a SettingsScene to E.L.L.A. with volume, listen duration, and reset progress controls. Remove the Tutorial button from the main menu.

**Architecture:** Foundation layer (TTSConfig.volume, PiperTTS.set_volume, SessionManager.reset_to_start, save_setting helper) first, then new SettingsScene, then wire everything into app.py and MainMenuScene. All settings take effect immediately and persist to settings.ini on each tap.

**Tech Stack:** Python, pygame-ce, configparser, pytest.

**Spec:** `docs/superpowers/specs/2026-05-21-settings-scene-design.md`

---

## File Structure

| File | Change |
|---|---|
| `src/ella_bot/speech/tts/base.py` | Add `volume: float = 1.0` to `TTSConfig`; add `set_volume` no-op to `BaseTTS` |
| `src/ella_bot/speech/tts/engines/piper.py` | Pass `volume` to `SynthesisConfig` in `__init__`; add `set_volume(fraction)` |
| `src/ella_bot/services/session_manager.py` | Add `reset_to_start()` method |
| `src/ella_bot/config/app_config.py` | Add `save_setting(section, key, value)` function; load `volume` from `[TTS]` |
| `config/settings.ini` | Add `volume = 6` under `[TTS]` |
| `src/ella_bot/ui/pygame_gui/scenes/settings.py` | New file — `SettingsScene` |
| `src/ella_bot/ui/pygame_gui/scenes/main_menu.py` | Remove Tutorial button; wire Settings → switch_scene |
| `src/ella_bot/ui/pygame_gui/app.py` | Import and register `SettingsScene` |
| `tests/test_settings_scene.py` | New file — unit tests for clamping and helpers |
| `tests/test_tts_piper.py` | Add `set_volume` tests |
| `tests/test_config.py` | Add `save_setting` round-trip test |

---

### Task 1: Foundation layer — volume, reset_to_start, save_setting

**Files:**
- Modify: `src/ella_bot/speech/tts/base.py`
- Modify: `src/ella_bot/speech/tts/engines/piper.py`
- Modify: `src/ella_bot/services/session_manager.py`
- Modify: `src/ella_bot/config/app_config.py`
- Modify: `config/settings.ini`
- Test: `tests/test_tts_piper.py`, `tests/test_config.py`

**Background:** `PiperTTS` constructs `SynthesisConfig` without a `volume` parameter. `SessionManager` has no full-reset method (only `reset_current_level`). `save_setting` does not exist yet. These are all pure-Python changes with no pygame dependency.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_tts_piper.py`:

```python
def test_set_volume_rebuilds_syn_config():
    from unittest.mock import MagicMock, patch
    from ella_bot.speech.tts.engines.piper import PiperTTS
    from ella_bot.speech.tts.base import TTSConfig

    config = TTSConfig(length_scale=1.0, noise_scale=0.667, noise_w=0.8)
    with patch("ella_bot.speech.tts.engines.piper.PiperVoice.load", return_value=MagicMock()):
        tts = PiperTTS(config=config, piper_model="fake.onnx")

    tts.set_volume(0.5)
    assert tts._syn_config.volume == 0.5


def test_base_tts_set_volume_is_noop():
    from ella_bot.speech.tts.base import BaseTTS
    tts = BaseTTS()
    result = tts.set_volume(0.5)
    assert result is None
```

Append to `tests/test_config.py`:

```python
def test_save_setting_round_trip(tmp_path, monkeypatch):
    import configparser
    ini_dir = tmp_path / "config"
    ini_dir.mkdir()
    ini = ini_dir / "settings.ini"
    parser = configparser.ConfigParser()
    parser.add_section("Speech")
    parser.set("Speech", "listen_seconds", "5")
    with open(ini, "w") as f:
        parser.write(f)

    monkeypatch.setattr("ella_bot.config.app_config.get_project_root", lambda: tmp_path)

    from ella_bot.config.app_config import save_setting, load_settings
    save_setting("Speech", "listen_seconds", "9")
    settings = load_settings()
    assert settings.get("listen_seconds") == 9
```

Check if `tests/test_session_manager.py` exists, and if so append; otherwise create it:

```python
def test_reset_to_start_returns_to_level_1a():
    from ella_bot.services.session_manager import SessionManager

    sm = SessionManager(
        level_pools={"1a": ["cat", "dog"], "1b": ["fish"]},
        start_level="1a",
    )
    sm.current_level = "1b"
    sm.level_indices["1b"] = 0
    sm.completed_in_level = 3

    sm.reset_to_start()

    assert sm.current_level == "1a"
    assert sm.completed_in_level == 0
    assert sm.level_indices["1a"] == 0
    assert sm.expected_sentence in ("cat", "dog")
```

- [ ] **Step 2: Run the failing tests**

```
.venv/bin/python -m pytest tests/test_tts_piper.py::test_set_volume_rebuilds_syn_config tests/test_tts_piper.py::test_base_tts_set_volume_is_noop tests/test_config.py::test_save_setting_round_trip -v
```

Expected: FAIL — `set_volume` does not exist, `save_setting` does not exist.

- [ ] **Step 3: Add `volume` field to TTSConfig and `set_volume` no-op to BaseTTS**

In `src/ella_bot/speech/tts/base.py`, update `TTSConfig` dataclass by adding after `length_scale`:

```python
    volume: float = 1.0
```

And add to `BaseTTS` class after the `stop` method:

```python
    def set_volume(self, fraction: float) -> None:
        return None
```

The complete `BaseTTS` class should look like:

```python
class BaseTTS:
    def speak(self, text: str) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        """Stop any active playback if supported."""
        return None

    def set_volume(self, fraction: float) -> None:
        return None
```

- [ ] **Step 4: Update PiperTTS to use volume**

In `src/ella_bot/speech/tts/engines/piper.py`, update `__init__` to pass `volume` to `SynthesisConfig`:

```python
        self._syn_config = SynthesisConfig(
            length_scale=self.config.length_scale,
            noise_scale=self.config.noise_scale,
            noise_w_scale=self.config.noise_w,
            volume=self.config.volume,
        )
```

Add the `set_volume` method to `PiperTTS` after the `stop` method:

```python
    def set_volume(self, fraction: float) -> None:
        self._syn_config = SynthesisConfig(
            length_scale=self.config.length_scale,
            noise_scale=self.config.noise_scale,
            noise_w_scale=self.config.noise_w,
            volume=fraction,
        )
```

- [ ] **Step 5: Add `reset_to_start` to SessionManager**

In `src/ella_bot/services/session_manager.py`, add after `reset_current_level`:

```python
    def reset_to_start(self) -> None:
        self.current_level = "1a"
        self.level_indices = {level: 0 for level in self.level_order}
        self.completed_in_level = 0
        self.level_goal = len(self.level_pools.get("1a", []))
        self.expected_sentence = self.pick_sentence_for_level("1a")
```

- [ ] **Step 6: Add `save_setting` to app_config.py and load `volume`**

In `src/ella_bot/config/app_config.py`, add after the imports (before `load_settings`):

```python
def save_setting(section: str, key: str, value: str) -> None:
    """Write a single key to settings.ini, preserving all other values."""
    config_path = get_project_root() / "config" / "settings.ini"
    if not config_path.exists():
        return
    parser = configparser.ConfigParser()
    parser.read(config_path, encoding="utf-8")
    if not parser.has_section(section):
        parser.add_section(section)
    parser.set(section, key, value)
    with open(config_path, "w", encoding="utf-8") as f:
        parser.write(f)
```

In the `if parser.has_section("TTS"):` block, add after the `length_scale` read:

```python
        if parser.has_option("TTS", "volume"):
            defaults["volume"] = parser.getint("TTS", "volume")
```

- [ ] **Step 7: Add `volume = 6` to settings.ini**

In `config/settings.ini`, add under `[TTS]` after `length_scale`:

```ini
volume = 6
```

- [ ] **Step 8: Run the tests — verify they pass**

```
.venv/bin/python -m pytest tests/test_tts_piper.py::test_set_volume_rebuilds_syn_config tests/test_tts_piper.py::test_base_tts_set_volume_is_noop tests/test_config.py::test_save_setting_round_trip -v
```

Expected: PASS.

Also run the session manager test:

```
.venv/bin/python -m pytest tests/ -k "reset_to_start" -v
```

Expected: PASS.

- [ ] **Step 9: Run full test suite**

```
.venv/bin/python -m pytest -v
```

Expected: all tests PASS.

- [ ] **Step 10: Commit**

```bash
git add src/ella_bot/speech/tts/base.py src/ella_bot/speech/tts/engines/piper.py \
        src/ella_bot/services/session_manager.py \
        src/ella_bot/config/app_config.py config/settings.ini \
        tests/test_tts_piper.py tests/test_config.py
git commit -m "feat: add volume control foundation, reset_to_start, and save_setting helper"
```

---

### Task 2: SettingsScene

**Files:**
- Create: `src/ella_bot/ui/pygame_gui/scenes/settings.py`
- Create: `tests/test_settings_scene.py`

**Background:** The scene follows the same `BaseScene` pattern as `MainMenuScene`. It owns three controls — volume (6-step segmented bar), listen duration (stepper 5–10 s), and reset progress (danger button + confirm overlay). All rects are `None` until `render()` assigns them. Tests bypass `__init__` using `object.__new__` to avoid pygame dependency.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_settings_scene.py`:

```python
from unittest.mock import MagicMock


def _make_scene():
    """Build a SettingsScene instance without touching pygame."""
    from ella_bot.ui.pygame_gui.scenes.settings import SettingsScene
    app = MagicMock()
    app.asr = MagicMock()
    app.asr.listen_seconds = 7
    app.tts = MagicMock()
    scene = object.__new__(SettingsScene)
    scene.app = app
    scene.volume_level = 3
    scene.listen_seconds = 7
    scene.pressed_button = None
    scene.show_reset_confirm = False
    return scene


def test_volume_tap_plus_increments():
    scene = _make_scene()
    scene._tap_volume(1)
    assert scene.volume_level == 4


def test_volume_tap_minus_decrements():
    scene = _make_scene()
    scene._tap_volume(-1)
    assert scene.volume_level == 2


def test_volume_clamps_at_min():
    scene = _make_scene()
    scene.volume_level = 1
    scene._tap_volume(-1)
    assert scene.volume_level == 1


def test_volume_clamps_at_max():
    scene = _make_scene()
    scene.volume_level = 6
    scene._tap_volume(1)
    assert scene.volume_level == 6


def test_volume_tap_calls_set_volume():
    scene = _make_scene()
    scene.volume_level = 3
    scene._tap_volume(1)
    scene.app.tts.set_volume.assert_called_once_with(4 / 6)


def test_listen_tap_plus_increments():
    scene = _make_scene()
    scene._tap_listen(1)
    assert scene.listen_seconds == 8


def test_listen_tap_minus_decrements():
    scene = _make_scene()
    scene._tap_listen(-1)
    assert scene.listen_seconds == 6


def test_listen_clamps_at_min():
    scene = _make_scene()
    scene.listen_seconds = 5
    scene._tap_listen(-1)
    assert scene.listen_seconds == 5


def test_listen_clamps_at_max():
    scene = _make_scene()
    scene.listen_seconds = 10
    scene._tap_listen(1)
    assert scene.listen_seconds == 10


def test_listen_tap_updates_asr():
    scene = _make_scene()
    scene.listen_seconds = 7
    scene._tap_listen(1)
    assert scene.app.asr.listen_seconds == 8
```

- [ ] **Step 2: Run the failing tests**

```
.venv/bin/python -m pytest tests/test_settings_scene.py -v
```

Expected: FAIL — `SettingsScene` does not exist.

- [ ] **Step 3: Implement SettingsScene**

Create `src/ella_bot/ui/pygame_gui/scenes/settings.py`:

```python
from __future__ import annotations

import pygame
from ella_bot.ui.pygame_gui.scene import BaseScene
from ella_bot.config.app_config import save_setting
from ella_bot.ui.pygame_gui.ui_helpers import draw_menu_button

_VOLUME_MIN = 1
_VOLUME_MAX = 6
_LISTEN_MIN = 5
_LISTEN_MAX = 10


class SettingsScene(BaseScene):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.volume_level: int = 6
        self.listen_seconds: int = 5
        self.pressed_button: str | None = None
        self.show_reset_confirm: bool = False

        self.btn_vol_minus: pygame.Rect | None = None
        self.btn_vol_plus: pygame.Rect | None = None
        self.btn_listen_minus: pygame.Rect | None = None
        self.btn_listen_plus: pygame.Rect | None = None
        self.btn_reset: pygame.Rect | None = None
        self.btn_back: pygame.Rect | None = None
        self.btn_confirm_yes: pygame.Rect | None = None
        self.btn_confirm_no: pygame.Rect | None = None

        self.bg_color = (245, 205, 214)
        self.btn_color = (248, 111, 150)
        self.btn_text_color = (255, 255, 255)
        self.btn_outline_color = (0, 0, 0)
        self.btn_pressed_color = (251, 165, 193)
        self.seg_filled_color = (248, 111, 150)
        self.seg_empty_color = (210, 170, 185)
        self.danger_color = (220, 70, 90)
        self.danger_pressed_color = (200, 50, 70)

    def on_enter(self) -> None:
        self.show_reset_confirm = False
        self.pressed_button = None
        try:
            from ella_bot.config.app_config import load_settings
            settings = load_settings()
        except Exception:
            settings = {}
        self.volume_level = int(settings.get("volume", _VOLUME_MAX))
        if self.app.asr is not None:
            self.listen_seconds = self.app.asr.listen_seconds
        else:
            self.listen_seconds = int(settings.get("listen_seconds", _LISTEN_MIN))

    def handle_event(self, event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._on_mouse_down(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._on_mouse_up(event.pos)

    def _on_mouse_down(self, pos) -> None:
        if self.show_reset_confirm:
            if self.btn_confirm_yes and self.btn_confirm_yes.collidepoint(pos):
                self.pressed_button = "confirm_yes"
            elif self.btn_confirm_no and self.btn_confirm_no.collidepoint(pos):
                self.pressed_button = "confirm_no"
            return
        for name, rect in [
            ("vol_minus", self.btn_vol_minus),
            ("vol_plus", self.btn_vol_plus),
            ("listen_minus", self.btn_listen_minus),
            ("listen_plus", self.btn_listen_plus),
            ("reset", self.btn_reset),
            ("back", self.btn_back),
        ]:
            if rect and rect.collidepoint(pos):
                self.pressed_button = name
                break

    def _on_mouse_up(self, pos) -> None:
        try:
            if self.show_reset_confirm:
                if self.pressed_button == "confirm_yes" and self.btn_confirm_yes and self.btn_confirm_yes.collidepoint(pos):
                    self.app.session.reset_to_start()
                    self.app.switch_scene("main_menu")
                elif self.pressed_button == "confirm_no" and self.btn_confirm_no and self.btn_confirm_no.collidepoint(pos):
                    self.show_reset_confirm = False
                return
            btn = self.pressed_button
            if btn == "vol_minus" and self.btn_vol_minus and self.btn_vol_minus.collidepoint(pos):
                self._tap_volume(-1)
            elif btn == "vol_plus" and self.btn_vol_plus and self.btn_vol_plus.collidepoint(pos):
                self._tap_volume(1)
            elif btn == "listen_minus" and self.btn_listen_minus and self.btn_listen_minus.collidepoint(pos):
                self._tap_listen(-1)
            elif btn == "listen_plus" and self.btn_listen_plus and self.btn_listen_plus.collidepoint(pos):
                self._tap_listen(1)
            elif btn == "reset" and self.btn_reset and self.btn_reset.collidepoint(pos):
                self.show_reset_confirm = True
            elif btn == "back" and self.btn_back and self.btn_back.collidepoint(pos):
                self.app.switch_scene("main_menu")
        finally:
            self.pressed_button = None

    def _tap_volume(self, delta: int) -> None:
        self.volume_level = max(_VOLUME_MIN, min(_VOLUME_MAX, self.volume_level + delta))
        self.app.tts.set_volume(self.volume_level / _VOLUME_MAX)
        save_setting("TTS", "volume", str(self.volume_level))

    def _tap_listen(self, delta: int) -> None:
        self.listen_seconds = max(_LISTEN_MIN, min(_LISTEN_MAX, self.listen_seconds + delta))
        if self.app.asr is not None:
            self.app.asr.listen_seconds = self.listen_seconds
        save_setting("Speech", "listen_seconds", str(self.listen_seconds))

    def render(self) -> None:
        screen = self.app.screen
        w, h = screen.get_size()
        screen.fill(self.bg_color)

        title = self.app.font_title.render("Settings", True, (0, 0, 0))
        screen.blit(title, title.get_rect(center=(w // 2, int(h * 0.10))))

        cx = w // 2
        btn_sz = 70
        btn_r = 12

        # Volume row
        vol_label_y = int(h * 0.28)
        lbl = self.app.font_body.render("Volume", True, (0, 0, 0))
        screen.blit(lbl, lbl.get_rect(midleft=(cx - 260, vol_label_y)))

        seg_w, seg_h, seg_gap = 52, 36, 8
        total_seg_w = _VOLUME_MAX * seg_w + (_VOLUME_MAX - 1) * seg_gap
        seg_x0 = cx - total_seg_w // 2
        seg_y = vol_label_y + 40
        for i in range(_VOLUME_MAX):
            rx = seg_x0 + i * (seg_w + seg_gap)
            color = self.seg_filled_color if (i + 1) <= self.volume_level else self.seg_empty_color
            pygame.draw.rect(screen, color, (rx, seg_y, seg_w, seg_h), border_radius=8)
            if (i + 1) > self.volume_level:
                pygame.draw.rect(screen, self.btn_outline_color, (rx, seg_y, seg_w, seg_h), width=2, border_radius=8)

        self.btn_vol_minus = pygame.Rect(seg_x0 - btn_sz - 12, seg_y, btn_sz, btn_sz)
        self.btn_vol_plus = pygame.Rect(seg_x0 + total_seg_w + 12, seg_y, btn_sz, btn_sz)
        for rect, symbol, key in [
            (self.btn_vol_minus, "-", "vol_minus"),
            (self.btn_vol_plus, "+", "vol_plus"),
        ]:
            pressed = self.pressed_button == key
            bg = self.btn_pressed_color if pressed else self.btn_color
            pygame.draw.rect(screen, bg, rect, border_radius=btn_r)
            pygame.draw.rect(screen, self.btn_outline_color, rect, width=4, border_radius=btn_r)
            s = self.app.font_button.render(symbol, True, self.btn_text_color)
            screen.blit(s, s.get_rect(center=rect.center))

        # Listen Time row
        listen_label_y = int(h * 0.50)
        lbl2 = self.app.font_body.render("Listen Time", True, (0, 0, 0))
        screen.blit(lbl2, lbl2.get_rect(midleft=(cx - 260, listen_label_y)))

        val = self.app.font_button.render(f"{self.listen_seconds} sec", True, (0, 0, 0))
        val_rect = val.get_rect(center=(cx, listen_label_y + 40 + btn_sz // 2))
        screen.blit(val, val_rect)

        self.btn_listen_minus = pygame.Rect(val_rect.left - btn_sz - 16, val_rect.top, btn_sz, btn_sz)
        self.btn_listen_plus = pygame.Rect(val_rect.right + 16, val_rect.top, btn_sz, btn_sz)
        for rect, symbol, key in [
            (self.btn_listen_minus, "-", "listen_minus"),
            (self.btn_listen_plus, "+", "listen_plus"),
        ]:
            pressed = self.pressed_button == key
            bg = self.btn_pressed_color if pressed else self.btn_color
            pygame.draw.rect(screen, bg, rect, border_radius=btn_r)
            pygame.draw.rect(screen, self.btn_outline_color, rect, width=4, border_radius=btn_r)
            s = self.app.font_button.render(symbol, True, self.btn_text_color)
            screen.blit(s, s.get_rect(center=rect.center))

        # Reset Progress button
        reset_w, reset_h = 320, 90
        self.btn_reset = pygame.Rect(cx - reset_w // 2, int(h * 0.70), reset_w, reset_h)
        reset_bg = self.danger_pressed_color if self.pressed_button == "reset" else self.danger_color
        pygame.draw.rect(screen, reset_bg, self.btn_reset, border_radius=15)
        pygame.draw.rect(screen, self.btn_outline_color, self.btn_reset, width=6, border_radius=15)
        rs = self.app.font_body.render("Reset Progress", True, (255, 255, 255))
        screen.blit(rs, rs.get_rect(center=self.btn_reset.center))

        # Back button
        back_w, back_h = 180, 70
        self.btn_back = pygame.Rect(24, h - back_h - 24, back_w, back_h)
        draw_menu_button(screen, pygame, self.btn_back, "Back",
                         self.pressed_button == "back",
                         self.btn_color, self.btn_text_color, self.btn_outline_color,
                         font=self.app.font_body)

        # Confirmation overlay
        if self.show_reset_confirm:
            overlay = pygame.Surface((w, h), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            screen.blit(overlay, (0, 0))

            dlg_w = int(w * 0.7)
            dlg_h = int(h * 0.32)
            dlg_x = (w - dlg_w) // 2
            dlg_y = (h - dlg_h) // 2
            dlg = pygame.Rect(dlg_x, dlg_y, dlg_w, dlg_h)
            pygame.draw.rect(screen, (255, 255, 255), dlg, border_radius=12)
            pygame.draw.rect(screen, (0, 0, 0), dlg, width=6, border_radius=12)

            msg = self.app.font_body.render("Reset all progress to Level 1?", True, (0, 0, 0))
            screen.blit(msg, msg.get_rect(center=(w // 2, dlg_y + int(dlg_h * 0.35))))

            bw, bh = 160, 70
            by = dlg_y + dlg_h - bh - 24
            self.btn_confirm_yes = pygame.Rect(w // 2 - bw - 12, by, bw, bh)
            self.btn_confirm_no = pygame.Rect(w // 2 + 12, by, bw, bh)
            for rect, text, key in [
                (self.btn_confirm_yes, "Yes", "confirm_yes"),
                (self.btn_confirm_no, "No", "confirm_no"),
            ]:
                pressed = self.pressed_button == key
                bg = self.btn_pressed_color if pressed else self.btn_color
                pygame.draw.rect(screen, bg, rect, border_radius=12)
                pygame.draw.rect(screen, self.btn_outline_color, rect, width=6, border_radius=12)
                ts = self.app.font_body.render(text, True, (255, 255, 255))
                screen.blit(ts, ts.get_rect(center=rect.center))
```

- [ ] **Step 4: Run the tests — verify they pass**

```
.venv/bin/python -m pytest tests/test_settings_scene.py -v
```

Expected: all 10 tests PASS.

- [ ] **Step 5: Run full test suite**

```
.venv/bin/python -m pytest -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/ella_bot/ui/pygame_gui/scenes/settings.py tests/test_settings_scene.py
git commit -m "feat: add SettingsScene with volume, listen time, and reset progress"
```

---

### Task 3: Wire SettingsScene into app — update MainMenuScene and app.py

**Files:**
- Modify: `src/ella_bot/ui/pygame_gui/scenes/main_menu.py`
- Modify: `src/ella_bot/ui/pygame_gui/app.py`

**Background:** `MainMenuScene` currently has four buttons: Start, Tutorial, Settings, Exit. Tutorial must be removed. The Settings button must call `app.switch_scene("settings")` instead of setting a placeholder message. `app.py` must import `SettingsScene` and register it under key `"settings"` in the `self.scenes` dict. No new tests needed — existing tests cover scene switching at the unit level.

- [ ] **Step 1: Remove Tutorial from MainMenuScene**

Replace the entire `MainMenuScene` class in `src/ella_bot/ui/pygame_gui/scenes/main_menu.py` with:

```python
import pygame
from ella_bot.ui.pygame_gui.scene import BaseScene
from ella_bot.ui.pygame_gui.ui_helpers import draw_menu_button

class MainMenuScene(BaseScene):
    def __init__(self, app):
        super().__init__(app)
        self.pressed_button = None
        self.show_exit_confirm = False

        self.menu_start_button = None
        self.menu_settings_button = None
        self.menu_exit_button = None
        self.menu_confirm_yes_button = None
        self.menu_confirm_no_button = None

        self.menu_bg_color = (245, 205, 214)
        self.button_bg_color = (248, 111, 150)
        self.button_text_color = (255, 255, 255)
        self.button_outline_color = (0, 0, 0)

    def on_enter(self) -> None:
        self.show_exit_confirm = False
        self.pressed_button = None

    def handle_event(self, event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_mouse_down(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._handle_mouse_up(event.pos)

    def _handle_mouse_down(self, mouse_pos) -> None:
        if self.show_exit_confirm:
            if self.menu_confirm_yes_button and self.menu_confirm_yes_button.collidepoint(mouse_pos):
                self.pressed_button = "confirm_yes"
                return
            if self.menu_confirm_no_button and self.menu_confirm_no_button.collidepoint(mouse_pos):
                self.pressed_button = "confirm_no"
                return

        if self.menu_start_button and self.menu_start_button.collidepoint(mouse_pos):
            self.pressed_button = "start"
        elif self.menu_settings_button and self.menu_settings_button.collidepoint(mouse_pos):
            self.pressed_button = "settings"
        elif self.menu_exit_button and self.menu_exit_button.collidepoint(mouse_pos):
            self.pressed_button = "exit"

    def _handle_mouse_up(self, mouse_pos) -> None:
        try:
            if self.pressed_button == "start" and self.menu_start_button and self.menu_start_button.collidepoint(mouse_pos):
                self.app.switch_scene("reading_prompt")
                self.app.active_scene._start_attempt()
            elif self.pressed_button == "settings" and self.menu_settings_button and self.menu_settings_button.collidepoint(mouse_pos):
                self.app.switch_scene("settings")
            elif self.pressed_button == "exit" and self.menu_exit_button and self.menu_exit_button.collidepoint(mouse_pos):
                self.show_exit_confirm = True
            elif self.pressed_button == "confirm_yes" and self.menu_confirm_yes_button and self.menu_confirm_yes_button.collidepoint(mouse_pos):
                self.app.running = False
            elif self.pressed_button == "confirm_no" and self.menu_confirm_no_button and self.menu_confirm_no_button.collidepoint(mouse_pos):
                self.show_exit_confirm = False
        finally:
            self.pressed_button = None

    def render(self) -> None:
        screen = self.app.screen
        width, height = screen.get_size()

        screen.fill(self.menu_bg_color)

        title_surf = self.app.font_title.render("Welcome to E.L.L.A.", True, (0, 0, 0))
        title_rect = title_surf.get_rect(center=(width // 2, int(height * 0.15)))
        screen.blit(title_surf, title_rect)

        button_width = 320
        button_height = 110
        button_y_start = int(height * 0.32)
        button_spacing = 140
        center_x = width // 2

        self.menu_start_button = pygame.Rect(center_x - button_width // 2, button_y_start, button_width, button_height)
        draw_menu_button(screen, pygame, self.menu_start_button, "Start", self.pressed_button == "start", self.button_bg_color, self.button_text_color, self.button_outline_color, font=self.app.font_button)

        self.menu_settings_button = pygame.Rect(center_x - button_width // 2, button_y_start + button_spacing, button_width, button_height)
        draw_menu_button(screen, pygame, self.menu_settings_button, "Settings", self.pressed_button == "settings", self.button_bg_color, self.button_text_color, self.button_outline_color, font=self.app.font_button)

        self.menu_exit_button = pygame.Rect(center_x - button_width // 2, button_y_start + button_spacing * 2, button_width, button_height)
        draw_menu_button(screen, pygame, self.menu_exit_button, "Exit", self.pressed_button == "exit", self.button_bg_color, self.button_text_color, self.button_outline_color, font=self.app.font_button)

        if self.show_exit_confirm:
            overlay = pygame.Surface((width, height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            screen.blit(overlay, (0, 0))

            dialog_w = int(width * 0.8)
            dialog_h = int(height * 0.32)
            dialog_x = (width - dialog_w) // 2
            dialog_y = (height - dialog_h) // 2
            dialog_rect = pygame.Rect(dialog_x, dialog_y, dialog_w, dialog_h)
            pygame.draw.rect(screen, (255, 255, 255), dialog_rect, border_radius=12)
            pygame.draw.rect(screen, (0, 0, 0), dialog_rect, width=6, border_radius=12)

            msg = "Are you sure you want to exit?"
            msg_surf = self.app.font_body.render(msg, True, (0, 0, 0))
            msg_rect = msg_surf.get_rect(center=(width // 2, dialog_y + int(dialog_h * 0.35)))
            screen.blit(msg_surf, msg_rect)

            btn_w = 160
            btn_h = 70
            btn_y = dialog_y + dialog_h - btn_h - 24
            yes_rect = pygame.Rect((width // 2) - btn_w - 12, btn_y, btn_w, btn_h)
            no_rect = pygame.Rect((width // 2) + 12, btn_y, btn_w, btn_h)
            self.menu_confirm_yes_button = yes_rect
            self.menu_confirm_no_button = no_rect

            yes_bg = (251, 165, 193) if self.pressed_button == "confirm_yes" else self.button_bg_color
            pygame.draw.rect(screen, yes_bg, yes_rect, border_radius=12)
            pygame.draw.rect(screen, self.button_outline_color, yes_rect, width=6, border_radius=12)
            yes_text = self.app.font_body.render("Yes", True, (255, 255, 255))
            screen.blit(yes_text, yes_text.get_rect(center=yes_rect.center))

            no_bg = (251, 165, 193) if self.pressed_button == "confirm_no" else self.button_bg_color
            pygame.draw.rect(screen, no_bg, no_rect, border_radius=12)
            pygame.draw.rect(screen, self.button_outline_color, no_rect, width=6, border_radius=12)
            no_text = self.app.font_body.render("No", True, (255, 255, 255))
            screen.blit(no_text, no_text.get_rect(center=no_rect.center))
```

- [ ] **Step 2: Register SettingsScene in app.py**

In `src/ella_bot/ui/pygame_gui/app.py`, add the import at the top with the other scene imports:

```python
from ella_bot.ui.pygame_gui.scenes.settings import SettingsScene
```

In the `run()` method, update the `self.scenes` dict to add `"settings"`:

```python
        self.scenes = {
            "intro": IntroScene(self),
            "main_menu": MainMenuScene(self),
            "reading_prompt": ReadingPromptScene(self),
            "settings": SettingsScene(self),
        }
```

- [ ] **Step 3: Run the full test suite**

```
.venv/bin/python -m pytest -v
```

Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add src/ella_bot/ui/pygame_gui/scenes/main_menu.py \
        src/ella_bot/ui/pygame_gui/app.py
git commit -m "feat: wire SettingsScene into app, remove Tutorial button from main menu"
```
