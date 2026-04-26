from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Dict, List

from ella_bot.feedback.feedback_engine import (
    build_feedback,
    build_spoken_feedback_with_coaching,
)
from ella_bot.speech.offline_asr import SimulatedASR, VoskASR
from ella_bot.speech.tts_offline import TTSConfig, build_tts
from ella_bot.ui.console_ui import render_result
from ella_bot.ui.gui_config import GUIConfig
from ella_bot.ui.gui_pygame import EllaGUIApp
from ella_bot.validation.text_validation import (
    build_highlighted_expected,
    normalize,
    spoken_word_confidence_map,
    validate_spoken_text,
)


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
    parser.add_argument("--audio-feedback", action="store_true", help="Speak feedback aloud with offline TTS")
    parser.add_argument(
        "--tts-engine",
        default="auto",
        choices=["auto", "espeak", "pyttsx3", "say"],
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
    """Resolve user-provided paths with optional project-folder fallback.

    If `path` does not exist and has no path separator, this tries `./<fallback_dir>/<path>`.
    """
    candidate = Path(path)
    if candidate.exists():
        return candidate

    if fallback_dir and candidate.parent == Path("."):
        fallback = Path(f"./{fallback_dir}") / path
        if fallback.exists():
            return fallback

    return candidate


def build_asr(args: argparse.Namespace):
    if args.use_mic:
        model_path = resolve_existing_path(args.vosk_model, fallback_dir="models")
        return VoskASR(
            model_path=str(model_path),
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
