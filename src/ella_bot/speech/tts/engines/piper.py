from __future__ import annotations

import threading
from typing import Optional

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
    if peak > 0.0:
        # Peak normalization to exactly 0.95 ensures consistent loud and clear volume
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
        self._syn_config = self._get_syn_config()
        self._stop = threading.Event()
        self._active_stream = None
        self._lock = threading.Lock()

    def _get_syn_config(self, volume: Optional[float] = None, rate: Optional[int] = None) -> SynthesisConfig:
        base_rate = 200.0
        target_rate = rate if (rate is not None and rate > 0) else (self.config.rate if (self.config.rate and self.config.rate > 0) else 200)
        speed_ratio = base_rate / target_rate
        
        return SynthesisConfig(
            length_scale=self.config.length_scale * speed_ratio,
            noise_scale=self.config.noise_scale,
            noise_w_scale=self.config.noise_w,
            volume=volume if volume is not None else self.config.volume,
        )

    def speak(self, text: str, rate: Optional[int] = None) -> None:
        print(f"[ELLA] Speaking: {text}")
        stop_event = threading.Event()
        self._stop = stop_event
        if self.config.non_blocking:
            threading.Thread(target=self._speak_sync, args=(text, stop_event, rate), daemon=True).start()
        else:
            self._speak_sync(text, stop_event, rate)

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            if self._active_stream is not None:
                try:
                    self._active_stream.abort()
                except Exception:
                    pass

    def set_volume(self, fraction: float) -> None:
        self.config.volume = fraction
        self._syn_config = self._get_syn_config(volume=fraction)

    def _speak_sync(self, text: str, stop_event: threading.Event, rate: Optional[int] = None) -> None:
        if not text.strip():
            return

        syn_config = self._get_syn_config(rate=rate)

        stream = None
        try:
            if stop_event.is_set():
                return

            if text.startswith(("phonemes:", "phonemes,")):
                raw_phonemes_str = text[9:].strip()
                phonemes_list = list(raw_phonemes_str)
                phoneme_ids = self._voice.phonemes_to_ids(phonemes_list)
                
                audio_sample = self._voice.phoneme_ids_to_audio(phoneme_ids, syn_config=syn_config)
                
                if audio_sample.dtype == np.float32:
                    audio_sample = (audio_sample * 32767).astype(np.int16)
                
                pcm_warm = _apply_warmth(audio_sample)
                sample_rate = getattr(self._voice.config, "sample_rate", 22050)
                
                stream = sd.RawOutputStream(
                    samplerate=sample_rate,
                    channels=1,
                    dtype="int16",
                )
                with self._lock:
                    if stop_event.is_set():
                        return
                    self._active_stream = stream
                    stream.start()
                
                stream.write(pcm_warm.tobytes())
                
                # Wait for the phoneme audio to finish playing before closing
                import time
                duration = len(pcm_warm) / sample_rate
                # Sleep in small responsive chunks to remain highly responsive to stop events
                chunk_time = 0.05
                elapsed = 0.0
                while elapsed < duration and not stop_event.is_set():
                    time.sleep(chunk_time)
                    elapsed += chunk_time
            else:
                total_samples = 0
                sample_rate = 22050
                start_time = None
                for chunk in self._voice.synthesize(text, syn_config=syn_config):
                    if stop_event.is_set():
                        break
                    pcm = np.frombuffer(chunk.audio_int16_bytes, dtype=np.int16).copy()
                    pcm_warm = _apply_warmth(pcm)
                    if stream is None:
                        stream = sd.RawOutputStream(
                            samplerate=chunk.sample_rate,
                            channels=chunk.sample_channels,
                            dtype="int16",
                        )
                        with self._lock:
                            if stop_event.is_set():
                                break
                            self._active_stream = stream
                            stream.start()
                            import time
                            start_time = time.monotonic()
                    stream.write(pcm_warm.tobytes())
                    total_samples += len(pcm_warm)
                    sample_rate = chunk.sample_rate
                
                # Wait for the entire speech to finish playing naturally before closing the stream
                if total_samples > 0 and stream is not None and start_time is not None:
                    import time
                    duration = total_samples / sample_rate
                    chunk_time = 0.05
                    while not stop_event.is_set():
                        elapsed = time.monotonic() - start_time
                        if elapsed >= duration:
                            break
                        time.sleep(chunk_time)
                
        except Exception as exc:
            logger.error("PiperTTS error: %s", exc)
        finally:
            with self._lock:
                self._active_stream = None
            if stream is not None:
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass
