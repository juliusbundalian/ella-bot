from __future__ import annotations

"""Confetti animation component for Pygame GUI celebrations with real Lottie playback."""

import json
import math
import random
import time
from pathlib import Path
from typing import Dict, List, Tuple

from ella_bot.utils.file_utils import resolve_asset_path
from ella_bot.utils.logging import get_logger

logger = get_logger(__name__)

# Default USA Confetti Palette (Red, White, Blue) from USA confetti.json
USA_CONFETTI_COLORS: List[Tuple[int, int, int]] = [
    (214, 54, 59),   # Patriotic Red
    (14, 58, 94),    # Navy Blue
    (255, 255, 255), # White
]

USA_CONFETTI_SHAPES: List[str] = ["star", "rect", "circle", "streamer"]


def load_lottie_confetti_data(
    lottie_path: str | Path | None = None,
) -> Tuple[List[Tuple[int, int, int]], List[str]]:
    """Extracts colors and particle shape types from a Lottie confetti JSON file."""
    if lottie_path is None:
        try:
            target_path = resolve_asset_path("assets/lottie/USA confetti.json")
        except Exception:
            target_path = Path("assets/lottie/USA confetti.json")
    else:
        target_path = Path(lottie_path)

    if not target_path.exists():
        return USA_CONFETTI_COLORS, USA_CONFETTI_SHAPES

    try:
        data = json.loads(target_path.read_text(encoding="utf-8"))
        colors: List[Tuple[int, int, int]] = []
        shapes: List[str] = []

        def extract_recursive(obj):
            if isinstance(obj, dict):
                if obj.get("ty") in ("fl", "st") and "c" in obj:
                    k = obj["c"].get("k")
                    if isinstance(k, list) and len(k) >= 3 and all(isinstance(v, (int, float)) for v in k[:3]):
                        r = min(255, max(0, int(k[0] * 255)))
                        g = min(255, max(0, int(k[1] * 255)))
                        b = min(255, max(0, int(k[2] * 255)))
                        if (r, g, b) not in colors:
                            colors.append((r, g, b))

                ty = obj.get("ty")
                if ty == "sr":
                    shapes.append("star")
                elif ty == "el":
                    shapes.append("circle")
                elif ty == "rc":
                    shapes.append("rect")
                elif ty == "sh":
                    shapes.append("streamer")

                for val in obj.values():
                    extract_recursive(val)
            elif isinstance(obj, list):
                for item in obj:
                    extract_recursive(item)

        extract_recursive(data)

        if (255, 255, 255) not in colors:
            colors.append((255, 255, 255))

        final_colors = colors if colors else USA_CONFETTI_COLORS
        final_shapes = list(set(shapes)) if shapes else USA_CONFETTI_SHAPES
        return final_colors, final_shapes
    except Exception as exc:
        logger.warning(f"Error parsing Lottie confetti file '{target_path}': {exc}")
        return USA_CONFETTI_COLORS, USA_CONFETTI_SHAPES


class LottiePlayer:
    """Renders exact vector Lottie JSON animations frame-by-frame into Pygame surfaces using rlottie-python."""

    def __init__(self, lottie_path: str | Path):
        self.path = Path(lottie_path)
        self.anim = None
        self.total_frames = 0
        self.width = 0
        self.height = 0
        self.cache: Dict[Tuple[int, int, int], None] = {}
        self._init_lottie()

    def _init_lottie(self):
        try:
            import rlottie_python
            if self.path.exists():
                self.anim = rlottie_python.LottieAnimation.from_file(str(self.path))
                self.total_frames = self.anim.lottie_animation_get_totalframe()
                pil_img = self.anim.render_pillow_frame(0)
                self.width, self.height = pil_img.size
        except Exception as exc:
            logger.warning(f"Lottie player initialization skipped for '{self.path}': {exc}")
            self.anim = None

    def render_frame(self, pygame_module, progress: float, target_w: int, target_h: int):
        if not self.anim or self.total_frames == 0:
            return None, (0, 0)

        frame_idx = int(progress * (self.total_frames - 1))
        frame_idx = max(0, min(self.total_frames - 1, frame_idx))

        cache_key = (frame_idx, target_w, target_h)
        if cache_key in self.cache:
            return self.cache[cache_key]

        try:
            pil_img = self.anim.render_pillow_frame(frame_idx)
            surf = pygame_module.image.frombytes(pil_img.tobytes(), pil_img.size, pil_img.mode)
            
            # Preserve aspect ratio (fill/cover target dimensions)
            scale = max(target_w / self.width, target_h / self.height)
            scaled_w = max(1, int(self.width * scale))
            scaled_h = max(1, int(self.height * scale))
            
            if (self.width, self.height) != (scaled_w, scaled_h):
                surf = pygame_module.transform.smoothscale(surf, (scaled_w, scaled_h))

            pos_x = (target_w - scaled_w) // 2
            pos_y = (target_h - scaled_h) // 2
            result = (surf, (pos_x, pos_y))

            if len(self.cache) < 300:
                self.cache[cache_key] = result
            return result
        except Exception as exc:
            logger.warning(f"Failed rendering Lottie frame {frame_idx}: {exc}")
            return None, (0, 0)


