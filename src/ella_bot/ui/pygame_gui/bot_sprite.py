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
        frames = self.frames.get(self.state) or self.frames.get("idle")
        if not frames:
            return
        frame = frames[self.frame_index % len(frames)]

        max_width = int(prompt_rect.width * 0.32)
        max_height = int(prompt_rect.height * 0.42)
        frame_w = max(1, frame.get_width())
        frame_h = max(1, frame.get_height())
        scale = min(max_width / frame_w, max_height / frame_h)
        target_size = (max(1, int(frame_w * scale)), max(1, int(frame_h * scale)))
        rendered = pygame.transform.smoothscale(frame, target_size)

        overlap = int(target_size[1] * 0.28)
        target_rect = rendered.get_rect(
            bottomright=(prompt_rect.right - 26, prompt_rect.bottom + overlap - 48)
        )

        old_clip = screen.get_clip()
        try:
            screen.set_clip(prompt_rect)
            screen.blit(rendered, target_rect)
        finally:
            screen.set_clip(old_clip)
