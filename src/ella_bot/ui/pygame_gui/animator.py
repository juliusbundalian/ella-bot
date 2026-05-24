from __future__ import annotations

from pathlib import Path
from typing import Dict, List


class AvatarAnimator:
    """Loads avatar frame sequences by state and advances frames at a fixed rate."""

    def __init__(
        self,
        pygame_module,
        assets_dir: Path,
        frame_size: tuple[int, int] | None,
        animation_fps: int = 10,
        speaking_fps: int = 5,
        loading_fps: int = 8,
        processing_fps: int = 4,
    ) -> None:
        self.pg = pygame_module
        self.assets_dir = assets_dir
        self.frame_size = frame_size or (360, 360)
        self._use_native_size = frame_size is None
        self.animation_interval_ms = max(40, int(1000 / max(1, animation_fps)))
        self.speaking_interval_ms = max(40, int(1000 / max(1, speaking_fps)))
        self.loading_interval_ms = max(40, int(1000 / max(1, loading_fps)))
        self.processing_interval_ms = max(40, int(1000 / max(1, processing_fps)))
        self.listening_interval_ms = 4000

        self.animations: Dict[str, List] = {}
        self.current_state = "neutral"
        self.frame_index = 0
        self.last_tick_ms = 0

        self._load_assets()
        if not self.animations:
            self._build_fallback_assets()

    @staticmethod
    def _is_mouth_animated_state(state: str) -> bool:
        return state in {"warmup", "speaking", "processing", "listening"}

    def _state_interval_ms(self, state: str) -> int:
        if state == "processing":
            return self.processing_interval_ms
        if state == "listening":
            return self.listening_interval_ms
        if state == "speaking":
            return self.speaking_interval_ms
        if state == "warmup":
            return self.loading_interval_ms
        return self.animation_interval_ms

    def _faces_base_dir(self) -> Path | None:
        for candidate in (self.assets_dir / "faces", self.assets_dir.parent / "faces"):
            if candidate.exists():
                return candidate
        return None

    def _faces_state_dirs(self) -> Dict[str, Path]:
        base = self._faces_base_dir()
        if base is None:
            return {}

        return {
            "warmup": base / "warmup",
            "idle": base / "idle",
            "neutral": base / "idle",
            "listening": base / "listening",
            "speaking": base / "speaking",
            "processing": base / "thinking",
            "success": base / "warmup",
            "retry": base / "error",
        }

    def _state_dirs(self) -> Dict[str, Path]:
        if self._faces_base_dir() is not None:
            return self._faces_state_dirs()

        base = self.assets_dir / "avatars" / "ella_default"
        return {
            "neutral": base / "neutral",
            "listening": base / "listening",
            "speaking": base / "speaking",
            "success": base / "success",
            "retry": base / "retry",
            "processing": base / "processing",
        }

    def _load_assets(self) -> None:
        for state, folder in self._state_dirs().items():
            frames: List = []
            if folder.exists():
                for image_path in sorted(folder.glob("*.png")):
                    try:
                        image = self.pg.image.load(str(image_path)).convert_alpha()
                        if not self._use_native_size:
                            image = self.pg.transform.smoothscale(image, self.frame_size)
                        frames.append(image)
                    except Exception:
                        continue
            if frames:
                self.animations[state] = frames

    def _fallback_frame(self, mouth_open: float, accent: tuple[int, int, int]):
        w, h = self.frame_size
        surface = self.pg.Surface((w, h), self.pg.SRCALPHA)
        body = self.pg.Rect(6, 6, w - 12, h - 12)
        self.pg.draw.rect(surface, (135, 209, 181), body, border_radius=26)
        self.pg.draw.rect(surface, (29, 63, 82), body, width=6, border_radius=26)

        face = self.pg.Rect(34, 34, w - 68, int(h * 0.58))
        self.pg.draw.rect(surface, (226, 246, 255), face, border_radius=18)
        self.pg.draw.rect(surface, (40, 74, 95), face, width=4, border_radius=18)

        eye_r = 8
        self.pg.draw.circle(surface, (31, 63, 83), (int(w * 0.42), int(h * 0.30)), eye_r)
        self.pg.draw.circle(surface, (31, 63, 83), (int(w * 0.58), int(h * 0.30)), eye_r)

        mouth_center = (int(w * 0.50), int(h * 0.47))
        mouth_width = int(w * 0.17)
        mouth_height = max(5, int((h * 0.08) * mouth_open))
        mouth = self.pg.Rect(0, 0, mouth_width, mouth_height)
        mouth.center = mouth_center
        self.pg.draw.ellipse(surface, accent, mouth)

        for x in (int(w * 0.25), int(w * 0.75)):
            self.pg.draw.rect(surface, (29, 63, 82), (x - 8, int(h * 0.75), 16, int(h * 0.16)), border_radius=4)

        return surface

    def _build_fallback_assets(self) -> None:
        self.animations = {
            "neutral": [self._fallback_frame(0.10, (66, 112, 142))],
            "listening": [self._fallback_frame(0.10, (21, 147, 122))],
            "processing": [self._fallback_frame(0.10, (207, 138, 39))],
            "speaking": [
                self._fallback_frame(0.28, (66, 112, 142)),
                self._fallback_frame(0.62, (66, 112, 142)),
                self._fallback_frame(0.40, (66, 112, 142)),
                self._fallback_frame(0.72, (66, 112, 142)),
            ],
            "success": [self._fallback_frame(0.10, (21, 147, 122))],
            "retry": [self._fallback_frame(0.10, (188, 67, 78))],
        }

    def set_state(self, state: str, reset: bool = False) -> None:
        if state not in self.animations:
            state = "neutral"

        if reset or self.current_state != state:
            self.current_state = state
            self.frame_index = 0
            self.last_tick_ms = 0

    def update(self, now_ms: int) -> None:
        frames = self.animations.get(self.current_state, [])
        if not self._is_mouth_animated_state(self.current_state):
            self.frame_index = 0
            self.last_tick_ms = 0
            return

        if len(frames) <= 1:
            return

        if self.last_tick_ms == 0:
            self.last_tick_ms = now_ms
            return

        interval_ms = self._state_interval_ms(self.current_state)
        if now_ms - self.last_tick_ms >= interval_ms:
            self.frame_index = (self.frame_index + 1) % len(frames)
            self.last_tick_ms = now_ms

    def current_frame(self):
        frames = self.animations.get(self.current_state) or self.animations.get("neutral")
        if not frames:
            self._build_fallback_assets()
            frames = self.animations["neutral"]

        if not self._is_mouth_animated_state(self.current_state):
            return frames[0]

        return frames[self.frame_index % len(frames)]
