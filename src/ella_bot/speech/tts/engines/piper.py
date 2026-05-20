from __future__ import annotations

import threading

import numpy as np
import sounddevice as sd
from piper import PiperVoice, SynthesisConfig

from ella_bot.speech.tts.base import BaseTTS, TTSConfig
from ella_bot.utils.logging import get_logger

logger = get_logger(__name__)


def _apply_warmth(pcm_int16: np.ndarray) -> np.ndarray:
    """Gentle FIR low-pass to soften harsh high frequencies, making the voice warmer."""
    audio = pcm_int16.astype(np.float32) / 32768.0
    b = np.array([0.25, 0.50, 0.25], dtype=np.float32)
    smoothed = np.convolve(audio, b, mode="same")
    output = 0.70 * audio + 0.30 * smoothed
    peak = np.max(np.abs(output)) if output.size else 0.0
    if peak > 0.95:
        output = output / peak * 0.95
    return (output * 32767).astype(np.int16)


class PiperTTS(BaseTTS):
    """Offline TTS using the in-process piper-tts package.

    The voice model is loaded once at construction and reused for every
    utterance, avoiding a per-call subprocess spawn (important on Pi 5).
    """

    def __init__(self, config: TTSConfig, piper_model: str):
        self.config = config or TTSConfig()
        self.piper_model = piper_model
        self._voice = PiperVoice.load(piper_model)
        self._syn_config = SynthesisConfig(
            length_scale=self.config.length_scale,
            noise_scale=self.config.noise_scale,
            noise_w_scale=self.config.noise_w,
        )
        self._stop = threading.Event()

    def speak(self, text: str) -> None:
        if self.config.non_blocking:
            threading.Thread(target=self._speak_sync, args=(text,), daemon=True).start()
        else:
            self._speak_sync(text)

    def stop(self) -> None:
        self._stop.set()
        try:
            sd.stop()
        except Exception:
            pass

    def _speak_sync(self, text: str) -> None:
        if not text.strip():
            return

        self._stop.clear()
        stream = None
        try:
            for chunk in self._voice.synthesize(text, syn_config=self._syn_config):
                if self._stop.is_set():
                    break
                pcm = np.frombuffer(chunk.audio_int16_bytes, dtype=np.int16).copy()
                pcm_warm = _apply_warmth(pcm)
                if stream is None:
                    stream = sd.RawOutputStream(
                        samplerate=chunk.sample_rate,
                        channels=chunk.sample_channels,
                        dtype="int16",
                    )
                    stream.start()
                stream.write(pcm_warm.tobytes())
        except Exception as exc:
            logger.error("PiperTTS error: %s", exc)
        finally:
            if stream is not None:
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass
