from __future__ import annotations

import json
import logging
import zipfile
from pathlib import Path
from typing import Optional

import pygame

logger = logging.getLogger(__name__)

try:
    import rlottie_python
except ImportError:
    rlottie_python = None


class LottieBackground:
    """Decodes and plays a looping Lottie background (.lottie or .json) using rlottie-python.
    
    Supports 'ping_pong', 'crossfade', and 'loop' modes for 100% smooth, seamless looping.
    """

    def __init__(
        self,
        lottie_path: Path | str,
        target_size: Optional[tuple[int, int]] = None,
        loop_mode: str = "crossfade",
        crossfade_frames: int = 15,
    ):
        self.lottie_path = Path(lottie_path)
        self.target_size = target_size
        self.loop_mode = loop_mode.lower()
        self.crossfade_frames = crossfade_frames
        self.fps: float = 30.0
        self.frame_duration_ms: float = 1000.0 / 30.0
        self.total_frames: int = 0
        self.total_duration_ms: float = 0.0
        self._anim: Optional[rlottie_python.LottieAnimation] = None
        self._last_frame_idx: int = -1
        self._current_surface: Optional[pygame.Surface] = None
        self._scaled_surface: Optional[pygame.Surface] = None
        self._last_scale_size: Optional[tuple[int, int]] = None
        self._temp_json_path: Optional[Path] = None
        self._loaded = False
        self._init_lottie()

    def _init_lottie(self) -> None:
        if rlottie_python is None:
            logger.warning("rlottie_python is not installed; LottieBackground disabled.")
            return

        if not self.lottie_path.exists():
            logger.error(f"Lottie file not found: {self.lottie_path}")
            return

        target_json_path = self.lottie_path
        extracted_path = self.lottie_path.parent / f"{self.lottie_path.stem}_extracted.json"

        # Check if pre-extracted JSON exists first (helps on Raspberry Pi with restricted permissions)
        if extracted_path.exists():
            target_json_path = extracted_path
        elif zipfile.is_zipfile(self.lottie_path):
            try:
                with zipfile.ZipFile(self.lottie_path) as z:
                    json_file = None
                    for name in z.namelist():
                        if name.endswith(".json") and not name.startswith("manifest"):
                            json_file = name
                            break
                    if json_file:
                        json_bytes = z.read(json_file)
                        extracted_path.write_bytes(json_bytes)
                        target_json_path = extracted_path
                        self._temp_json_path = extracted_path
            except Exception as exc:
                logger.error(f"Failed extracting .lottie archive: {exc}")

        try:
            self._anim = rlottie_python.LottieAnimation.from_file(str(target_json_path))
            self.total_frames = self._anim.lottie_animation_get_totalframe()
            if self.total_frames > 0:
                if self.loop_mode == "ping_pong":
                    cycle_frames = 2 * (self.total_frames - 1)
                    self.total_duration_ms = (cycle_frames / self.fps) * 1000.0
                else:
                    self.total_duration_ms = (self.total_frames / self.fps) * 1000.0
                self._loaded = True
                logger.info(f"Initialized LottieBackground {self.lottie_path.name}: {self.total_frames} frames ({self.loop_mode} mode).")
        except Exception as exc:
            logger.error(f"Failed initializing Lottie animation: {exc}")

    def _get_target_index(self, now_ms: int) -> int:
        if self.total_frames <= 1:
            return 0

        if self.loop_mode == "ping_pong":
            cycle_frames = 2 * (self.total_frames - 1)
            step = int((now_ms % self.total_duration_ms) / self.frame_duration_ms) % cycle_frames
            return step if step < self.total_frames else cycle_frames - step

        return int((now_ms % self.total_duration_ms) / self.frame_duration_ms) % self.total_frames

    def get_frame(self, now_ms: int, target_size: Optional[tuple[int, int]] = None) -> Optional[pygame.Surface]:
        if not self._loaded or self._anim is None or self.total_frames == 0:
            return None

        size = target_size or self.target_size
        target_idx = self._get_target_index(now_ms)

        if target_idx != self._last_frame_idx or self._current_surface is None:
            try:
                pil_img = self._anim.render_pillow_frame(target_idx)
                surf = pygame.image.frombytes(pil_img.tobytes(), pil_img.size, pil_img.mode)

                # Cross-fade boundary blending if enabled
                if self.loop_mode == "crossfade" and target_idx >= self.total_frames - self.crossfade_frames:
                    fade_progress = (target_idx - (self.total_frames - self.crossfade_frames)) / float(self.crossfade_frames)
                    pil_start = self._anim.render_pillow_frame(0)
                    start_surf = pygame.image.frombytes(pil_start.tobytes(), pil_start.size, pil_start.mode)
                    start_surf.set_alpha(int(fade_progress * 255))
                    surf.blit(start_surf, (0, 0))

                self._current_surface = surf
                self._last_frame_idx = target_idx
                self._scaled_surface = None
            except Exception as exc:
                logger.warning(f"Error rendering Lottie frame {target_idx}: {exc}")
                return None

        if self._current_surface is None:
            return None

        if size and self._current_surface.get_size() != size:
            if self._scaled_surface is None or self._last_scale_size != size:
                self._scaled_surface = pygame.transform.smoothscale(self._current_surface, size)
                self._last_scale_size = size
            return self._scaled_surface

        return self._current_surface

    def release(self) -> None:
        self._anim = None
        self._loaded = False
        if self._temp_json_path and self._temp_json_path.exists():
            try:
                self._temp_json_path.unlink()
            except Exception:
                pass
