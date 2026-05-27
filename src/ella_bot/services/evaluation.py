from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from ella_bot.core.constants import TIER_SUBLEVELS, tier_of


@dataclass
class ItemAttempt:
    item: int
    expected: str
    heard: str
    accuracy: float
    wer: float
    correct: bool
    ts: str


@dataclass
class SubLevelResult:
    tier: int
    level: str
    items_total: int
    first_try_correct: int
    attempts: int
    fluency: float
    rating: str
    passed: bool


@dataclass
class TierResult:
    tier: int
    fluency: float
    rating: str
    items_total: int
    first_try_correct: int
    passed: bool


@dataclass
class CumulativeResult:
    overall_fluency: float
    overall_rating: str
    items_total: int
    first_try_correct: int
    tiers: List[TierResult]
    duration_s: float


def rating_for(fluency: float) -> str:
    pct = fluency * 100
    if pct >= 90:
        return "A"
    if pct >= 80:
        return "B"
    if pct >= 70:
        return "C"
    if pct >= 60:
        return "D"
    return "F"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class EvaluationService:
    """Accumulates reading attempts, scores them, and appends JSONL records.

    No pygame dependency. Attempts are kept in memory keyed by level so a
    Retry can drop a unit's attempts; already-written JSONL records are
    append-only history and are never rewritten.
    """

    def __init__(self, log_path: Path, pass_bar: float = 0.70) -> None:
        self.log_path = Path(log_path)
        self.pass_bar = pass_bar
        self.session_id = _now()
        self._started = datetime.now()
        self._attempts: Dict[str, List[ItemAttempt]] = {}
        self._tier_results: Dict[int, TierResult] = {}

    def record_attempt(self, level, item, expected, heard, accuracy, wer, correct) -> None:
        self._attempts.setdefault(level, []).append(
            ItemAttempt(
                item=item, expected=expected, heard=heard,
                accuracy=accuracy, wer=wer, correct=correct, ts=_now(),
            )
        )

    def _aggregate(self, levels):
        """Return (items_total, first_try_correct, fluency, attempts) over levels.

        Item numbers restart per level, so distinct items are counted per
        level and summed (avoids collapsing "item 1" across sub-levels).
        """
        items_total = first_try = attempts = 0
        accs: List[float] = []
        for level in levels:
            atts = self._attempts.get(level, [])
            if not atts:
                continue
            first_by_item: Dict[int, bool] = {}
            for a in atts:
                if a.item not in first_by_item:
                    first_by_item[a.item] = a.correct
                accs.append(a.accuracy)
            items_total += len(first_by_item)
            first_try += sum(1 for ok in first_by_item.values() if ok)
            attempts += len(atts)
        fluency = sum(accs) / len(accs) if accs else 0.0
        return items_total, first_try, fluency, attempts

    def _append(self, record: dict) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
            f.flush()

    def finish_sublevel(self, level: str) -> SubLevelResult:
        items_total, first_try, fluency, attempts = self._aggregate([level])
        result = SubLevelResult(
            tier=tier_of(level), level=level, items_total=items_total,
            first_try_correct=first_try, attempts=attempts,
            fluency=fluency, rating=rating_for(fluency), passed=fluency >= self.pass_bar,
        )
        self._append({
            "type": "sublevel", "session_id": self.session_id,
            "tier": result.tier, "level": result.level,
            "items_total": result.items_total, "first_try_correct": result.first_try_correct,
            "attempts": result.attempts, "fluency": round(result.fluency, 4),
            "rating": result.rating, "passed": result.passed,
            "items": [asdict(a) for a in self._attempts.get(level, [])],
            "ts": _now(),
        })
        return result

    def finish_tier(self, tier: int) -> TierResult:
        levels = TIER_SUBLEVELS.get(tier, [])
        items_total, first_try, fluency, _ = self._aggregate(levels)
        result = TierResult(
            tier=tier, fluency=fluency, rating=rating_for(fluency),
            items_total=items_total, first_try_correct=first_try,
            passed=fluency >= self.pass_bar,
        )
        self._tier_results[tier] = result
        self._append({
            "type": "tier", "session_id": self.session_id, "tier": tier,
            "fluency": round(result.fluency, 4), "rating": result.rating,
            "items_total": result.items_total, "first_try_correct": result.first_try_correct,
            "passed": result.passed, "ts": _now(),
        })
        return result

    def finish_session(self) -> CumulativeResult:
        items_total, first_try, fluency, _ = self._aggregate(list(self._attempts.keys()))
        tiers = [self._tier_results[t] for t in sorted(self._tier_results)]
        result = CumulativeResult(
            overall_fluency=fluency, overall_rating=rating_for(fluency),
            items_total=items_total, first_try_correct=first_try,
            tiers=tiers, duration_s=(datetime.now() - self._started).total_seconds(),
        )
        self._append({
            "type": "session", "session_id": self.session_id,
            "overall_fluency": round(result.overall_fluency, 4),
            "overall_rating": result.overall_rating,
            "items_total": result.items_total, "first_try_correct": result.first_try_correct,
            "tiers": [asdict(t) for t in tiers],
            "started_ts": self._started.isoformat(timespec="seconds"),
            "ended_ts": _now(), "duration_s": round(result.duration_s, 1), "ts": _now(),
        })
        return result

    def reset_sublevel(self, level: str) -> None:
        self._attempts[level] = []

    def reset_tier(self, tier: int) -> None:
        for level in TIER_SUBLEVELS.get(tier, []):
            self._attempts[level] = []
        self._tier_results.pop(tier, None)

    def reset_all(self) -> None:
        self._attempts.clear()
        self._tier_results.clear()
