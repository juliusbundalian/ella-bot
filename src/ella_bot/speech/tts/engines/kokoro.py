from __future__ import annotations

import threading
import numpy as np
import sounddevice as sd
from typing import Optional

from ella_bot.speech.tts.base import BaseTTS, TTSConfig

class KokoroTTS(BaseTTS):
    """High-quality offline TTS using Kokoro ONNX engine."""

    def __init__(self, config: TTSConfig, model_path: str, voices_path: str):
        self.config = config
        self.model_path = model_path
        self.voices_path = voices_path
        self._kokoro = None
        self._load_lock = threading.Lock()
        # Pre-load in background to reduce first-speech latency
        threading.Thread(target=self._get_engine, daemon=True).start()

    def _get_engine(self):
        with self._load_lock:
            if self._kokoro is None:
                try:
                    from kokoro_onnx import Kokoro
                    print(f"[TTS] Pre-loading Kokoro model from {self.model_path}...")
                    self._kokoro = Kokoro(self.model_path, self.voices_path)
                    # Warm-up run to initialize ONNX session kernels
                    self._kokoro.create(" ", voice="af_heart", speed=1.0, lang="en-us")
                    print("[TTS] Kokoro model loaded and warmed up.")
                except ImportError:
                    raise RuntimeError("kokoro-onnx is not installed. Run: pip install kokoro-onnx")
                except Exception as e:
                    print(f"[TTS Error] Failed to load Kokoro model: {e}")
            return self._kokoro

    def speak(self, text: str) -> None:
        if self.config.non_blocking:
            threading.Thread(target=self._speak_sync, args=(text,), daemon=True).start()
        else:
            self._speak_sync(text)

    def stop(self) -> None:
        try:
            sd.stop()
        except Exception:
            pass

    def _speak_sync(self, text: str) -> None:
        if not text.strip():
            return

        try:
            kokoro = self._get_engine()
            
            # Default voice to af_heart if not specified
            voice = self.config.voice or "af_heart"
            
            # Map rate to speed (Kokoro uses 1.0 as normal)
            # Ella's rate is usually around 150 (wpm). 
            # We'll use 1.0 as default.
            speed = 1.0
            if self.config.rate != 150:
                speed = self.config.rate / 150.0

            print(f"[Kokoro TTS] Generating speech with voice '{voice}' at speed {speed:.2f}...")
            samples, sample_rate = kokoro.create(
                text,
                voice=voice,
                speed=speed,
                lang="en-us"
            )

            if samples is not None and len(samples) > 0:
                sd.play(samples, sample_rate)
                sd.wait()

        except Exception as e:
            print(f"KokoroTTS Error: {e}")
