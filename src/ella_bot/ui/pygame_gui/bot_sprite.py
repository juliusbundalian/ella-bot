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


import math


def draw_thought_bubble(
    screen: pygame.Surface,
    prompt_rect: pygame.Rect,
    now_ms: int,
    font: pygame.font.Font | None = None,
) -> None:
    """Draw speech bubble matching exact Main Menu design and placement displaying 'Waiting...'."""
    if prompt_rect is None or prompt_rect.width <= 0:
        return

    if font is None:
        try:
            font = pygame.font.Font(None, 28)
        except Exception:
            font = pygame.font.SysFont(None, 28, bold=True)

    # Animate dot count: "Waiting.", "Waiting..", "Waiting..."
    dot_count = (now_ms // 400) % 3 + 1
    text_str = "Waiting" + "." * dot_count
    text_surf = font.render(text_str, True, (255, 250, 243))

    inner_rect = prompt_rect.inflate(-64, -64)

    bubble_w = max(180, text_surf.get_width() + 48)
    bubble_h = 70

    bubble_right = inner_rect.right - 45
    bubble_x = bubble_right - bubble_w
    bubble_y = inner_rect.top + int(inner_rect.height * 0.31)

    bubble_rect = pygame.Rect(bubble_x, bubble_y, bubble_w, bubble_h)

    # 1. Drop shadow
    shadow_rect = pygame.Rect(bubble_rect.left + 4, bubble_rect.top + 4, bubble_w, bubble_h)
    pygame.draw.rect(screen, (25, 5, 35), shadow_rect, border_radius=35)

    # 2. Main pill body (#7F3F97)
    pygame.draw.rect(screen, (127, 63, 151), bubble_rect, border_radius=35)

    # 3. Outline stroke (#3B0C4C)
    pygame.draw.rect(screen, (59, 12, 76), bubble_rect, width=3, border_radius=35)

    # 4. Speech bubble tail pointing DOWNWARDS directly into the top of ELLA's head
    p1 = (bubble_rect.right - 65, bubble_rect.bottom - 2)
    p2 = (bubble_rect.right - 35, bubble_rect.bottom - 2)
    p3 = (bubble_rect.right - 45, bubble_rect.bottom + 38)

    pygame.draw.polygon(screen, (127, 63, 151), [p1, p2, p3])
    pygame.draw.line(screen, (59, 12, 76), p1, p3, 3)
    pygame.draw.line(screen, (59, 12, 76), p2, p3, 3)
    pygame.draw.line(screen, (127, 63, 151), p1, p2, 5)

    # 5. Text render
    text_rect = text_surf.get_rect(center=bubble_rect.center)
    screen.blit(text_surf, text_rect)


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

    def draw(
        self,
        screen: pygame.Surface,
        prompt_rect: pygame.Rect,
        show_thought_bubble: bool = False,
        now_ms: int = 0,
        font: pygame.font.Font | None = None,
    ) -> pygame.Rect | None:
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

        if show_thought_bubble:
            draw_thought_bubble(screen, prompt_rect, now_ms if now_ms > 0 else pygame.time.get_ticks(), font=font)

        return target_rect
