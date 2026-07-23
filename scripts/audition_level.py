#!/usr/bin/env python3
"""Audition the spoken form of every item on a level through the real TTS engine.

This reproduces exactly what the app models for each item: it applies the same
level-scoped pronunciation overrides (tier-1 phonics blends only) and the same
"phonemes:" handling used by the start announcement, so you can verify by ear
that e.g. "go" sounds like the phonics blend on level 1c but like the natural
word on level 2a.

Examples:
    python scripts/audition_level.py 2a
    python scripts/audition_level.py 1c --only go
    python scripts/audition_level.py 2a --engine piper --rate 300
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

# Make src/ importable when run from the repo root.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ella_bot.speech.tts.base import TTSConfig  # noqa: E402
from ella_bot.speech.tts.factory import build_tts  # noqa: E402
from ella_bot.validation.feedback import overrides_for_level  # noqa: E402


STOP_CONSONANTS = frozenset("bcdgjkpt")
CONTINUOUS_CONSONANTS = frozenset("fhlmnrsvwyz")
SEQUENCE_CONSONANTS = frozenset("qx")
PIPER_COMPARISON_MODEL = "en_US-hfc_female-medium.onnx"


@dataclass(frozen=True)
class PiperVariant:
    name: str
    rate: int
    noise_scale: float
    noise_w_scale: float
    warmth: bool
    padding_ms: int


def consonant_class(letter: str) -> str:
    normalized = letter.lower()
    if normalized in STOP_CONSONANTS:
        return "stop"
    if normalized in CONTINUOUS_CONSONANTS:
        return "continuous"
    if normalized in SEQUENCE_CONSONANTS:
        return "sequence"
    raise ValueError(f"Unsupported level 1B consonant: {letter!r}")


def comparison_variants(letter: str) -> tuple[PiperVariant, ...]:
    class_rates = {"stop": 170, "continuous": 125, "sequence": 145}
    class_rate = class_rates[consonant_class(letter)]
    return (
        PiperVariant("current", 190, 0.667, 0.8, True, 0),
        PiperVariant("clean", 190, 0.3, 0.3, False, 0),
        PiperVariant("relaxed", 145, 0.3, 0.3, False, 200),
        PiperVariant("class-tuned", class_rate, 0.2, 0.2, False, 250),
    )


def validate_compare_request(level: str, engine: str, items: list[str]) -> str | None:
    if level.lower() != "1b":
        return "--compare-piper is only available for level 1b"
    if engine.lower() != "piper":
        return "--compare-piper requires --engine piper"
    if not items:
        return "--only did not match any level 1b target"
    return None


def validate_compare_targets(
    items: list[object], level_overrides: dict[str, object]
) -> tuple[list[tuple[str, str]], str | None]:
    targets = []
    for item in items:
        if not isinstance(item, str):
            return [], f"Unsupported level 1B consonant: {item!r}"
        try:
            consonant_class(item)
        except ValueError as exc:
            return [], str(exc)

        key = item.lower()
        if key not in level_overrides:
            return [], f"Comparison target {item!r} is missing pronunciation override"

        spoken = level_overrides[key]
        if not isinstance(spoken, str) or not spoken.startswith(("phonemes:", "phonemes,")):
            return [], f"Comparison target {item!r} is not a phoneme override: {spoken!r}"
        if not spoken[9:].strip():
            return [], f"Comparison target {item!r} has an empty phoneme payload"
        targets.append((item, spoken))

    return targets, None


def load_piper_voice(model_path: Path):
    from piper import PiperVoice

    return PiperVoice.load(str(model_path))


def _create_synthesis_config(**kwargs):
    from piper import SynthesisConfig

    return SynthesisConfig(**kwargs)


def _apply_warmth(pcm: np.ndarray) -> np.ndarray:
    from ella_bot.speech.tts.engines.piper import _apply_warmth as apply_warmth

    return apply_warmth(pcm)


def _play_audio(pcm: np.ndarray, sample_rate: int) -> None:
    import sounddevice as sd

    sd.play(pcm, samplerate=sample_rate)
    sd.wait()


def _as_int16(audio: np.ndarray) -> np.ndarray:
    if audio.dtype == np.float32 or audio.dtype == np.float64:
        return (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
    return audio.astype(np.int16, copy=False)


def play_piper_variant(voice, spoken: str, variant: PiperVariant) -> int:
    if not spoken.startswith(("phonemes:", "phonemes,")):
        raise ValueError(f"Comparison target is not a phoneme override: {spoken!r}")

    raw_phonemes = spoken[9:].strip()
    phoneme_ids = voice.phonemes_to_ids(list(raw_phonemes))
    syn_config = _create_synthesis_config(
        length_scale=200 / variant.rate,
        noise_scale=variant.noise_scale,
        noise_w_scale=variant.noise_w_scale,
        volume=1.0,
    )
    pcm = _as_int16(voice.phoneme_ids_to_audio(phoneme_ids, syn_config=syn_config))
    if variant.warmth:
        pcm = _apply_warmth(pcm)
    if variant.padding_ms:
        pad_samples = round(voice.config.sample_rate * variant.padding_ms / 1000)
        pcm = np.pad(pcm, (pad_samples, pad_samples))

    _play_audio(pcm, voice.config.sample_rate)
    return len(pcm)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("level", help="Level/sub-level to audition, e.g. 1c, 2a, 3")
    p.add_argument("--only", default=None, help="Only speak items containing this substring")
    p.add_argument("--engine", default="piper", help="TTS engine (default: piper)")
    p.add_argument(
        "--rate",
        type=int,
        default=190,
        help="Speech rate / words-per-minute. Lower is slower (default: 190)",
    )
    p.add_argument(
        "--gap",
        type=float,
        default=1.0,
        help="Seconds of silence to pause between items or comparison variants (default: 1.0)",
    )
    p.add_argument(
        "--piper-model",
        default="./models/en_US-hfc_female-medium.onnx",
        help="Path to Piper voice model",
    )
    p.add_argument(
        "--pools",
        default="./config/level_pools.json",
        help="Path to level_pools.json",
    )
    p.add_argument(
        "--overrides",
        default="./config/pronunciation_overrides.json",
        help="Path to pronunciation_overrides.json",
    )
    p.add_argument(
        "--compare-piper",
        action="store_true",
        help="Compare Piper tuning variants for isolated level 1b consonants",
    )
    p.add_argument("--dry-run", action="store_true", help="Print what would be spoken without playing audio")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    pools = json.loads((ROOT / args.pools).read_text(encoding="utf-8")) if not Path(args.pools).is_absolute() else json.loads(Path(args.pools).read_text(encoding="utf-8"))
    if args.level not in pools:
        print(f"Unknown level {args.level!r}. Available: {', '.join(pools)}")
        return 2

    raw_overrides = json.loads((ROOT / args.overrides).read_text(encoding="utf-8"))
    # Apply the SAME level scoping the app uses at runtime.
    level_overrides = overrides_for_level(args.level, raw_overrides)

    items = pools[args.level]
    if args.only:
        items = [w for w in items if args.only.lower() in w.lower()]

    if args.compare_piper:
        error = validate_compare_request(args.level, args.engine, items)
        if error:
            print(error, file=sys.stderr)
            return 2

        targets, error = validate_compare_targets(items, level_overrides)
        if error:
            print(error, file=sys.stderr)
            return 2

        model_path = Path(args.piper_model)
        if not model_path.is_absolute():
            model_path = ROOT / model_path
        if model_path.name != PIPER_COMPARISON_MODEL:
            print(
                f"Piper comparison requires {PIPER_COMPARISON_MODEL}; got: {model_path}",
                file=sys.stderr,
            )
            return 2
        if not model_path.is_file():
            print(f"Piper model not found: {model_path}", file=sys.stderr)
            return 2

        voice = None
        if not args.dry_run:
            try:
                voice = load_piper_voice(model_path)
            except Exception as exc:
                print(f"Piper model could not be loaded: {exc}", file=sys.stderr)
                return 2

        print(f"Level 1b Piper comparison: {len(targets)} item(s).\n")
        for item, spoken in targets:
            for variant in comparison_variants(item):
                print(
                    f"  {item} [{variant.name}] rate={variant.rate} "
                    f"noise={variant.noise_scale}/{variant.noise_w_scale} "
                    f"warmth={'on' if variant.warmth else 'off'} "
                    f"padding={variant.padding_ms}ms"
                )
                if voice is not None:
                    try:
                        play_piper_variant(voice, spoken, variant)
                    except Exception as exc:
                        print(f"Comparison failed for {item} [{variant.name}]: {exc}", file=sys.stderr)
                        return 1
                    time.sleep(args.gap)
        return 0

    tts = None
    if not args.dry_run:
        tts = build_tts(
            engine_name=args.engine,
            config=TTSConfig(rate=args.rate, piper_model=args.piper_model),
        )

    print(f"Level {args.level}: {len(items)} item(s). "
          f"Phonics overrides {'ACTIVE (tier 1)' if level_overrides else 'INACTIVE (tier 2+)'}.\n")

    for item in items:
        spoken = level_overrides.get(item.lower(), item)
        kind = "phoneme" if "phonemes:" in spoken else "word"
        print(f"  {item:<10} -> [{kind}] {spoken}")
        if tts is not None:
            tts.speak(spoken)
            time.sleep(args.gap)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
