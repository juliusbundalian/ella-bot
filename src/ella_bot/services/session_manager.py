from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Dict, List

from ella_bot.core.constants import (
    LEVEL_ORDER, LEVEL_THRESHOLDS, TIER_SUBLEVELS,
    TIER2_PLUS_SESSION_LIMIT, tier_of,
)
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
        self._session_pools: Dict[str, List[str]] = {}
        self._session_pools[self.current_level] = self._build_session_pool(self.current_level)
        self.expected_sentence = self.pick_sentence_for_level(self.current_level)
        self.completed_in_level = 0
        self.level_goal = len(self._session_pools.get(self.current_level, []))
        self.last_announced_sentence = ""

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

    def to_checkpoint(self) -> dict:
        """Return all mutable reading-session state needed for an exact resume."""
        return {
            "current_level": self.current_level,
            "level_indices": dict(self.level_indices),
            "session_pools": {
                level: list(pool) for level, pool in self._session_pools.items()
            },
            "expected_sentence": self.expected_sentence,
            "completed_in_level": self.completed_in_level,
            "level_goal": self.level_goal,
            "last_announced_sentence": self.last_announced_sentence,
        }

    @classmethod
    def from_checkpoint(
        cls,
        level_pools: Dict[str, List[str]],
        payload: object,
    ) -> "SessionManager":
        """Restore an exact reading session after validating persisted state."""
        expected_fields = {
            "current_level",
            "level_indices",
            "session_pools",
            "expected_sentence",
            "completed_in_level",
            "level_goal",
            "last_announced_sentence",
        }
        if not isinstance(payload, dict) or set(payload) != expected_fields:
            raise ValueError("Invalid session checkpoint fields")

        current_level = payload["current_level"]
        if current_level not in LEVEL_ORDER or current_level not in level_pools:
            raise ValueError("Invalid checkpoint level")

        raw_indices = payload["level_indices"]
        if not isinstance(raw_indices, dict) or any(
            level not in LEVEL_ORDER
            or isinstance(index, bool)
            or not isinstance(index, int)
            or index < 0
            for level, index in raw_indices.items()
        ):
            raise ValueError("Invalid checkpoint level indices")
        level_indices = {level: 0 for level in LEVEL_ORDER}
        level_indices.update(raw_indices)

        raw_session_pools = payload["session_pools"]
        if not isinstance(raw_session_pools, dict):
            raise ValueError("Invalid checkpoint session pools")
        session_pools: Dict[str, List[str]] = {}
        for level, pool in raw_session_pools.items():
            configured_pool = level_pools.get(level)
            if (
                level not in LEVEL_ORDER
                or configured_pool is None
                or not isinstance(pool, list)
                or any(not isinstance(item, str) or item not in configured_pool for item in pool)
            ):
                raise ValueError("Invalid checkpoint session pool")
            session_pools[level] = list(pool)

        current_pool = session_pools.get(current_level)
        current_index = level_indices[current_level]
        if not current_pool or current_index >= len(current_pool):
            raise ValueError("Checkpoint item is outside the current pool")

        expected_sentence = payload["expected_sentence"]
        if not isinstance(expected_sentence, str) or expected_sentence != current_pool[current_index]:
            raise ValueError("Checkpoint sentence does not match its item position")

        completed = payload["completed_in_level"]
        level_goal = payload["level_goal"]
        if (
            isinstance(completed, bool)
            or not isinstance(completed, int)
            or completed < 0
            or isinstance(level_goal, bool)
            or not isinstance(level_goal, int)
            or level_goal != len(current_pool)
            or completed > level_goal
        ):
            raise ValueError("Invalid checkpoint level progress")

        last_announced = payload["last_announced_sentence"]
        if not isinstance(last_announced, str):
            raise ValueError("Invalid checkpoint announcement")

        restored = cls(level_pools=level_pools, start_level=current_level)
        restored.level_indices = level_indices
        restored._session_pools = session_pools
        restored.expected_sentence = expected_sentence
        restored.completed_in_level = completed
        restored.level_goal = level_goal
        restored.last_announced_sentence = last_announced
        return restored

    def _build_session_pool(self, level: str) -> List[str]:
        pool = self.level_pools.get(level, [])
        if tier_of(level) in (1, 2):
            return list(pool)
        if len(pool) <= TIER2_PLUS_SESSION_LIMIT:
            return list(pool)
        return random.sample(pool, TIER2_PLUS_SESSION_LIMIT)

    def current_item_number(self) -> int:
        return self.level_indices.get(self.current_level, 0) + 1

    def pick_sentence_for_level(self, level: str) -> str:
        if level == "hard":
            pool = self.level_pools.get(level, [])
            return random.choice(pool) if pool else ""
        pool = self._session_pools.get(level, [])
        if not pool:
            return ""
        index = self.level_indices.get(level, 0)
        index = max(0, min(index, len(pool) - 1))
        return pool[index]

    def display_level_name(self) -> str:
        return self.current_level.replace("-", " ").title()

    def current_pool_size(self) -> int:
        return len(self._session_pools.get(self.current_level, []))

    def advance_to_next_sentence(self) -> None:
        if self.current_level == "hard":
            self.expected_sentence = self.pick_sentence_for_level(self.current_level)
            return
        pool = self._session_pools.get(self.current_level, [])
        if not pool:
            self.expected_sentence = ""
            return
        next_index = min(self.level_indices.get(self.current_level, 0) + 1, len(pool) - 1)
        self.level_indices[self.current_level] = next_index
        self.expected_sentence = pool[next_index]

    def reset_current_level(self) -> None:
        self._session_pools[self.current_level] = self._build_session_pool(self.current_level)
        self.completed_in_level = 0
        self.level_goal = self.current_pool_size()
        self.level_indices[self.current_level] = 0
        self.expected_sentence = self.pick_sentence_for_level(self.current_level)
        self.last_announced_sentence = ""

    def reset_to_start(self) -> None:
        self.current_level = "1a"
        self.level_indices = {level: 0 for level in self.level_order}
        self.completed_in_level = 0
        self._session_pools["1a"] = self._build_session_pool("1a")
        self.level_goal = len(self._session_pools.get("1a", []))
        self.expected_sentence = self.pick_sentence_for_level("1a")
        self.last_announced_sentence = ""

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
            self._session_pools[subs[0]] = self._build_session_pool(subs[0])
        self.completed_in_level = 0
        self.level_goal = self.current_pool_size()
        self.expected_sentence = self.pick_sentence_for_level(self.current_level)
        self.last_announced_sentence = ""

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
        clean_target = target_sentence.rstrip(".!?")
        level = self.display_level_name()
        item = self.current_item_number()
        intros = [
            f"Alright! You're on level {level}, item {item}. When you're ready, please read, {clean_target}.",
            f"Okay, let's do this! Level {level}, item {item}. Go ahead and read, {clean_target}.",
            f"Here we go! Item {item} on level {level}. Please read out loud, {clean_target}.",
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
