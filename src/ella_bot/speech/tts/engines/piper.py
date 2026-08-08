from __future__ import annotations

import threading
from typing import Optional

import numpy as np
import sounddevice as sd
from piper import PiperVoice, SynthesisConfig

from ella_bot.speech.tts.base import BaseTTS, TTSConfig
from ella_bot.utils.logging import get_logger

logger = get_logger(__name__)


def _apply_warmth(pcm_int16: np.ndarray, volume: float = 1.0) -> np.ndarray:
    """Gentle FIR low-pass to soften harsh high frequencies, making the voice warmer."""
    audio = pcm_int16.astype(np.float32) / 32768.0
    b = np.array([0.25, 0.50, 0.25], dtype=np.float32)
    smoothed = np.convolve(audio, b, mode="same")
    output = 0.70 * audio + 0.30 * smoothed
    peak = np.max(np.abs(output)) if output.size else 0.0
    if peak > 0.0:
        output = output / peak * 0.98 * max(0.0, min(1.0, volume))
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
        self._pause_event = threading.Event()
        self._active_stream = None
        self._lock = threading.Lock()
        self._speak_lock = threading.Lock()

    @property
    def is_speaking(self) -> bool:
        with self._lock:
            return self._active_stream is not None

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
        self._pause_event.clear()
        with self._lock:
            if self._active_stream is not None:
                try:
                    self._active_stream.abort()
                except Exception:
                    pass

    def pause(self) -> None:
        self._pause_event.set()

    def resume(self) -> None:
        self._pause_event.clear()

    def set_volume(self, fraction: float) -> None:
        self.config.volume = fraction
        self._syn_config = self._get_syn_config(volume=fraction)

    def _speak_sync(self, text: str, stop_event: threading.Event, rate: Optional[int] = None) -> None:
        if not text.strip():
            return

        with self._speak_lock:
            syn_config = self._get_syn_config(rate=rate)

            stream = None
            try:
                if stop_event.is_set():
                    return

                if text.startswith(("phonemes:", "phonemes,")):
                    raw_phonemes_str = text[9:].strip()
                    phonemes_list = list(raw_phonemes_str)
                    phoneme_ids = self._voice.phonemes_to_ids(phonemes_list)

                    phoneme_syn_config = SynthesisConfig(
                        length_scale=syn_config.length_scale,
                        noise_scale=0.3,
                        noise_w_scale=0.3,
                        volume=syn_config.volume,
                    )
                    audio_sample = self._voice.phoneme_ids_to_audio(phoneme_ids, syn_config=phoneme_syn_config)

                    if audio_sample.dtype == np.float32:
                        audio_sample = (audio_sample * 32767).astype(np.int16)

                    # Peak normalize isolated phonemes to 98% volume for crisp, clear playback
                    audio_float = audio_sample.astype(np.float32)
                    peak = np.max(np.abs(audio_float)) if audio_float.size else 0.0
                    if peak > 0.0:
                        target_gain = 32767.0 * 0.98 * max(0.0, min(1.0, syn_config.volume))
                        audio_float = (audio_float / peak) * target_gain
                    pcm_warm = audio_float.astype(np.int16)
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

                    import time
                    chunk_samples = int(sample_rate * 0.05)
                    for i in range(0, len(pcm_warm), chunk_samples):
                        while self._pause_event.is_set() and not stop_event.is_set():
                            self.current_amplitude = 0.0
                            time.sleep(0.1)
                        if stop_event.is_set():
                            break
                        sub_chunk = pcm_warm[i:i+chunk_samples]
                        if sub_chunk.size > 0:
                            self.current_amplitude = float(np.max(np.abs(sub_chunk.astype(np.float32))) / 32768.0)
                        else:
                            self.current_amplitude = 0.0
                        stream.write(sub_chunk.tobytes())

                    # Wait for the phoneme audio to finish playing before closing
                    duration = len(pcm_warm) / sample_rate
                    chunk_time = 0.05
                    elapsed = 0.0
                    while elapsed < duration and not stop_event.is_set():
                        while self._pause_event.is_set() and not stop_event.is_set():
                            self.current_amplitude = 0.0
                            time.sleep(0.1)
                        if stop_event.is_set():
                            break
                        time.sleep(chunk_time)
                        elapsed += chunk_time
                else:
                    total_samples = 0
                    sample_rate = 22050
                    start_time = None
                    import time
                    for chunk in self._voice.synthesize(text, syn_config=syn_config):
                        if stop_event.is_set():
                            break
                        pcm = np.frombuffer(chunk.audio_int16_bytes, dtype=np.int16).copy()
                        pcm_warm = _apply_warmth(pcm, volume=syn_config.volume)
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
                                start_time = time.monotonic()

                        chunk_samples = int(chunk.sample_rate * 0.05)
                        for i in range(0, len(pcm_warm), chunk_samples):
                            while self._pause_event.is_set() and not stop_event.is_set():
                                self.current_amplitude = 0.0
                                time.sleep(0.1)
                                if start_time is not None:
                                    start_time += 0.1
                            if stop_event.is_set():
                                break
                            sub_chunk = pcm_warm[i:i+chunk_samples]
                            if sub_chunk.size > 0:
                                self.current_amplitude = float(np.max(np.abs(sub_chunk.astype(np.float32))) / 32768.0)
                            else:
                                self.current_amplitude = 0.0
                            stream.write(sub_chunk.tobytes())

                        total_samples += len(pcm_warm)
                        sample_rate = chunk.sample_rate

                    # Wait for the entire speech to finish playing naturally before closing the stream
                    if total_samples > 0 and stream is not None and start_time is not None:
                        duration = total_samples / sample_rate
                        chunk_time = 0.05
                        while not stop_event.is_set():
                            while self._pause_event.is_set() and not stop_event.is_set():
                                self.current_amplitude = 0.0
                                time.sleep(0.1)
                                start_time += 0.1
                            if stop_event.is_set():
                                break
                            elapsed = time.monotonic() - start_time
                            if elapsed >= duration:
                                break
                            time.sleep(chunk_time)

            except Exception as exc:
                logger.error("PiperTTS error: %s", exc)
            finally:
                self.current_amplitude = 0.0
                with self._lock:
                    self._active_stream = None
                    if stream is not None:
                        try:
                            if not stop_event.is_set():
                                stream.stop()
                            stream.close()
                        except Exception:
                            pass
