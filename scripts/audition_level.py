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

# Make src/ importable when run from the repo root.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ella_bot.speech.tts.base import TTSConfig  # noqa: E402
from ella_bot.speech.tts.factory import build_tts  # noqa: E402
from ella_bot.validation.feedback import overrides_for_level  # noqa: E402


STOP_CONSONANTS = frozenset("bcdgjkpt")
CONTINUOUS_CONSONANTS = frozenset("fhlmnrsvwyz")
SEQUENCE_CONSONANTS = frozenset("qx")


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


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("level", help="Level/sub-level to audition, e.g. 1c, 2a, 3")
    p.add_argument("--only", default=None, help="Only speak items containing this substring")
    p.add_argument("--engine", default="piper", help="TTS engine (default: piper)")
    p.add_argument(
        "--rate",
        type=int,
        default=190,
        help="Speech rate / words-per-minute. Lower is slower (default: 150; the app uses 340)",
    )
    p.add_argument(
        "--gap",
        type=float,
        default=1.0,
        help="Seconds of silence to pause between items (default: 1.0)",
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
    p.add_argument("--dry-run", action="store_true", help="Print what would be spoken without playing audio")
    return p.parse_args()


def main() -> int:
    args = parse_args()

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
