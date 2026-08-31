from __future__ import annotations

import configparser
from typing import Dict, Any

from ella_bot.utils.file_utils import get_project_root


def save_setting(section: str, key: str, value: str) -> None:
    """Write a single key to settings.ini, preserving all other values."""
    config_path = get_project_root() / "config" / "settings.ini"
    if not config_path.exists():
        return
    parser = configparser.ConfigParser()
    parser.read(config_path, encoding="utf-8")
    if not parser.has_section(section):
        parser.add_section(section)
    parser.set(section, key, value)
    with open(config_path, "w", encoding="utf-8") as f:
        parser.write(f)


def load_settings() -> Dict[str, Any]:
    """Loads settings.ini into a dictionary suitable for argparse defaults."""
    config_path = get_project_root() / "config" / "settings.ini"
    
    defaults: Dict[str, Any] = {}
    if not config_path.exists():
        return defaults

    parser = configparser.ConfigParser()
    parser.read(config_path, encoding="utf-8")

    if parser.has_section("System"):
        if parser.has_option("System", "start_level"):
            defaults["start_level"] = parser.get("System", "start_level")
        if parser.has_option("System", "sentence_file"):
            defaults["sentence_file"] = parser.get("System", "sentence_file")
        if parser.has_option("System", "session_log"):
            defaults["session_log"] = parser.get("System", "session_log")

    if parser.has_section("Speech"):
        if parser.has_option("Speech", "use_mic"):
            defaults["use_mic"] = parser.getboolean("Speech", "use_mic")
        if parser.has_option("Speech", "vosk_model"):
            defaults["vosk_model"] = parser.get("Speech", "vosk_model")
        if parser.has_option("Speech", "listen_seconds"):
            defaults["listen_seconds"] = parser.getint("Speech", "listen_seconds")
        if parser.has_option("Speech", "sample_rate"):
            defaults["sample_rate"] = parser.getint("Speech", "sample_rate")
        if parser.has_option("Speech", "mic_gain"):
            defaults["mic_gain"] = parser.getfloat("Speech", "mic_gain")
        if parser.has_option("Speech", "input_device"):
            try:
                defaults["input_device"] = parser.getint("Speech", "input_device")
            except ValueError:
                defaults["input_device"] = None

    if parser.has_section("TTS"):
        if parser.has_option("TTS", "audio_feedback"):
            defaults["audio_feedback"] = parser.getboolean("TTS", "audio_feedback")
        if parser.has_option("TTS", "tts_engine"):
            defaults["tts_engine"] = parser.get("TTS", "tts_engine")
        if parser.has_option("TTS", "tts_rate"):
            defaults["tts_rate"] = parser.getint("TTS", "tts_rate")
        if parser.has_option("TTS", "pronunciation_overrides"):
            defaults["pronunciation_overrides"] = parser.get("TTS", "pronunciation_overrides")
        if parser.has_option("TTS", "piper_binary"):
            defaults["piper_binary"] = parser.get("TTS", "piper_binary")
        if parser.has_option("TTS", "piper_model"):
            defaults["piper_model"] = parser.get("TTS", "piper_model")
        if parser.has_option("TTS", "noise_scale"):
            defaults["noise_scale"] = parser.getfloat("TTS", "noise_scale")
        if parser.has_option("TTS", "noise_w"):
            defaults["noise_w"] = parser.getfloat("TTS", "noise_w")
        if parser.has_option("TTS", "length_scale"):
            defaults["length_scale"] = parser.getfloat("TTS", "length_scale")
        if parser.has_option("TTS", "volume"):
            defaults["volume"] = parser.getint("TTS", "volume") / 6.0
        if parser.has_option("TTS", "kokoro_model"):
            defaults["kokoro_model"] = parser.get("TTS", "kokoro_model")
        if parser.has_option("TTS", "kokoro_voices"):
            defaults["kokoro_voices"] = parser.get("TTS", "kokoro_voices")

    if parser.has_section("GUI"):
        if parser.has_option("GUI", "gui"):
            defaults["gui"] = parser.getboolean("GUI", "gui")
        if parser.has_option("GUI", "fullscreen"):
            defaults["fullscreen"] = parser.getboolean("GUI", "fullscreen")
        if parser.has_option("GUI", "gui_width"):
            defaults["gui_width"] = parser.getint("GUI", "gui_width")
        if parser.has_option("GUI", "gui_height"):
            defaults["gui_height"] = parser.getint("GUI", "gui_height")
        if parser.has_option("GUI", "gui_left_padding"):
            defaults["gui_left_padding"] = parser.getint("GUI", "gui_left_padding")

    return defaults