class ConfettiParticle:
    def __init__(
        self,
        screen_w: int,
        screen_h: int,
        colors: List[Tuple[int, int, int]] | None = None,
        shape_types: List[str] | None = None,
    ):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.colors = colors if colors else USA_CONFETTI_COLORS
        self.shape_types = shape_types if shape_types else USA_CONFETTI_SHAPES
        self.reset()

    def reset(self):
        origin_x = random.choice([
            self.screen_w * 0.1,
            self.screen_w * 0.5,
            self.screen_w * 0.9,
            random.uniform(0, self.screen_w),
        ])
        self.x = origin_x
        self.y = random.uniform(-120, -10)

        angle = (
            random.uniform(-math.pi / 3, math.pi / 3)
            if self.x < self.screen_w / 2
            else random.uniform(-2 * math.pi / 3, -math.pi / 3)
        )
        speed = random.uniform(4, 14)
        self.vx = math.cos(angle) * speed + random.uniform(-2, 2)
        self.vy = random.uniform(1.5, 6)

        self.w = random.uniform(10, 20)
        self.h = random.uniform(10, 24)
        self.color = random.choice(self.colors)
        self.shape_type = random.choice(self.shape_types)

        self.rotation = random.uniform(0, 360)
        self.rot_speed = random.uniform(-8, 8)
        self.flutter_phase = random.uniform(0, 2 * math.pi)
        self.flutter_speed = random.uniform(0.05, 0.12)
        self.wobble_x = 0.0

    def update(self):
        self.flutter_phase += self.flutter_speed
        self.wobble_x = math.sin(self.flutter_phase) * 2.5
        self.x += self.vx * 0.35 + self.wobble_x
        self.y += self.vy * 0.75
        self.vy += 0.09
        self.rotation += self.rot_speed


class ConfettiAnimation:
    """Manages celebratory USA Lottie confetti playback and particle fallback."""

    def __init__(
        self,
        count: int = 160,
        lottie_path: str | Path | None = None,
    ):
        self.count = count
        if lottie_path is None:
            try:
                self.lottie_file = resolve_asset_path("assets/lottie/USA confetti.json")
            except Exception:
                self.lottie_file = Path("assets/lottie/USA confetti.json")
        else:
            self.lottie_file = Path(lottie_path)

        self.lottie_player = LottiePlayer(self.lottie_file) if self.lottie_file.exists() else None
        self.colors, self.shape_types = load_lottie_confetti_data(self.lottie_file)
        self.particles: List[ConfettiParticle] = []
        self.active = False
        self.start_time = 0.0
        self.duration = 4.0

    def trigger(self, duration: float = 4.0) -> None:
        self.duration = duration
        self.start_time = time.monotonic()
        self.active = True
        self.particles.clear()

    def update_and_render(self, pygame_module, screen) -> None:
        if not self.active:
            return

        elapsed = time.monotonic() - self.start_time
        if elapsed > self.duration:
            self.active = False
            self.particles.clear()
            return

        width, height = screen.get_size()

        # Spawn particles dynamically during the first half of animation
        if len(self.particles) < self.count and elapsed < self.duration * 0.7:
            for _ in range(min(14, self.count - len(self.particles))):
                self.particles.append(
                    ConfettiParticle(width, height, colors=self.colors, shape_types=self.shape_types)
                )

        # Attempt actual vector Lottie playback as primary layer
        if self.lottie_player and self.lottie_player.anim:
            try:
                progress = min(1.0, elapsed / self.duration)
                frame_surf, pos = self.lottie_player.render_frame(pygame_module, progress, width, height)
                if frame_surf is not None:
                    screen.blit(frame_surf, pos)
            except Exception as exc:
                logger.debug(f"Lottie rendering fallback: {exc}")

        fade = 1.0
        if elapsed > self.duration - 1.0:
            fade = max(0.0, (self.duration - elapsed) / 1.0)

        for p in self.particles:
            p.update()

            if p.y > height + 50:
                continue

            rad = math.radians(p.rotation)
            cos_r = math.cos(rad)
            sin_r = math.sin(rad)

            scale_w = max(0.2, abs(math.cos(p.flutter_phase * 1.5)))
            pw = p.w * scale_w
            ph = p.h

            cx, cy = p.x, p.y

            if fade < 1.0:
                r, g, b = p.color
                color = (int(r * fade), int(g * fade), int(b * fade))
            else:
                color = p.color

            try:
                if p.shape_type == "star":
                    star_pts = []
                    r_outer = pw / 2
                    r_inner = r_outer * 0.45
                    for i in range(10):
                        r_val = r_outer if i % 2 == 0 else r_inner
                        angle = rad + i * (math.pi / 5) - (math.pi / 2)
                        star_pts.append((cx + r_val * math.cos(angle), cy + r_val * math.sin(angle)))
                    pygame_module.draw.polygon(screen, color, star_pts)

                elif p.shape_type == "circle":
                    radius = max(2, int(pw / 2))
                    pygame_module.draw.circle(screen, color, (int(cx), int(cy)), radius)

                elif p.shape_type == "streamer":
                    corners = [
                        (-pw / 4, -ph),
                        (pw / 4, -ph),
                        (pw / 2, ph),
                        (-pw / 2, ph),
                    ]
                    pts = []
                    for dx, dy in corners:
                        rx = cx + (dx * cos_r - dy * sin_r)
                        ry = cy + (dx * sin_r + dy * cos_r)
                        pts.append((rx, ry))
                    pygame_module.draw.polygon(screen, color, pts)

                else:
                    corners = [
                        (-pw / 2, -ph / 2),
                        (pw / 2, -ph / 2),
                        (pw / 2, ph / 2),
                        (-pw / 2, ph / 2),
                    ]
                    pts = []
                    for dx, dy in corners:
                        rx = cx + (dx * cos_r - dy * sin_r)
                        ry = cy + (dx * sin_r + dy * cos_r)
                        pts.append((rx, ry))
                    pygame_module.draw.polygon(screen, color, pts)
            except Exception:
                pass
