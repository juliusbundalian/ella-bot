from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Dict, List

from ella_bot.core.constants import LEVEL_ORDER, LEVEL_THRESHOLDS, TIER_SUBLEVELS, tier_of
from ella_bot.utils.file_utils import resolve_config_path


class SessionManager:
    """Owns level progression, sentence selection, and announcement text."""

    def __init__(self, level_pools: Dict[str, List[str]], start_level: str = "1a") -> None:
        self.level_order = list(LEVEL_ORDER)
        self.level_thresholds = dict(LEVEL_THRESHOLDS)
        self.level_pools = level_pools

        if start_level not in self.level_order:
            start_level = "1a"
        self.current_level = start_level
        self.level_indices: Dict[str, int] = {level: 0 for level in self.level_order}
        self.expected_sentence = self.pick_sentence_for_level(self.current_level)
        self.completed_in_level = 0
        self.level_goal = len(self.level_pools.get(self.current_level, []))

    @classmethod
    def from_config_file(
        cls,
        start_level: str = "1a",
        hard_sentences: List[str] | None = None,
        seed_sentence: str = "",
    ) -> "SessionManager":
        with open(resolve_config_path("level_pools.json"), "r", encoding="utf-8") as f:
            level_pools = json.load(f)
        if hard_sentences:
            level_pools["hard"] = hard_sentences
        elif seed_sentence and seed_sentence not in level_pools["hard"]:
            level_pools["hard"] = [seed_sentence]
        return cls(level_pools=level_pools, start_level=start_level)

    def current_item_number(self) -> int:
        return self.level_indices.get(self.current_level, 0) + 1

    def pick_sentence_for_level(self, level: str) -> str:
        pool = self.level_pools.get(level, [])
        if not pool:
            return ""
        if level == "hard":
            return random.choice(pool)
        index = self.level_indices.get(level, 0)
        index = max(0, min(index, len(pool) - 1))
        return pool[index]

    def display_level_name(self) -> str:
        return self.current_level.replace("-", " ").title()

    def current_pool_size(self) -> int:
        return len(self.level_pools.get(self.current_level, []))

    def advance_to_next_sentence(self) -> None:
        if self.current_level == "hard":
            self.expected_sentence = self.pick_sentence_for_level(self.current_level)
            return
        pool = self.level_pools.get(self.current_level, [])
        if not pool:
            self.expected_sentence = ""
            return
        next_index = min(self.level_indices.get(self.current_level, 0) + 1, len(pool) - 1)
        self.level_indices[self.current_level] = next_index
        self.expected_sentence = pool[next_index]

    def reset_current_level(self) -> None:
        self.completed_in_level = 0
        self.level_goal = self.current_pool_size()
        self.level_indices[self.current_level] = 0
        self.expected_sentence = self.pick_sentence_for_level(self.current_level)

    def reset_to_start(self) -> None:
        self.current_level = "1a"
        self.level_indices = {level: 0 for level in self.level_order}
        self.completed_in_level = 0
        self.level_goal = len(self.level_pools.get("1a", []))
        self.expected_sentence = self.pick_sentence_for_level("1a")

    def advance_to_higher_stage(self) -> bool:
        idx = self.level_order.index(self.current_level)
        if idx + 1 >= len(self.level_order):
            return False
        self.current_level = self.level_order[idx + 1]
        self.reset_current_level()
        return True

    def tier_of(self, level: str) -> int:
        return tier_of(level)

    def is_last_sublevel_of_tier(self, level: str) -> bool:
        subs = TIER_SUBLEVELS.get(tier_of(level), [])
        return bool(subs) and level == subs[-1]

    def is_last_tier(self, tier: int) -> bool:
        return tier == max(TIER_SUBLEVELS)

    def current_sublevel_complete(self) -> bool:
        if self.current_level == "hard":
            return False
        return self.completed_in_level >= self.level_goal

    def retry_sublevel(self, level: str) -> None:
        self.current_level = level
        self.reset_current_level()

    def retry_tier(self, tier: int) -> None:
        subs = TIER_SUBLEVELS.get(tier, [])
        for sub in subs:
            self.level_indices[sub] = 0
        if subs:
            self.current_level = subs[0]
        self.completed_in_level = 0
        self.level_goal = self.current_pool_size()
        self.expected_sentence = self.pick_sentence_for_level(self.current_level)

    def try_level_up(self, accuracy: float) -> bool:
        if self.current_level == "hard":
            return False
        threshold = self.level_thresholds.get(self.current_level, 1.0)
        if self.completed_in_level < self.level_goal:
            return False
        if accuracy < threshold:
            return False
        return self.advance_to_higher_stage()

    def build_start_announcement(self) -> str:
        target_sentence = self.expected_sentence.strip() or "the next item"
        level = self.display_level_name()
        item = self.current_item_number()
        intros = [
            f"Alright! You're on the {level} level, item {item}. When you're ready, please read, {target_sentence}.",
            f"Okay, let's do this! {level} level, item {item}. Go ahead and read, {target_sentence}.",
            f"Here we go! Item {item} on the {level} level. Please read out loud, {target_sentence}.",
        ]
        return random.choice(intros)


def get_resume_level(log_path: Path, default_level: str = "1a") -> str:
    """Read the JSONL sessions log file and determine the next incomplete level to resume from."""
    if not log_path or not log_path.exists():
        return default_level

    last_passed_level = None
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if data.get("type") == "sublevel" and data.get("passed") is True:
                        lvl = data.get("level")
                        if lvl in LEVEL_ORDER:
                            last_passed_level = lvl
                except Exception:
                    continue
    except Exception:
        pass

    if last_passed_level is None:
        return default_level

    # Find the next level in LEVEL_ORDER
    try:
        idx = LEVEL_ORDER.index(last_passed_level)
        if idx + 1 < len(LEVEL_ORDER):
            return LEVEL_ORDER[idx + 1]
        else:
            # If they completed the very last level, stay on the last level
            return last_passed_level
    except ValueError:
        return default_level
