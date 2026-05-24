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
