from __future__ import annotations

from typing import Dict, List

LEVEL_ORDER: List[str] = [
    "1a", "1b", "1c", "1d", "1e", "1f", "1g",
    "2a", "2b", "2c", "2d", "3", "4",
]

LEVEL_THRESHOLDS: Dict[str, float] = {
    "1a": 0.85,
    "1b": 0.85,
    "1c": 0.85,
    "1d": 0.85,
    "1e": 0.85,
    "1f": 0.85,
    "1g": 0.85,
    "2a": 0.88,
    "2b": 0.90,
    "2c": 0.92,
    "2d": 0.95,
    "3": 1.01,
    "4": 1.01,
}

TIER_SUBLEVELS: Dict[int, List[str]] = {
    1: ["1a", "1b", "1c", "1d", "1e", "1f", "1g"],
    2: ["2a", "2b", "2c", "2d"],
    3: ["3"],
    4: ["4"],
}

TIER2_PLUS_SESSION_LIMIT: int = 10


def tier_of(level: str) -> int:
    """Return the tier number (1-4) a sub-level belongs to, or 0 if unknown."""
    for tier, subs in TIER_SUBLEVELS.items():
        if level in subs:
            return tier
    return 0


def max_attempts_for_level(level: str) -> int:
    """Return the maximum attempts allowed per item for the given level."""
    return 1 if tier_of(level) == 1 else 3


def get_level1_sound_and_word(item: str) -> tuple[str, str]:
    """Return (sound_target, display_word) for a Level 1 item.

    If item is formatted as 'sound (word)' e.g. 'ai (main)', returns ('ai', 'main').
    Otherwise returns (item, item).
    """
    item_clean = item.strip()
    if "(" in item_clean and ")" in item_clean:
        sound = item_clean.split("(")[0].strip()
        open_idx = item_clean.find("(")
        close_idx = item_clean.find(")", open_idx)
        word = item_clean[open_idx + 1 : close_idx].strip()
        return sound, word if word else sound
    return item_clean, item_clean

