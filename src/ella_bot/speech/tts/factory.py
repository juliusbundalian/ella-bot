from __future__ import annotations

import importlib
import platform
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional


from ella_bot.speech.tts.base import (
    BaseTTS,
    TTSConfig,
    EspeakTTS,
    Pyttsx3TTS,
    MacSayTTS,
    ReSpeakerTTS,
)


def build_tts(engine_name: str, config: Optional[TTSConfig] = None) -> BaseTTS:
    name = engine_name.lower()

    if name == "espeak":
        return EspeakTTS(config=config)
    if name == "pyttsx3":
        return Pyttsx3TTS(config=config)
    if name == "say":
        return MacSayTTS(config=config)
    if name == "respeaker":
        return ReSpeakerTTS(config=config)
    if name == "piper":
        from ella_bot.speech.tts.engines.piper import PiperTTS
        from ella_bot.utils.file_utils import resolve_model_path
        from pathlib import Path
        model = resolve_model_path(
            (config.piper_model if config else None) or "en_US-hfc_female-medium.onnx"
        )
        if not Path(model).exists():
            print(f"[TTS Warning] Piper model file not found at {model}. falling back to auto-selection.")
            return build_tts("auto", config)
        return PiperTTS(config=config, piper_model=str(model))
    if name == "kokoro":
        from ella_bot.speech.tts.engines.kokoro import KokoroTTS
        from ella_bot.utils.file_utils import resolve_model_path
        from pathlib import Path
        model = resolve_model_path((config.kokoro_model if config else None) or "kokoro-v1.0.onnx")
        voices = resolve_model_path((config.kokoro_voices if config else None) or "voices-v1.0.bin")
        if not Path(model).exists() or not Path(voices).exists():
            print(f"[TTS Warning] Kokoro model or voices not found. falling back to auto-selection.")
            return build_tts("auto", config)
        return KokoroTTS(config=config, model_path=str(model), voices_path=str(voices))

    if name == "auto":
        from ella_bot.utils.file_utils import resolve_model_path
        from ella_bot.utils.logging import get_logger
        _log = get_logger(__name__)

        # 1. Prefer Piper (in-process neural TTS, light enough for Pi 5)
        piper_model = resolve_model_path(
            (config.piper_model if config else None) or "en_US-hfc_female-medium.onnx"
        )
        if piper_model.exists():
            try:
                from ella_bot.speech.tts.engines.piper import PiperTTS
                _log.info("[TTS] Auto-selecting Piper (Neural TTS). Model: %s", piper_model)
                return PiperTTS(config=config, piper_model=str(piper_model))
            except Exception as e:
                _log.warning("[TTS] Piper failed to load: %s", e)

        # 2. Fall back to Kokoro if its model files are present
        kokoro_model = resolve_model_path((config.kokoro_model if config else None) or "kokoro-v1.0.onnx")
        kokoro_voices = resolve_model_path((config.kokoro_voices if config else None) or "voices-v1.0.bin")
        if kokoro_model.exists() and kokoro_voices.exists():
            try:
                from ella_bot.speech.tts.engines.kokoro import KokoroTTS
                _log.info("[TTS] Auto-selecting Kokoro (High Quality Offline) for natural speech.")
                return KokoroTTS(config=config, model_path=str(kokoro_model), voices_path=str(kokoro_voices))
            except Exception as e:
                _log.warning("[TTS] Kokoro failed to load: %s", e)

        if platform.system() == "Darwin":
            try:
                return MacSayTTS(config=config)
            except Exception:
                try:
                    return Pyttsx3TTS(config=config)
                except Exception:
                    return EspeakTTS(config=config)

        # On Linux, check for ReSpeaker hardware first
        try:
            # Check if ReSpeaker kernel driver is loaded
            result = subprocess.run(
                ["lsmod"], capture_output=True, text=True, check=False
            )
            if "seeed_voicecard" in result.stdout or "ac108" in result.stdout:
                try:
                    return ReSpeakerTTS(config=config)
                except Exception:
                    pass
        except Exception:
            pass

        try:
            return EspeakTTS(config=config)
        except Exception:
            return Pyttsx3TTS(config=config)

    raise ValueError(f"Unsupported TTS engine: {engine_name}")
