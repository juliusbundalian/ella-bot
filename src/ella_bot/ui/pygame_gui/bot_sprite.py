from __future__ import annotations

import pygame

from ella_bot.utils.file_utils import get_project_root


def bot_state_for_app(app_state: str) -> str:
    if app_state == "processing":
        return "thinking"
    if app_state == "retry":
        return "idle"
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
            "idle": 140,
            "listening": 320,
            "speaking": 100,
            "thinking": 200,
            "warmup": 200,
            "error": 1200,
        }

    def _load_frames(self) -> dict[str, list[pygame.Surface]]:
        base = get_project_root() / "bot"
        robot_svg_dir = get_project_root() / "assets" / "Robot SVG"
        talking_png_dir = get_project_root() / "assets" / "talking png"

        frames: dict[str, list[pygame.Surface]] = {}

        # 1. Load speaking frames from assets/talking png for TTS speech
        speaking_images: list[pygame.Surface] = []
        if talking_png_dir.exists():
            for image_path in sorted(talking_png_dir.glob("speak_*.png")):
                try:
                    image = pygame.image.load(str(image_path)).convert_alpha()
                    speaking_images.append(image)
                except Exception:
                    continue

        if speaking_images:
            frames["speaking"] = speaking_images
            static_pose = [speaking_images[0]]
            for state in ("listening", "thinking", "warmup", "error"):
                frames[state] = static_pose
        else:
            mapping: dict[str, list] = {
                "listening": [base / "listening"],
                "speaking": [base / "speaking"],
                "thinking": [base / "thinking"],
                "warmup": [base / "warmup"],
                "error": [base / "error"],
            }
            for state, folders in mapping.items():
                images: list[pygame.Surface] = []
                for folder in folders:
                    if folder.exists():
                        for pattern in ("*.svg", "*.png"):
                            for image_path in sorted(folder.glob(pattern)):
                                try:
                                    image = pygame.image.load(str(image_path)).convert_alpha()
                                    images.append(image)
                                except Exception:
                                    continue
                        if images:
                            break
                if images:
                    frames[state] = images

        # 2. Load idle frames from assets/Robot SVG (used for Main Menu)
        idle_images: list[pygame.Surface] = []
        if robot_svg_dir.exists():
            for pattern in ("*.svg", "*.png"):
                for image_path in sorted(robot_svg_dir.glob(pattern)):
                    try:
                        image = pygame.image.load(str(image_path)).convert_alpha()
                        idle_images.append(image)
                    except Exception:
                        continue

        if not idle_images:
            idle_folder = base / "idle"
            if idle_folder.exists():
                for pattern in ("*.svg", "*.png"):
                    for image_path in sorted(idle_folder.glob(pattern)):
                        try:
                            image = pygame.image.load(str(image_path)).convert_alpha()
                            idle_images.append(image)
                        except Exception:
                            continue

        if idle_images:
            frames["idle"] = idle_images
        elif speaking_images:
            frames["idle"] = [speaking_images[0]]

        return frames

    def _get_scaled_frames(self, max_width: int, max_height: int) -> list[pygame.Surface]:
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

    def update(self, now_ms: int, app_state: str, tts_amplitude: float = 0.0) -> None:
        next_state = bot_state_for_app(app_state)
        if next_state != self.state:
            self.state = next_state
            self.frame_index = 0
            self.last_tick_ms = 0

        frames = self.frames.get(self.state, [])
        if len(frames) <= 1:
            self.frame_index = 0
            return

        if self.state == "speaking" and tts_amplitude > 0.0:
            normalized = min(1.0, tts_amplitude / 0.50)
            self.frame_index = int(normalized * (len(frames) - 1))
            return

        if self.last_tick_ms == 0:
            self.last_tick_ms = now_ms
            return

        interval_ms = self.intervals_ms.get(self.state, 140)
        if now_ms - self.last_tick_ms >= interval_ms:
            self.frame_index = (self.frame_index + 1) % len(frames)
            self.last_tick_ms = now_ms

    def draw(self, screen: pygame.Surface, prompt_rect: pygame.Rect) -> pygame.Rect | None:
        max_width = int(prompt_rect.width * 0.50)
        max_height = int(prompt_rect.height * 0.90)

        scaled = self._get_scaled_frames(max_width, max_height)
        if not scaled:
            return None

        rendered = scaled[self.frame_index % len(scaled)]
        hide_lower_half_offset = int(rendered.get_height() * 0.27)
        target_rect = rendered.get_rect(
            bottomright=(prompt_rect.right + 100, prompt_rect.bottom + hide_lower_half_offset)
        )

        screen.blit(rendered, target_rect)
        return target_rect
