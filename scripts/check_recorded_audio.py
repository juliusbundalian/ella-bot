#!/usr/bin/env python3
"""Check that every configured Level 1 and 2 item resolves to a recording."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ella_bot.core.constants import get_level1_sound_and_word, tier_of
from ella_bot.services.sound_effects import resolve_level1_playback


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config/level_pools.json")
    args = parser.parse_args(argv)
    with args.config.open(encoding="utf-8") as source:
        pools = json.load(source)

    checked = 0
    missing = []
    for level, items in pools.items():
        tier = tier_of(level)
        if tier not in (1, 2):
            continue
        for item in items:
            checked += 1
            target = get_level1_sound_and_word(item)[0] if tier == 1 else item.strip()
            path = resolve_level1_playback(level, target)
            if path is None or not path.is_file():
                missing.append((level, item))

    for level, item in missing:
        print(f"Missing recording for {level.upper()}: {item}")
    print(f"Checked {checked} items; {len(missing)} missing recording(s).")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
