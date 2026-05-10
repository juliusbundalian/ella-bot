from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict

from ella_bot.speech.asr.simulated import SimulatedASR
from ella_bot.speech.asr.vosk_engine import VoskASR
from ella_bot.speech.tts.base import TTSConfig
from ella_bot.speech.tts.factory import build_tts
from ella_bot.ui.pygame_gui.config import GUIConfig
from ella_bot.ui.pygame_gui.app import EllaGUIApp
from ella_bot.utils.file_utils import get_project_root
from ella_bot.config.app_config import load_settings

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="E.L.L.A. offline reading assistant prototype")
    parser.add_argument(
        "--start-level",
        default="1a",
        choices=["1a", "1b", "1c", "1d", "1e", "1f", "1g", "2a", "2b", "2c", "2d", "3", "4"],
        help="Starting level for GUI progression mode.",
    )
    parser.add_argument(
        "--spoken",
        default="",
        help="Simulated spoken sentence text. If omitted with --use-mic, microphone ASR is used.",
    )
    parser.add_argument("--use-mic", action="store_true", help="Use microphone input with Vosk")
    parser.add_argument("--vosk-model", default="./models/vosk-model-small-en-us-0.15")
    parser.add_argument("--listen-seconds", type=int, default=4)
    parser.add_argument(
        "--input-device",
        type=int,
        default=None,
        help="Optional sounddevice input device index (see sounddevice query).",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=None,
        help="Optional microphone sample rate for ASR input. If omitted, the device default rate is used.",
    )
    parser.add_argument("--audio-feedback", action="store_true", help="Speak feedback aloud with offline TTS")
    parser.add_argument(
        "--tts-engine",
        default="auto",
        choices=["auto", "espeak", "pyttsx3", "say", "respeaker"],
        help="TTS backend for audio feedback.",
    )
    parser.add_argument("--tts-rate", type=int, default=150, help="Words-per-minute speech rate for TTS")
    parser.add_argument("--tts-voice", default=None, help="Optional TTS voice id/name")
    parser.add_argument(
        "--tts-non-blocking",
        action="store_true",
        help="Play TTS asynchronously when supported (espeak backend).",
    )
    parser.add_argument(
        "--pronunciation-overrides",
        default="./config/pronunciation_overrides.json",
        help="Path to JSON word->spoken_form overrides used for audio feedback.",
    )
    parser.add_argument("--gui", action="store_true", help="Run modern Pygame GUI instead of console output")
    parser.add_argument("--fullscreen", action="store_true", help="Launch GUI in fullscreen mode")
    parser.add_argument("--gui-width", type=int, default=1280, help="GUI window width (ignored in fullscreen)")
    parser.add_argument("--gui-height", type=int, default=720, help="GUI window height (ignored in fullscreen)")
    
    settings = load_settings()
    parser.set_defaults(**settings)
    
    return parser.parse_args()


def load_pronunciation_overrides(path: str) -> Dict[str, str]:
    file_path = resolve_existing_path(path, fallback_dir="config")
    if not file_path.exists():
        return {}

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    if not isinstance(data, dict):
        return {}

    overrides: Dict[str, str] = {}
    for key, value in data.items():
        if isinstance(key, str) and isinstance(value, str) and key.strip() and value.strip():
            overrides[key.strip().lower()] = value.strip()
    return overrides


def resolve_existing_path(path: str, fallback_dir: str | None = None) -> Path:
    """Resolve user-provided paths with optional project-folder fallback."""
    candidate = Path(path)
    if candidate.exists():
        return candidate

    if fallback_dir:
        fallback = get_project_root() / fallback_dir / path
        if fallback.exists():
            return fallback

    return candidate


def build_asr(args: argparse.Namespace):
    if args.use_mic:
        model_path = resolve_existing_path(args.vosk_model, fallback_dir="models")
        return VoskASR(
            model_path=str(model_path),
            sample_rate=args.sample_rate,
            listen_seconds=args.listen_seconds,
            input_device=args.input_device,
        )
    return SimulatedASR(simulated_text=args.spoken)


def build_tts_if_enabled(args: argparse.Namespace):
    if not args.audio_feedback:
        return None

    return build_tts(
        engine_name=args.tts_engine,
        config=TTSConfig(
            voice=args.tts_voice,
            rate=args.tts_rate,
            non_blocking=args.tts_non_blocking,
        ),
    )


def run_gui(args: argparse.Namespace) -> None:
    gui = EllaGUIApp(
        expected_sentence="",
        asr=build_asr(args),
        tts=build_tts_if_enabled(args),
        audio_feedback=args.audio_feedback,
        pronunciation_overrides=load_pronunciation_overrides(args.pronunciation_overrides),
        start_level=args.start_level,
        config=GUIConfig(
            width=args.gui_width,
            height=args.gui_height,
            fullscreen=args.fullscreen,
        ),
    )
    gui.run()


def main() -> None:
    args = parse_args()

    try:
        run_gui(args)
    except Exception as exc:
        print(f"[Runtime error] {exc}")


if __name__ == "__main__":
    main()
