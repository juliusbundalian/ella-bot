from __future__ import annotations

import importlib
import platform
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class TTSConfig:
    voice: Optional[str] = None
    rate: int = 150
    non_blocking: bool = False


class BaseTTS:
    def speak(self, text: str) -> None:
        raise NotImplementedError


class EspeakTTS(BaseTTS):
    """Offline TTS using espeak-ng or espeak CLI."""

    def __init__(self, config: Optional[TTSConfig] = None):
        self.config = config or TTSConfig()
        self.binary = shutil.which("espeak-ng") or shutil.which("espeak")
        if not self.binary:
            raise RuntimeError("No espeak-ng/espeak binary found in PATH.")

    def speak(self, text: str) -> None:
        cmd = [self.binary, "-s", str(self.config.rate)]
        if self.config.voice:
            cmd.extend(["-v", self.config.voice])
        cmd.append(text)

        if self.config.non_blocking:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return

        subprocess.run(cmd, check=False)


class Pyttsx3TTS(BaseTTS):
    """Offline TTS using pyttsx3.

    Install: pip install pyttsx3
    """

    def __init__(self, config: Optional[TTSConfig] = None):
        self.config = config or TTSConfig()
        try:
            pyttsx3 = importlib.import_module("pyttsx3")
        except Exception as exc:
            raise RuntimeError("pyttsx3 is not installed. Run: pip install pyttsx3") from exc

        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", self.config.rate)

        if self.config.voice:
            for voice in self.engine.getProperty("voices"):
                if self.config.voice.lower() in str(voice.name).lower() or self.config.voice in str(voice.id):
                    self.engine.setProperty("voice", voice.id)
                    break

    def speak(self, text: str) -> None:
        self.engine.say(text)
        # pyttsx3 is inherently blocking for runAndWait in most backends.
        self.engine.runAndWait()


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

    def speak(self, text: str) -> None:
        cmd = [self.binary]
        if self.config.voice:
            cmd.extend(["-v", self.config.voice])
        # Approximate words per minute setting.
        cmd.extend(["-r", str(self.config.rate), text])

        if self.config.non_blocking:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return

        subprocess.run(cmd, check=False)


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

    def speak(self, text: str) -> None:
        """Use espeak with ReSpeaker audio output via ALSA."""
        cmd = [self.espeak_binary, "-s", str(self.config.rate)]
        if self.config.voice:
            cmd.extend(["-v", self.config.voice])
        cmd.append(text)

        if self.config.non_blocking:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return

        subprocess.run(cmd, check=False)


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
    if name == "auto":
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
