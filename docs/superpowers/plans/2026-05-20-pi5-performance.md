# Pi 5 Performance Optimizations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce two known Raspberry Pi 5 CPU bottlenecks: VoskASR running at the device default rate (48 kHz) instead of the 16 kHz rate the model was trained on, and BotSprite calling `pygame.transform.smoothscale` on every render frame at 60 FPS.

**Architecture:** Vosk fix is pure config plumbing — add `sample_rate = 16000` to `settings.ini` and load it in `app_config.py`; the `--sample-rate` CLI arg and `VoskASR(sample_rate=...)` constructor already exist. BotSprite fix extracts a `_get_scaled_frames(max_width, max_height)` helper that scales each state's frames once and caches the result, invalidating only when the bounding box size changes (which never happens on a fixed-resolution kiosk).

**Tech Stack:** Python, `configparser`, `sounddevice` / `vosk`, `pygame-ce`, `pytest`.

---

## File Structure

| File | Change |
|---|---|
| `config/settings.ini` | Add `sample_rate = 16000` under `[Speech]` |
| `src/ella_bot/config/app_config.py` | Load `sample_rate` from `[Speech]` section |
| `src/ella_bot/ui/pygame_gui/bot_sprite.py` | Add `_scaled_cache` dict + `_get_scaled_frames()` helper; `draw()` uses cache |
| `tests/test_config.py` | Add assertion that `load_settings` maps `sample_rate` |
| `tests/test_bot_sprite.py` | Add cache-reuse and cache-invalidation tests |

---

### Task 1: Wire Vosk 16 kHz default through settings and config loader

**Files:**
- Modify: `config/settings.ini` — add `sample_rate = 16000` under `[Speech]`
- Modify: `src/ella_bot/config/app_config.py:26-32` — add `sample_rate` read
- Test: `tests/test_config.py`

**Background:** `VoskASR.__init__` accepts `sample_rate: int | None`. When `None`, `transcribe()` auto-detects the device default (typically 48 kHz on ReSpeaker). The Vosk small-EN model is trained at 16 kHz — running at 48 kHz wastes CPU and degrades accuracy. The `--sample-rate` CLI argument and `build_asr(sample_rate=...)` factory call already exist; they just need a default value in the settings file.

- [ ] **Step 1: Write the failing test**

In `tests/test_config.py`, append:

```python
def test_load_settings_maps_sample_rate():
    from ella_bot.config.app_config import load_settings
    settings = load_settings()
    assert settings.get("sample_rate") == 16000
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_config.py::test_load_settings_maps_sample_rate -v`
Expected: FAIL — `settings.get("sample_rate")` returns `None` because neither `settings.ini` nor `load_settings()` set this key yet.

- [ ] **Step 3: Add sample_rate to settings.ini**

In `config/settings.ini`, under the `[Speech]` section, add the new key so the section reads:

```ini
[Speech]
use_mic = True
vosk_model = ./models/vosk-model-small-en-us-0.15
listen_seconds = 5
sample_rate = 16000
```

- [ ] **Step 4: Load sample_rate in app_config.py**

In `src/ella_bot/config/app_config.py`, inside the `if parser.has_section("Speech"):` block, add after the `listen_seconds` read:

```python
        if parser.has_option("Speech", "sample_rate"):
            defaults["sample_rate"] = parser.getint("Speech", "sample_rate")
```

The complete `Speech` block should look like:

```python
    if parser.has_section("Speech"):
        if parser.has_option("Speech", "use_mic"):
            defaults["use_mic"] = parser.getboolean("Speech", "use_mic")
        if parser.has_option("Speech", "vosk_model"):
            defaults["vosk_model"] = parser.get("Speech", "vosk_model")
        if parser.has_option("Speech", "listen_seconds"):
            defaults["listen_seconds"] = parser.getint("Speech", "listen_seconds")
        if parser.has_option("Speech", "sample_rate"):
            defaults["sample_rate"] = parser.getint("Speech", "sample_rate")
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_config.py::test_load_settings_maps_sample_rate -v`
Expected: PASS.

- [ ] **Step 6: Run the full test suite**

Run: `.venv/bin/python -m pytest -v`
Expected: all tests PASS (no regressions).

