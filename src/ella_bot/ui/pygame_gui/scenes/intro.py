from __future__ import annotations

import subprocess
import time
from typing import List, Optional
import cv2
import pygame

from ella_bot.ui.pygame_gui.scene import BaseScene
from ella_bot.utils.file_utils import resolve_asset_path


class IntroScene(BaseScene):
    def __init__(self, app):
        super().__init__(app)
        self.frames: List[pygame.Surface] = []
        self.fps: float = 30.0
        self.duration: float = 0.0
        self.start_time: float = 0.0
        self.sound: Optional[pygame.mixer.Sound] = None
        self.sound_channel: Optional[pygame.mixer.Channel] = None
        self.has_finished: bool = False
        self._video_loaded: bool = False

    def _ensure_audio(self, mp4_path, wav_path) -> bool:
        if wav_path.exists():
            return True
        try:
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            cmd = [
                ffmpeg_exe, "-y", "-i", str(mp4_path),
                "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
                str(wav_path)
            ]
            res = subprocess.run(cmd, capture_output=True)
            return res.returncode == 0 and wav_path.exists()
        except Exception as exc:
            print(f"[DEBUG] Error extracting intro audio: {exc}")
            return False

    def _load_video(self) -> None:
        if self._video_loaded:
            return
        mp4_path = resolve_asset_path("assets/intro_ella.mp4")
        if not mp4_path.exists():
            mp4_path = resolve_asset_path("intro_ella.mp4")

        wav_path = resolve_asset_path("assets/intro_ella.wav")
        if not wav_path.exists():
            wav_path = resolve_asset_path("intro_ella.wav")

        if not mp4_path.exists():
            self._video_loaded = True
            return

        self._ensure_audio(mp4_path, wav_path)

        try:
            cap = cv2.VideoCapture(str(mp4_path))
            self.fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            loaded_surfaces = []
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                surf = pygame.surfarray.make_surface(frame_rgb.swapaxes(0, 1))
                loaded_surfaces.append(surf)
            cap.release()

            self.frames = loaded_surfaces
            self.duration = len(self.frames) / self.fps if self.fps > 0 else 0.0

            if wav_path.exists() and pygame.mixer.get_init():
                self.sound = pygame.mixer.Sound(str(wav_path))
        except Exception as exc:
            print(f"[DEBUG] Failed loading intro video: {exc}")

        self._video_loaded = True

    def on_enter(self) -> None:
        self._load_video()
        self.start_time = time.monotonic()
        self.has_finished = False

        if self.sound:
            try:
                self.sound_channel = self.sound.play()
            except Exception:
                self.sound_channel = None

        if not self.frames:
            # Fallback immediately if video loading failed or file missing
            self.app.switch_scene("main_menu")

    def on_exit(self) -> bool:
        if self.sound_channel:
            try:
                self.sound_channel.stop()
            except Exception:
                pass
        return True

    def handle_event(self, event) -> None:
        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
            self._finish_and_advance()

    def _finish_and_advance(self) -> None:
        if self.has_finished:
            return
        self.has_finished = True
        if self.sound_channel:
            try:
                self.sound_channel.stop()
            except Exception:
                pass
        self.app.switch_scene("main_menu")

    def update(self, now_ms: int) -> None:
        if self.has_finished or not self.frames:
            return

        elapsed = time.monotonic() - self.start_time
        if elapsed >= self.duration + 0.2:
            self._finish_and_advance()

    def render(self) -> None:
        screen = self.app.screen
        width, height = screen.get_size()

        if not self.frames or self.has_finished:
            screen.fill((0, 0, 0))
            return

        elapsed = time.monotonic() - self.start_time
        frame_idx = min(max(0, int(elapsed * self.fps)), len(self.frames) - 1)
        current_frame = self.frames[frame_idx]

        fw, fh = current_frame.get_size()
        scale = max(width / fw, height / fh)
        target_size = (int(fw * scale), int(fh * scale))

        scaled_frame = pygame.transform.smoothscale(current_frame, target_size)
        dest_rect = scaled_frame.get_rect(center=(width // 2, height // 2))

        screen.blit(scaled_frame, dest_rect)
