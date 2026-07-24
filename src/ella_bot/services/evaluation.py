from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from ella_bot.core.constants import LEVEL_ORDER, TIER_SUBLEVELS, tier_of


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


def _restore_dataclass(cls, payload: object):
    if not isinstance(payload, dict):
        raise ValueError(f"invalid {cls.__name__} checkpoint")
    expected = {field.name for field in fields(cls)}
    if set(payload) != expected:
        raise ValueError(f"invalid {cls.__name__} fields")
    try:
        return cls(**payload)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {cls.__name__} values") from exc


def _validate_attempt(level: str, attempt: ItemAttempt) -> None:
    if level not in LEVEL_ORDER:
        raise ValueError("invalid attempt level")
    if isinstance(attempt.item, bool) or not isinstance(attempt.item, int) or attempt.item < 1:
        raise ValueError("invalid attempt item")
    if not all(
        isinstance(value, str)
        for value in (attempt.expected, attempt.heard, attempt.ts)
    ):
        raise ValueError("invalid attempt text")
    if not isinstance(attempt.correct, bool):
        raise ValueError("invalid attempt correctness")
    for value in (attempt.accuracy, attempt.wer):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError("invalid attempt score")
        if not math.isfinite(float(value)):
            raise ValueError("attempt score must be finite")


def _validate_tier_result(tier: int, result: TierResult) -> None:
    if tier not in TIER_SUBLEVELS or result.tier != tier:
        raise ValueError("invalid tier result")
    if not isinstance(result.fluency, (int, float)) or isinstance(result.fluency, bool):
        raise ValueError("invalid tier fluency")
    if not math.isfinite(float(result.fluency)):
        raise ValueError("tier fluency must be finite")
    if not isinstance(result.rating, str) or not isinstance(result.passed, bool):
        raise ValueError("invalid tier rating")
    for count in (result.items_total, result.first_try_correct):
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("invalid tier item count")
    if result.first_try_correct > result.items_total:
        raise ValueError("invalid tier first-try count")


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

    def to_checkpoint(self) -> dict:
        """Return active scoring state needed to resume without losing history."""
        return {
            "session_id": self.session_id,
            "started_at": self._started.isoformat(),
            "attempts": {
                level: [asdict(attempt) for attempt in attempts]
                for level, attempts in self._attempts.items()
            },
            "tier_results": {
                str(tier): asdict(result)
                for tier, result in self._tier_results.items()
            },
        }

    @classmethod
    def from_checkpoint(
        cls,
        log_path: Path,
        pass_bar: float,
        payload: object,
    ) -> "EvaluationService":
        """Restore and validate active scoring state from a checkpoint."""
        expected_fields = {"session_id", "started_at", "attempts", "tier_results"}
        if not isinstance(payload, dict):
            raise ValueError("evaluation checkpoint must be an object")
        if set(payload) != expected_fields:
            raise ValueError("invalid evaluation checkpoint fields")
        if not isinstance(payload["session_id"], str):
            raise ValueError("invalid session id")
        try:
            started = datetime.fromisoformat(payload["started_at"])
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid evaluation start time") from exc
        if not isinstance(payload["attempts"], dict) or not isinstance(
            payload["tier_results"], dict
        ):
            raise ValueError("invalid evaluation collections")

        restored = cls(log_path=log_path, pass_bar=pass_bar)
        restored.session_id = payload["session_id"]
        restored._started = started
        restored._attempts = {}
        for level, attempts in payload["attempts"].items():
            if not isinstance(level, str) or not isinstance(attempts, list):
                raise ValueError("invalid attempt group")
            restored._attempts[level] = []
            for attempt_payload in attempts:
                attempt = _restore_dataclass(ItemAttempt, attempt_payload)
                _validate_attempt(level, attempt)
                restored._attempts[level].append(attempt)

        restored._tier_results = {}
        for tier_text, result_payload in payload["tier_results"].items():
            try:
                tier = int(tier_text)
            except (TypeError, ValueError) as exc:
                raise ValueError("invalid tier key") from exc
            if str(tier) != tier_text:
                raise ValueError("invalid tier key")
            tier_result = _restore_dataclass(TierResult, result_payload)
            _validate_tier_result(tier, tier_result)
            restored._tier_results[tier] = tier_result
        return restored

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
            best_by_item: Dict[int, float] = {}
            for a in atts:
                if a.item not in first_by_item:
                    first_by_item[a.item] = a.correct
                if a.item not in best_by_item or a.accuracy > best_by_item[a.item]:
                    best_by_item[a.item] = a.accuracy

            accs.extend(best_by_item.values())
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
        if self.log_path and self.log_path.exists():
            try:
                self.log_path.unlink()
            except Exception:
                try:
                    with open(self.log_path, "w", encoding="utf-8") as f:
                        pass
                except Exception:
                    pass
