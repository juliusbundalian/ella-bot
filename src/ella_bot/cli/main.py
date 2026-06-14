from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict

from ella_bot.speech.asr.factory import build_asr as build_asr_engine
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
        "--session-log",
        default="./data/sessions.jsonl",
        help="Path to the JSONL evaluation log (relative paths resolve against the project root).",
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
        choices=["auto", "espeak", "pyttsx3", "say", "respeaker", "piper", "kokoro"],
        help="TTS backend for audio feedback.",
    )
    parser.add_argument("--piper-binary", default="./piper/piper.exe", help="Path to Piper TTS binary")
    parser.add_argument("--piper-model", default="./models/bmo.onnx", help="Path to Piper voice model (.onnx)")
    parser.add_argument("--tts-rate", type=int, default=150, help="Words-per-minute speech rate for TTS")
    parser.add_argument("--tts-voice", default=None, help="Optional TTS voice id/name")
    parser.add_argument(
        "--tts-non-blocking",
        action="store_true",
        help="Play TTS asynchronously when supported (espeak backend).",
    )
    parser.add_argument("--kokoro-model", default="./models/kokoro-v1.0.onnx", help="Path to Kokoro ONNX model")
    parser.add_argument("--kokoro-voices", default="./models/voices-v1.0.bin", help="Path to Kokoro voices bin file")
    parser.add_argument(
        "--pronunciation-overrides",
        default="./config/pronunciation_overrides.json",
        help="Path to JSON word->spoken_form overrides used for audio feedback.",
    )
    # Piper synthesis parameters for expression
    parser.add_argument("--noise-scale", type=float, default=0.667, help="Piper variability (0.0-1.0)")
    parser.add_argument("--noise-w", type=float, default=0.8, help="Piper phoneme length variability")
    parser.add_argument("--length-scale", type=float, default=1.0, help="Piper synthesis speed (lower is faster)")
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
        return candidate.absolute()

    # If the path is relative, try looking in the project root
    root_relative = get_project_root() / path
    if root_relative.exists():
        return root_relative.absolute()

    # Special fallback for specific directories if provided
    if fallback_dir:
        # If path already contains the fallback_dir, don't double-prepend
        if fallback_dir in candidate.parts:
             fallback = get_project_root() / path
        else:
             fallback = get_project_root() / fallback_dir / path
             
        if fallback.exists():
            return fallback.absolute()

    return candidate


def build_asr(args: argparse.Namespace):
    model_path = ""
    if args.use_mic:
        model_path = str(resolve_existing_path(args.vosk_model, fallback_dir="models"))
    return build_asr_engine(
        use_mic=args.use_mic,
        spoken=args.spoken,
        vosk_model_path=model_path,
        sample_rate=args.sample_rate,
        listen_seconds=args.listen_seconds,
        input_device=args.input_device,
    )


def build_tts_if_enabled(args: argparse.Namespace):
    if not args.audio_feedback:
        return None

    return build_tts(
        engine_name=args.tts_engine,
        config=TTSConfig(
            voice=args.tts_voice,
            rate=args.tts_rate,
            non_blocking=args.tts_non_blocking,
            piper_binary=args.piper_binary,
            piper_model=args.piper_model,
            noise_scale=args.noise_scale,
            noise_w=args.noise_w,
            length_scale=args.length_scale,
            volume=getattr(args, "volume", 1.0),
            kokoro_model=args.kokoro_model,
            kokoro_voices=args.kokoro_voices,
        ),
    )



def run_gui(args: argparse.Namespace) -> None:
    session_log = Path(args.session_log)
    if not session_log.is_absolute():
        session_log = get_project_root() / args.session_log

    start_level = args.start_level
    if start_level == "1a":
        from ella_bot.services.session_manager import get_resume_level
        recovered_level = get_resume_level(session_log, default_level="1a")
        if recovered_level != "1a":
            print(f"[SESSION SYSTEM] Detected past progress in log. Automatically resuming from Level {recovered_level.upper()}.")
            start_level = recovered_level

    gui = EllaGUIApp(
        expected_sentence="",
        asr=build_asr(args),
        tts=build_tts_if_enabled(args),
        audio_feedback=args.audio_feedback,
        pronunciation_overrides=load_pronunciation_overrides(args.pronunciation_overrides),
        start_level=start_level,
        config=GUIConfig(
            width=args.gui_width,
            height=args.gui_height,
            fullscreen=args.fullscreen,
            session_log_path=session_log,
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
