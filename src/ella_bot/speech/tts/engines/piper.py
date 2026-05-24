from __future__ import annotations

import subprocess
import threading
import numpy as np
import sounddevice as sd

from ella_bot.speech.tts.base import BaseTTS, TTSConfig

_PIPER_SAMPLE_RATE = 22050


def _apply_warmth(pcm_int16: np.ndarray) -> np.ndarray:
    """Gentle FIR low-pass to soften harsh high frequencies, making the voice warmer."""
    audio = pcm_int16.astype(np.float32) / 32768.0
    b = np.array([0.25, 0.50, 0.25], dtype=np.float32)
    smoothed = np.convolve(audio, b, mode="same")
    output = 0.70 * audio + 0.30 * smoothed
    peak = np.max(np.abs(output))
    if peak > 0.95:
        output = output / peak * 0.95
    return (output * 32767).astype(np.int16)


class PiperTTS(BaseTTS):
    """Offline TTS using Piper engine."""

    def __init__(self, config: TTSConfig, piper_binary: str, piper_model: str):
        self.config = config
        self.piper_binary = piper_binary
        self.piper_model = piper_model
        self._process: subprocess.Popen | None = None

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
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
                self._process.wait(timeout=2)
            except Exception:
                pass
        self._process = None

    def _speak_sync(self, text: str) -> None:
        if not text.strip():
            return

        process = None
        try:
            cmd = [
                self.piper_binary,
                "--model", self.piper_model,
                "--output-raw",
                "--noise_scale", str(self.config.noise_scale),
                "--noise_w", str(self.config.noise_w),
                "--length_scale", str(self.config.length_scale),
            ]
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            self._process = process
            process.stdin.write(text.encode("utf-8") + b"\n")
            process.stdin.close()

            # Buffer all PCM data first so we can post-process it
            raw_chunks = []
            while True:
                chunk = process.stdout.read(4096)
                if not chunk:
                    break
                raw_chunks.append(chunk)

            if not raw_chunks:
                return

            raw_bytes = b"".join(raw_chunks)
            pcm = np.frombuffer(raw_bytes, dtype=np.int16).copy()
            pcm_warm = _apply_warmth(pcm)

            # Use RawOutputStream for reliable playback on Windows
            with sd.RawOutputStream(samplerate=_PIPER_SAMPLE_RATE, channels=1, dtype='int16') as stream:
                stream.write(pcm_warm.tobytes())

        except Exception as e:
            print(f"PiperTTS Error: {e}")
        finally:
            if process:
                try:
                    if process.stdout:
                        process.stdout.close()
                    if process.poll() is None:
                        process.terminate()
                    process.wait()
                except Exception:
                    pass
            self._process = None
