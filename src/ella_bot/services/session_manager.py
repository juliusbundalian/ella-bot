from __future__ import annotations

import json
import random
from typing import Dict, List

from ella_bot.core.constants import LEVEL_ORDER, LEVEL_THRESHOLDS
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
        with open(resolve_config_path("level_pools.json"), "r") as f:
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

    def advance_to_higher_stage(self) -> bool:
        idx = self.level_order.index(self.current_level)
        if idx + 1 >= len(self.level_order):
            return False
        self.current_level = self.level_order[idx + 1]
        self.reset_current_level()
        return True

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