- [ ] **Step 7: Commit**

```bash
git add config/settings.ini src/ella_bot/config/app_config.py tests/test_config.py
git commit -m "perf: default Vosk sample rate to 16kHz via settings.ini"
```

---

### Task 2: Cache BotSprite scaled frames per target size

**Files:**
- Modify: `src/ella_bot/ui/pygame_gui/bot_sprite.py`
- Test: `tests/test_bot_sprite.py`

**Background:** `BotSprite.draw()` calls `pygame.transform.smoothscale(frame, target_size)` on every render tick at 60 FPS. On a Pi 5 this is a significant per-frame CPU cost. The scaled size only changes when the window resizes (never on a fixed-resolution kiosk). Fix: extract a `_get_scaled_frames(max_width, max_height)` helper that scales all frames for the current state once and stores the results in `self._scaled_cache`. If `(max_width, max_height)` changes, the entire cache is cleared and rebuilt.

- [ ] **Step 1: Write the failing tests**

In `tests/test_bot_sprite.py`, append:

```python
def test_scaled_frames_are_cached_on_repeated_calls():
    from unittest.mock import MagicMock, patch
    from ella_bot.ui.pygame_gui.bot_sprite import BotSprite

    bot = object.__new__(BotSprite)
    fake_frame = MagicMock()
    fake_frame.get_width.return_value = 100
    fake_frame.get_height.return_value = 100
    fake_scaled = MagicMock()

    bot.frames = {"idle": [fake_frame]}
    bot.state = "idle"
    bot._scaled_cache = {}
    bot._cache_target_size = None

    with patch("ella_bot.ui.pygame_gui.bot_sprite.pygame.transform.smoothscale", return_value=fake_scaled) as mock_scale:
        bot._get_scaled_frames(200, 200)
        bot._get_scaled_frames(200, 200)  # same size — must use cache

    assert mock_scale.call_count == 1


def test_scaled_cache_clears_when_target_size_changes():
    from unittest.mock import MagicMock, patch
    from ella_bot.ui.pygame_gui.bot_sprite import BotSprite

    bot = object.__new__(BotSprite)
    fake_frame = MagicMock()
    fake_frame.get_width.return_value = 100
    fake_frame.get_height.return_value = 100
    fake_scaled = MagicMock()

    bot.frames = {"idle": [fake_frame]}
    bot.state = "idle"
    bot._scaled_cache = {}
    bot._cache_target_size = None

    with patch("ella_bot.ui.pygame_gui.bot_sprite.pygame.transform.smoothscale", return_value=fake_scaled) as mock_scale:
        bot._get_scaled_frames(200, 200)
        bot._get_scaled_frames(300, 300)  # size changed — must re-scale

    assert mock_scale.call_count == 2
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_bot_sprite.py::test_scaled_frames_are_cached_on_repeated_calls tests/test_bot_sprite.py::test_scaled_cache_clears_when_target_size_changes -v`
Expected: FAIL — `BotSprite` has no `_get_scaled_frames` method.

- [ ] **Step 3: Update BotSprite**

Replace the entire contents of `src/ella_bot/ui/pygame_gui/bot_sprite.py` with:

```python
from __future__ import annotations

import pygame

from ella_bot.utils.file_utils import get_project_root


def bot_state_for_app(app_state: str) -> str:
    if app_state == "processing":
        return "thinking"
    if app_state == "retry":
        return "error"
    if app_state == "success":
        return "idle"
    if app_state in {"idle", "listening", "speaking", "warmup"}:
        return app_state
    return "idle"


class BotSprite:
    """Owns the reading-prompt bot frames, animation ticking, and rendering."""

    def __init__(self) -> None:
        self.frames = self._load_frames()
        self.state = "idle"
        self.frame_index = 0
        self.last_tick_ms = 0
        self._scaled_cache: dict[str, list[pygame.Surface]] = {}
        self._cache_target_size: tuple[int, int] | None = None
        self.intervals_ms = {
            "idle": 1400,
            "listening": 320,
            "speaking": 160,
            "thinking": 200,
            "warmup": 200,
            "error": 1200,
        }

    def _load_frames(self) -> dict[str, list[pygame.Surface]]:
        base = get_project_root() / "bot"
        mapping = {
            "idle": base / "idle",
            "listening": base / "listening",
            "speaking": base / "speaking",
            "thinking": base / "thinking",
            "warmup": base / "warmup",
            "error": base / "error",
        }
        frames: dict[str, list[pygame.Surface]] = {}
        for state, folder in mapping.items():
            images: list[pygame.Surface] = []
            if folder.exists():
                for image_path in sorted(folder.glob("*.png")):
                    try:
                        image = pygame.image.load(str(image_path)).convert_alpha()
                        images.append(image)
                    except Exception:
                        continue
            if images:
                frames[state] = images
        return frames

    def _get_scaled_frames(self, max_width: int, max_height: int) -> list[pygame.Surface]:
        """Return scaled frames for the current state, caching by target bounding box.

        The cache is invalidated when (max_width, max_height) changes — which only
        happens on a window resize, never on a fixed-resolution Pi 5 kiosk.
        """
        target = (max_width, max_height)
        if target != self._cache_target_size:
            self._scaled_cache.clear()
            self._cache_target_size = target

        key = self.state if self.state in self.frames else "idle"
        if key not in self._scaled_cache:
            raw = self.frames.get(key, [])
            scaled: list[pygame.Surface] = []
            for f in raw:
                fw = max(1, f.get_width())
                fh = max(1, f.get_height())
                scale_factor = min(max_width / fw, max_height / fh)
                size = (max(1, int(fw * scale_factor)), max(1, int(fh * scale_factor)))
                scaled.append(pygame.transform.smoothscale(f, size))
            self._scaled_cache[key] = scaled
        return self._scaled_cache[key]

    def update(self, now_ms: int, app_state: str) -> None:
        next_state = bot_state_for_app(app_state)
        if next_state != self.state:
            self.state = next_state
            self.frame_index = 0
            self.last_tick_ms = 0

        frames = self.frames.get(self.state, [])
        if len(frames) <= 1:
            return

        if self.last_tick_ms == 0:
            self.last_tick_ms = now_ms
            return

        interval_ms = self.intervals_ms.get(self.state, 240)
        if now_ms - self.last_tick_ms >= interval_ms:
            self.frame_index = (self.frame_index + 1) % len(frames)
            self.last_tick_ms = now_ms

    def draw(self, screen: pygame.Surface, prompt_rect: pygame.Rect) -> None:
        max_width = int(prompt_rect.width * 0.32)
        max_height = int(prompt_rect.height * 0.42)

        scaled = self._get_scaled_frames(max_width, max_height)
        if not scaled:
            return

        rendered = scaled[self.frame_index % len(scaled)]
        overlap = int(rendered.get_height() * 0.28)
        target_rect = rendered.get_rect(
            bottomright=(prompt_rect.right - 26, prompt_rect.bottom + overlap - 48)
        )

        old_clip = screen.get_clip()
        try:
            screen.set_clip(prompt_rect)
            screen.blit(rendered, target_rect)
        finally:
            screen.set_clip(old_clip)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_bot_sprite.py -v`
Expected: all tests PASS (the 5 existing state-mapping tests + 2 new cache tests = 7 total).

- [ ] **Step 5: Run the full test suite**

Run: `.venv/bin/python -m pytest -v`
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/ella_bot/ui/pygame_gui/bot_sprite.py tests/test_bot_sprite.py
git commit -m "perf: cache BotSprite scaled frames per target size"
```

---

## Notes

- **Vosk sample rate**: if your audio device doesn't natively support 16 kHz, PortAudio will attempt software resampling. If that fails, override with `sample_rate = <device_native_rate>` in `settings.ini` or `--sample-rate` on the CLI. The ReSpeaker 2-mic HAT natively supports 16 kHz.
- **BotSprite cache and state changes**: when `self.state` changes (e.g., `idle` → `listening`), `update()` resets `frame_index`. The new state's frames may not be in `_scaled_cache` yet, but they'll be scaled on the first `draw()` call for that state — still far better than per-frame rescaling.
- **Deferred (separate plans):** Typed `AppConfig`, Tutorial/Settings scenes.
