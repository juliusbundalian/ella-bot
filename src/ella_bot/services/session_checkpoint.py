from __future__ import annotations

import json
import math
import os
import tempfile
import threading
from dataclasses import dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from ella_bot.core.constants import LEVEL_ORDER, TIER_SUBLEVELS
from ella_bot.services.evaluation import (
    EvaluationService,
    SubLevelResult,
    TierResult,
)
from ella_bot.services.session_manager import SessionManager
from ella_bot.utils.logging import get_logger


logger = get_logger(__name__)


@dataclass(frozen=True)
class SavedSessionSummary:
    level: str
    item_number: int
    saved_at: str
    phase: str


@dataclass(frozen=True)
class RestoredCheckpoint:
    saved_at: str
    selected_start_level: str
    phase: str
    session: SessionManager
    evaluation: EvaluationService
    latest_result_kind: str | None
    latest_result: SubLevelResult | TierResult | None


class SessionCheckpointStore:
    """Atomically persist and validate the latest stable GUI session state."""

    SCHEMA_VERSION = 1
    PHASES = {"reading", "results"}

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def summary(
        self,
        level_pools: Dict[str, List[str]],
        log_path: Path,
        pass_bar: float,
    ) -> SavedSessionSummary | None:
        restored = self.restore(level_pools, log_path, pass_bar)
        if restored is None:
            return None
        return SavedSessionSummary(
            level=restored.session.current_level,
            item_number=restored.session.current_item_number(),
            saved_at=restored.saved_at,
            phase=restored.phase,
        )

    def save(
        self,
        selected_start_level: str,
        phase: str,
        session: SessionManager,
        evaluation: EvaluationService,
        latest_result: dict | None = None,
    ) -> None:
        if selected_start_level not in LEVEL_ORDER or phase not in self.PHASES:
            raise ValueError("invalid checkpoint metadata")
        if latest_result is not None and not isinstance(latest_result, dict):
            raise ValueError("invalid checkpoint result wrapper")
        if latest_result is not None and set(latest_result) != {"kind", "payload"}:
            raise ValueError("invalid checkpoint result wrapper")

        kind = None if latest_result is None else latest_result["kind"]
        result_payload = None if latest_result is None else latest_result["payload"]
        if phase == "results" and kind not in {"sublevel", "tier"}:
            raise ValueError("results checkpoints require a supported result")
        if phase == "reading" and latest_result is not None:
            raise ValueError("reading checkpoints cannot contain a result")
        if phase == "results":
            self._restore_result(kind, result_payload)

        document = {
            "schema_version": self.SCHEMA_VERSION,
            "saved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "selected_start_level": selected_start_level,
            "phase": phase,
            "session": session.to_checkpoint(),
            "evaluation": evaluation.to_checkpoint(),
            "latest_result_kind": kind,
            "latest_result": result_payload,
        }
        encoded = json.dumps(document, indent=2, sort_keys=True).encode("utf-8")

        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary_name = tempfile.mkstemp(
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                dir=self.path.parent,
            )
            try:
                with os.fdopen(fd, "wb") as temporary:
                    temporary.write(encoded)
                    temporary.flush()
                    os.fsync(temporary.fileno())
                os.replace(temporary_name, self.path)
            except Exception:
                try:
                    Path(temporary_name).unlink()
                except FileNotFoundError:
                    pass
                raise

    def restore(
        self,
        level_pools: Dict[str, List[str]],
        log_path: Path,
        pass_bar: float,
    ) -> RestoredCheckpoint | None:
        document = self._read_valid_document()
        if document is None:
            return None
        try:
            session = SessionManager.from_checkpoint(level_pools, document["session"])
            evaluation = EvaluationService.from_checkpoint(
                log_path,
                pass_bar,
                document["evaluation"],
            )
            kind = document["latest_result_kind"]
            result = self._restore_result(kind, document["latest_result"])
            if document["phase"] == "results" and result is None:
                raise ValueError("results checkpoint has no result")
            if document["phase"] == "reading" and result is not None:
                raise ValueError("reading checkpoint contains a result")
        except ValueError as exc:
            self._archive_invalid(exc)
            return None

        return RestoredCheckpoint(
            saved_at=document["saved_at"],
            selected_start_level=document["selected_start_level"],
            phase=document["phase"],
            session=session,
            evaluation=evaluation,
            latest_result_kind=kind,
            latest_result=result,
        )

    def clear(self) -> None:
        with self._lock:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass

    def _read_valid_document(self) -> dict | None:
        if not self.path.exists():
            return None
        try:
            with self.path.open("r", encoding="utf-8") as source:
                document = json.load(source)
            expected_keys = {
                "schema_version",
                "saved_at",
                "selected_start_level",
                "phase",
                "session",
                "evaluation",
                "latest_result_kind",
                "latest_result",
            }
            if not isinstance(document, dict) or set(document) != expected_keys:
                raise ValueError("invalid checkpoint fields")
            if document["schema_version"] != self.SCHEMA_VERSION:
                raise ValueError("unsupported checkpoint schema")
            if document["selected_start_level"] not in LEVEL_ORDER:
                raise ValueError("invalid selected start level")
            if document["phase"] not in self.PHASES:
                raise ValueError("invalid checkpoint phase")
            saved_at = datetime.fromisoformat(document["saved_at"])
            if saved_at.utcoffset() is None:
                raise ValueError("checkpoint timestamp must include a timezone")
            if not isinstance(document["session"], dict):
                raise ValueError("invalid session payload")
            if not isinstance(document["evaluation"], dict):
                raise ValueError("invalid evaluation payload")
            return document
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self._archive_invalid(exc)
            return None

    def _archive_invalid(self, reason: Exception) -> None:
        logger.warning("Ignoring invalid session checkpoint: %s", reason)
        if not self.path.exists():
            return
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
        invalid_path = self.path.with_name(f"{self.path.name}.invalid-{timestamp}")
        try:
            os.replace(self.path, invalid_path)
        except OSError as exc:
            logger.warning("Unable to archive invalid checkpoint: %s", exc)

    @staticmethod
    def _restore_result(
        kind: str | None,
        payload: dict | None,
    ) -> SubLevelResult | TierResult | None:
        if kind is None and payload is None:
            return None
        result_types = {"sublevel": SubLevelResult, "tier": TierResult}
        result_type = result_types.get(kind)
        if result_type is None or not isinstance(payload, dict):
            raise ValueError("invalid checkpoint result")
        expected_fields = {field.name for field in fields(result_type)}
        if set(payload) != expected_fields:
            raise ValueError("invalid checkpoint result fields")
        try:
            result = result_type(**payload)
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid checkpoint result values") from exc
        if (
            isinstance(result.tier, bool)
            or not isinstance(result.tier, int)
            or result.tier not in TIER_SUBLEVELS
        ):
            raise ValueError("invalid checkpoint result tier")
        if not isinstance(result.passed, bool):
            raise ValueError("invalid checkpoint result pass flag")
        if kind == "sublevel" and result.level not in LEVEL_ORDER:
            raise ValueError("invalid checkpoint result level")
        if not isinstance(result.rating, str):
            raise ValueError("invalid checkpoint result rating")
        if not isinstance(result.fluency, (int, float)) or isinstance(result.fluency, bool):
            raise ValueError("invalid checkpoint result fluency")
        if not math.isfinite(float(result.fluency)):
            raise ValueError("checkpoint result fluency must be finite")
        for count in (result.items_total, result.first_try_correct):
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValueError("invalid checkpoint result item count")
        if result.first_try_correct > result.items_total:
            raise ValueError("invalid checkpoint result first-try count")
        if kind == "sublevel":
            if (
                isinstance(result.attempts, bool)
                or not isinstance(result.attempts, int)
                or result.attempts < result.items_total
            ):
                raise ValueError("invalid checkpoint result attempt count")
        return result
