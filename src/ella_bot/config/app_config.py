from __future__ import annotations

import configparser
from pathlib import Path
from typing import Dict, Any

from ella_bot.utils.file_utils import get_project_root

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

    if parser.has_section("Speech"):
        if parser.has_option("Speech", "use_mic"):
            defaults["use_mic"] = parser.getboolean("Speech", "use_mic")
        if parser.has_option("Speech", "vosk_model"):
            defaults["vosk_model"] = parser.get("Speech", "vosk_model")
        if parser.has_option("Speech", "listen_seconds"):
            defaults["listen_seconds"] = parser.getint("Speech", "listen_seconds")

    if parser.has_section("TTS"):
        if parser.has_option("TTS", "audio_feedback"):
            defaults["audio_feedback"] = parser.getboolean("TTS", "audio_feedback")
        if parser.has_option("TTS", "tts_engine"):
            defaults["tts_engine"] = parser.get("TTS", "tts_engine")
        if parser.has_option("TTS", "tts_rate"):
            defaults["tts_rate"] = parser.getint("TTS", "tts_rate")
        if parser.has_option("TTS", "pronunciation_overrides"):
            defaults["pronunciation_overrides"] = parser.get("TTS", "pronunciation_overrides")

    if parser.has_section("GUI"):
        if parser.has_option("GUI", "gui"):
            defaults["gui"] = parser.getboolean("GUI", "gui")
        if parser.has_option("GUI", "fullscreen"):
            defaults["fullscreen"] = parser.getboolean("GUI", "fullscreen")
        if parser.has_option("GUI", "gui_width"):
            defaults["gui_width"] = parser.getint("GUI", "gui_width")
        if parser.has_option("GUI", "gui_height"):
            defaults["gui_height"] = parser.getint("GUI", "gui_height")

    return defaults
