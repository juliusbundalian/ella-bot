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
