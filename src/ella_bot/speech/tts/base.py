from __future__ import annotations

import importlib
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional

from ella_bot.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TTSConfig:
    voice: Optional[str] = None
    rate: int = 120
    non_blocking: bool = False
    piper_binary: Optional[str] = None
    piper_model: Optional[str] = None
    noise_scale: float = 0.667
    noise_w: float = 0.8
    length_scale: float = 1.0
    volume: float = 1.0
    kokoro_model: Optional[str] = None
    kokoro_voices: Optional[str] = None



class BaseTTS:
    current_amplitude: float = 0.0

    @property
    def is_speaking(self) -> bool:
        return False

    def speak(self, text: str, rate: Optional[int] = None) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        """Stop any active playback if supported."""
        return None

    def pause(self) -> None:
        """Pause playback, keeping the current state."""
        return None

    def resume(self) -> None:
        """Resume playback from the paused state."""
        return None

    def set_volume(self, fraction: float) -> None:
        return None


class EspeakTTS(BaseTTS):
    """Offline TTS using espeak-ng or espeak CLI."""

    def __init__(self, config: Optional[TTSConfig] = None):
        self.config = config or TTSConfig()
        self.binary = shutil.which("espeak-ng") or shutil.which("espeak")
        if not self.binary:
            raise RuntimeError("No espeak-ng/espeak binary found in PATH.")
        self._process: Optional[subprocess.Popen] = None

    def speak(self, text: str, rate: Optional[int] = None) -> None:
        print(f"[ELLA] Speaking: {text}")
        self.stop()
        actual_rate = rate if rate is not None else self.config.rate
        cmd = [self.binary, "-s", str(actual_rate)]
        if self.config.voice:
            cmd.extend(["-v", self.config.voice])
        cmd.append(text)

        if self.config.non_blocking:
            self._process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return

        self._process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self._process.wait()
        self._process = None

    def stop(self) -> None:
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
                self._process.wait(timeout=2)
            except Exception:
                pass
        self._process = None


class Pyttsx3TTS(BaseTTS):
    """Offline TTS using pyttsx3.

    Install: pip install pyttsx3
    """

    def __init__(self, config: Optional[TTSConfig] = None):
        self.config = config or TTSConfig()
        try:
            importlib.import_module("pyttsx3")
        except Exception as exc:
            raise RuntimeError("pyttsx3 is not installed. Run: pip install pyttsx3") from exc

    def speak(self, text: str, rate: Optional[int] = None) -> None:
        print(f"[ELLA] Speaking: {text}")
        import pyttsx3
        import platform

        # On Windows, ensure COM is initialized for the current thread
        if platform.system() == "Windows":
            try:
                import pythoncom
                pythoncom.CoInitialize()
            except Exception:
                pass

        # Initialize locally per-call to avoid cross-thread COM errors on Windows
        try:
            logger.info("[TTS] Initializing pyttsx3 engine...")
            engine = pyttsx3.init()
            actual_rate = rate if rate is not None else self.config.rate
            engine.setProperty("rate", actual_rate)

            if self.config.voice:
                for voice in engine.getProperty("voices"):
                    if self.config.voice.lower() in str(voice.name).lower() or self.config.voice in str(voice.id):
                        engine.setProperty("voice", voice.id)
                        break

            logger.info(f"[TTS] Speaking: {text[:40]}...")
            engine.say(text)
            logger.info("[TTS] Calling runAndWait()...")
            engine.runAndWait()
            logger.info("[TTS] runAndWait() finished.")

            # Explicitly delete engine to free COM references
            del engine
        except Exception as e:
            logger.warning(f"[TTS Error] pyttsx3 failed: {e}")
            raise


class MacSayTTS(BaseTTS):
    """Offline TTS using macOS built-in `say` command."""

    def __init__(self, config: Optional[TTSConfig] = None):
        self.config = config or TTSConfig()
        self.binary = shutil.which("say")
        if not self.binary:
            raise RuntimeError("macOS 'say' command not found in PATH.")
        if not self.config.voice:
            # Samantha is generally clearer and more natural for US English classroom demos.
            self.config.voice = "Samantha"
        self._process: Optional[subprocess.Popen] = None

    def speak(self, text: str, rate: Optional[int] = None) -> None:
        print(f"[ELLA] Speaking: {text}")
        self.stop()
        cmd = [self.binary]
        if self.config.voice:
            cmd.extend(["-v", self.config.voice])
        # Approximate words per minute setting.
        actual_rate = rate if rate is not None else self.config.rate
        cmd.extend(["-r", str(actual_rate), text])

        if self.config.non_blocking:
            self._process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return

        self._process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self._process.wait()
        self._process = None

    def stop(self) -> None:
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
                self._process.wait(timeout=2)
            except Exception:
                pass
        self._process = None


class ReSpeakerTTS(BaseTTS):
    """Offline TTS for ReSpeaker hardware on Raspberry Pi.

    Routes audio through ReSpeaker's speaker output.
    Install: sudo apt install alsa-utils
    """

    def __init__(self, config: Optional[TTSConfig] = None):
        self.config = config or TTSConfig()
        # Check if espeak is available (primary) or fall back to aplay + wav generation
        self.espeak_binary = shutil.which("espeak-ng") or shutil.which("espeak")
        if not self.espeak_binary:
            raise RuntimeError(
                "espeak-ng/espeak required for ReSpeaker TTS. Install with: sudo apt install espeak-ng"
            )
        self._process: Optional[subprocess.Popen] = None

    def speak(self, text: str, rate: Optional[int] = None) -> None:
        """Use espeak with ReSpeaker audio output via ALSA."""
        print(f"[ELLA] Speaking: {text}")
        self.stop()
        actual_rate = rate if rate is not None else self.config.rate
        cmd = [self.espeak_binary, "-s", str(actual_rate)]
        if self.config.voice:
            cmd.extend(["-v", self.config.voice])
        cmd.append(text)

        if self.config.non_blocking:
            self._process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return

        self._process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self._process.wait()
        self._process = None

    def stop(self) -> None:
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
                self._process.wait(timeout=2)
            except Exception:
                pass
        self._process = None


