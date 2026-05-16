from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Dict, List

from ella_bot.validation.feedback import (
    build_feedback,
    build_spoken_feedback_with_coaching,
)
from ella_bot.speech.asr.simulated import SimulatedASR
from ella_bot.speech.asr.vosk_engine import VoskASR
from ella_bot.speech.tts.base import TTSConfig
from ella_bot.speech.tts.factory import build_tts
from ella_bot.ui.console.console_ui import render_result
from ella_bot.ui.pygame_gui.config import GUIConfig
from ella_bot.ui.pygame_gui.app import EllaGUIApp
from ella_bot.validation.validators import (
    build_highlighted_expected,
    normalize,
    spoken_word_confidence_map,
    validate_spoken_text,
)
from ella_bot.utils.file_utils import get_project_root
from ella_bot.config.app_config import load_settings

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="E.L.L.A. offline reading assistant prototype")
    parser.add_argument("--expected", help="Expected sentence")
    parser.add_argument(
        "--sentence-file",
        default="./config/sample_sentences.txt",
        help="Path to a text file containing one practice sentence per line.",
    )
    parser.add_argument(
        "--sentence-id",
        type=int,
        default=1,
        help="1-based index into sentence file when --expected is omitted.",
    )
    parser.add_argument(
        "--random-sentence",
        action="store_true",
        help="Choose a random sentence from sentence file when --expected is omitted.",
    )
    parser.add_argument(
        "--list-sentences",
        action="store_true",
        help="Print available sample sentences from sentence file and exit.",
    )
    parser.add_argument(
        "--start-level",
        default="easy",
        choices=["easy", "medium-a", "medium-b", "medium-c", "hard"],
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


def load_sample_sentences(path: str) -> List[str]:
    file_path = resolve_existing_path(path, fallback_dir="config")
    if not file_path.exists():
        return []

    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []

    sentences = [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]
    return sentences


def resolve_expected_sentence(args: argparse.Namespace) -> str:
    if args.expected and args.expected.strip():
        return args.expected.strip()

    sentences = load_sample_sentences(args.sentence_file)
    if not sentences:
        raise ValueError(
            "No expected sentence provided and no sample sentences found. "
            "Use --expected or provide --sentence-file with sentences."
        )

    if args.random_sentence:
        return random.choice(sentences)

    index = max(1, args.sentence_id)
    if index > len(sentences):
        index = len(sentences)
    return sentences[index - 1]


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
            piper_binary=args.piper_binary,
            piper_model=args.piper_model,
            noise_scale=args.noise_scale,
            noise_w=args.noise_w,
            length_scale=args.length_scale,
            kokoro_model=args.kokoro_model,
            kokoro_voices=args.kokoro_voices,
        ),
    )


def run_console(args: argparse.Namespace) -> None:
    asr = build_asr(args)
    asr_result = asr.transcribe(expected_sentence=args.expected)

    validation = validate_spoken_text(args.expected, asr_result.transcript)

    spoken_tokens = normalize(asr_result.transcript)
    confidences = [w.confidence for w in asr_result.words][: len(spoken_tokens)]
    conf_map = spoken_word_confidence_map(spoken_tokens, confidences)

    feedback = build_feedback(validation=validation, spoken_confidence_by_word=conf_map)

    highlighted = build_highlighted_expected(validation.alignment)
    output = render_result(
        expected_sentence=args.expected,
        spoken_sentence=asr_result.transcript,
        highlighted_expected=highlighted,
        validation=validation,
        feedback=feedback,
    )
    print(output)

    if args.audio_feedback:
        overrides = load_pronunciation_overrides(args.pronunciation_overrides)
        tts = build_tts_if_enabled(args)
        if tts is None:
            return

        spoken_lines = build_spoken_feedback_with_coaching(
            feedback=feedback,
            overrides=overrides,
            expected_sentence=args.expected,
            max_hints=2,
        )

        for line in spoken_lines:
            tts.speak(line)


def run_gui(args: argparse.Namespace) -> None:
    hard_sentences = load_sample_sentences(args.sentence_file)
    if not hard_sentences and args.expected:
        hard_sentences = [args.expected]

    gui = EllaGUIApp(
        expected_sentence=args.expected,
        asr=build_asr(args),
        tts=build_tts_if_enabled(args),
        audio_feedback=args.audio_feedback,
        pronunciation_overrides=load_pronunciation_overrides(args.pronunciation_overrides),
        hard_sentences=hard_sentences,
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

    if args.list_sentences:
        sentences = load_sample_sentences(args.sentence_file)
        if not sentences:
            print("No sample sentences found.")
            return
        for idx, sentence in enumerate(sentences, start=1):
            print(f"{idx}. {sentence}")
        return

    args.expected = resolve_expected_sentence(args)

    try:
        if args.gui:
            run_gui(args)
        else:
            run_console(args)
    except Exception as exc:
        print(f"[Runtime error] {exc}")


if __name__ == "__main__":
    main()
