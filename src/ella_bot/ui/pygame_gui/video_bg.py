from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pygame

logger = logging.getLogger(__name__)

try:
    import cv2
except ImportError:
    cv2 = None


class VideoBackground:
    """Decodes and plays a looping MP4 video background using streaming frame decoding.
    
    Memory efficient (<25MB RAM) by decoding frames on-the-fly instead of
    pre-allocating all frames into memory.
    """

    def __init__(self, video_path: Path | str, target_size: Optional[tuple[int, int]] = None):
        self.video_path = str(video_path)
        self.target_size = target_size
        self.fps: float = 30.0
        self.frame_duration_ms: float = 1000.0 / 30.0
        self.total_frames: int = 0
        self.total_duration_ms: float = 0.0
        self._cap: Optional[cv2.VideoCapture] = None
        self._last_frame_idx: int = -1
        self._current_surface: Optional[pygame.Surface] = None
        self._scaled_surface: Optional[pygame.Surface] = None
        self._last_scale_size: Optional[tuple[int, int]] = None
        self._loaded = False
        self._init_video()

    def __bool__(self) -> bool:
        return self._loaded

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def _init_video(self) -> None:
        if cv2 is None:
            logger.warning("cv2 (opencv) is not installed; VideoBackground disabled.")
            return

        self._cap = cv2.VideoCapture(self.video_path)
        if not self._cap.isOpened():
            logger.error(f"Failed to open video file: {self.video_path}")
            return

        fps = self._cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if fps > 0:
            self.fps = fps
            self.frame_duration_ms = 1000.0 / fps

        self.total_frames = max(1, total_frames)
        self.total_duration_ms = self.total_frames * self.frame_duration_ms
        self._loaded = True
        logger.info(f"Initialized streaming video {self.video_path}: {self.total_frames} frames at {self.fps:.1f} FPS.")

    def get_frame(self, now_ms: int, target_size: Optional[tuple[int, int]] = None) -> Optional[pygame.Surface]:
        if not self._loaded or self._cap is None:
            return None

        size = target_size or self.target_size
        target_idx = int((now_ms % self.total_duration_ms) / self.frame_duration_ms) % self.total_frames

        if target_idx != self._last_frame_idx or self._current_surface is None:
            # Check if sequential frame or seek needed
            if target_idx != self._last_frame_idx + 1:
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, target_idx)

            ret, frame = self._cap.read()
            if not ret or frame is None:
                # Seek to start on loop end
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self._cap.read()

            if ret and frame is not None:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB).swapaxes(0, 1)
                self._current_surface = pygame.surfarray.make_surface(frame_rgb)
                self._last_frame_idx = target_idx
                self._scaled_surface = None  # Invalidate scale cache

        if self._current_surface is None:
            return None

        if size and self._current_surface.get_size() != size:
            if self._scaled_surface is None or self._last_scale_size != size:
                self._scaled_surface = pygame.transform.smoothscale(self._current_surface, size)
                self._last_scale_size = size
            return self._scaled_surface

        return self._current_surface

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self._loaded = False
