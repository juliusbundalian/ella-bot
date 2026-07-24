# Level Selection and Exact Session Resume Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route the GUI Start button through an all-unlocked level picker and support automatic, exact recovery of the last stable reading or results state from an atomic checkpoint.

**Architecture:** Keep `sessions.jsonl` as append-only evaluation history and add a versioned `active_session.json` managed by a dedicated checkpoint store. `SessionManager` and `EvaluationService` serialize their own state, `EllaGUIApp` orchestrates checkpoint operations, and scenes request high-level actions without accessing checkpoint files.

**Tech Stack:** Python 3.9+, dataclasses, JSON, atomic filesystem replacement, pygame-ce, pytest.

## Global Constraints

- Every entry in `LEVEL_ORDER` must appear enabled on the level-selection page.
- A saved session must resume the exact stable reading item, attempts, randomized pool order, or pending results screen.
- The old checkpoint remains intact until a new level is confirmed and its replacement checkpoint saves successfully.
- Save after every completed scored or silent attempt, never during an in-flight attempt mutation.
- Preserve existing upward progression and pass gates from the selected starting level.
- Keep `sessions.jsonl` as append-only grading history; starting a new session must not erase it.
- Settings Reset Progress retains its existing full-reset meaning and clears both history and the active checkpoint.
- No cloud sync, multiple profiles, multiple save slots, level locking, grading changes, or historical-log migration.

---

### Task 1: Serialize and Restore `SessionManager`

**Files:**
- Modify: `src/ella_bot/services/session_manager.py:12-166`
- Test: `tests/test_session_manager.py`

**Interfaces:**
- Consumes: existing `SessionManager.level_pools`, `LEVEL_ORDER`, and session progression fields.
- Produces: `SessionManager.to_checkpoint() -> dict` and `SessionManager.from_checkpoint(level_pools: Dict[str, List[str]], payload: dict) -> SessionManager`.

- [ ] **Step 1: Write failing exact-state round-trip tests**

Append tests that prove ordinary and randomized pools retain identity and order:

```python
def test_checkpoint_round_trip_restores_exact_item_and_progress():
    pools = {"1a": ["a", "e", "i"], "1b": ["b"]}
    original = SessionManager(level_pools=pools, start_level="1a")
    original.advance_to_next_sentence()
    original.completed_in_level = 1
    original.last_announced_sentence = "e"

    restored = SessionManager.from_checkpoint(pools, original.to_checkpoint())

    assert restored.current_level == "1a"
    assert restored.current_item_number() == 2
    assert restored.expected_sentence == "e"
    assert restored.completed_in_level == 1
    assert restored.level_goal == 3
    assert restored.last_announced_sentence == "e"


def test_checkpoint_round_trip_preserves_randomized_pool_order():
    pools = _tier2_pools(40)
    original = SessionManager(level_pools=pools, start_level="2a")
    original.advance_to_next_sentence()
    original.advance_to_next_sentence()
    saved_order = list(original._session_pools["2a"])

    restored = SessionManager.from_checkpoint(pools, original.to_checkpoint())

    assert restored._session_pools["2a"] == saved_order
    assert restored.current_item_number() == 3
    assert restored.expected_sentence == saved_order[2]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.update(current_level="missing"),
        lambda payload: payload["level_indices"].update({"1a": -1}),
        lambda payload: payload.update(completed_in_level=-1),
        lambda payload: payload.update(expected_sentence="not the current item"),
    ],
)
def test_checkpoint_restore_rejects_invalid_session_state(mutate):
    pools = {"1a": ["a", "e"]}
    payload = SessionManager(level_pools=pools, start_level="1a").to_checkpoint()
    mutate(payload)

    with pytest.raises(ValueError):
        SessionManager.from_checkpoint(pools, payload)
```

- [ ] **Step 2: Run the new tests and verify RED**

Run:

```bash
.venv/bin/pytest -q tests/test_session_manager.py -k checkpoint
```

Expected: failures reporting that `to_checkpoint` and `from_checkpoint` do not exist.

- [ ] **Step 3: Implement session serialization with semantic validation**

Add methods with this field contract:

```python
    def to_checkpoint(self) -> dict:
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
        cls, level_pools: Dict[str, List[str]], payload: dict
    ) -> "SessionManager":
        if not isinstance(payload, dict):
            raise ValueError("session checkpoint must be an object")

        current_level = payload.get("current_level")
        if current_level not in LEVEL_ORDER or current_level not in level_pools:
            raise ValueError("invalid current level")

        indices = payload.get("level_indices")
        session_pools = payload.get("session_pools")
        if not isinstance(indices, dict) or not isinstance(session_pools, dict):
            raise ValueError("invalid session collections")

        normalized_indices = {level: 0 for level in LEVEL_ORDER}
        for level, value in indices.items():
            if level not in LEVEL_ORDER or not isinstance(value, int) or value < 0:
                raise ValueError("invalid level index")
            normalized_indices[level] = value

        normalized_pools: Dict[str, List[str]] = {}
        for level, pool in session_pools.items():
            if level not in LEVEL_ORDER or not isinstance(pool, list):
                raise ValueError("invalid session pool")
            if not all(isinstance(item, str) for item in pool):
                raise ValueError("session pool items must be strings")
            if any(item not in level_pools.get(level, []) for item in pool):
                raise ValueError("session pool contains an unknown item")
            normalized_pools[level] = list(pool)

        current_pool = normalized_pools.get(current_level)
        current_index = normalized_indices[current_level]
        if not current_pool or current_index >= len(current_pool):
            raise ValueError("current item is outside the saved pool")

        expected_sentence = payload.get("expected_sentence")
        if expected_sentence != current_pool[current_index]:
            raise ValueError("expected sentence does not match the saved item")

        completed = payload.get("completed_in_level")
        level_goal = payload.get("level_goal")
        if (
            not isinstance(completed, int)
            or completed < 0
            or not isinstance(level_goal, int)
            or level_goal != len(current_pool)
            or completed > level_goal
        ):
            raise ValueError("invalid level progress")

        last_announced = payload.get("last_announced_sentence", "")
        if not isinstance(last_announced, str):
            raise ValueError("invalid announcement state")

        restored = cls(level_pools=level_pools, start_level=current_level)
        restored.level_indices = normalized_indices
        restored._session_pools = normalized_pools
        restored.expected_sentence = expected_sentence
        restored.completed_in_level = completed
        restored.level_goal = level_goal
        restored.last_announced_sentence = last_announced
        return restored
```

- [ ] **Step 4: Run all session-manager tests and verify GREEN**

Run:

```bash
.venv/bin/pytest -q tests/test_session_manager.py
```

Expected: all session-manager tests pass.

- [ ] **Step 5: Commit the session-state boundary**

```bash
git add src/ella_bot/services/session_manager.py tests/test_session_manager.py
git commit -m "feat: serialize exact reading session state" -m "Add validated SessionManager checkpoint round-trips that preserve item position, completion counts, announcements, and randomized session-pool order."
```

---

### Task 2: Serialize and Restore `EvaluationService`

**Files:**
- Modify: `src/ella_bot/services/evaluation.py:1-202`
- Test: `tests/test_evaluation.py`

**Interfaces:**
- Consumes: `ItemAttempt`, `TierResult`, configured `log_path`, and `pass_bar`.
- Produces: `EvaluationService.to_checkpoint() -> dict` and `EvaluationService.from_checkpoint(log_path: Path, pass_bar: float, payload: dict) -> EvaluationService`.

- [ ] **Step 1: Write failing evaluation round-trip tests**

```python
def test_evaluation_checkpoint_round_trip_preserves_attempts_and_identity(tmp_path):
    original = EvaluationService(tmp_path / "sessions.jsonl", pass_bar=0.70)
    original.record_attempt("2a", 1, "word", "ward", 0.5, 1.0, False)
    original.record_attempt("2a", 1, "word", "word", 1.0, 0.0, True)
    original._tier_results[1] = TierResult(1, 0.9, "A", 7, 6, True)

    restored = EvaluationService.from_checkpoint(
        tmp_path / "sessions.jsonl", 0.70, original.to_checkpoint()
    )

    assert restored.session_id == original.session_id
    assert restored._started == original._started
    assert restored._attempts == original._attempts
    assert restored._tier_results == original._tier_results


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"session_id": 3, "started_at": "bad", "attempts": {}, "tier_results": {}},
        {"session_id": "s", "started_at": "bad", "attempts": {}, "tier_results": {}},
    ],
)
def test_evaluation_checkpoint_rejects_invalid_payload(tmp_path, payload):
    with pytest.raises(ValueError):
        EvaluationService.from_checkpoint(tmp_path / "s.jsonl", 0.70, payload)
```

- [ ] **Step 2: Run the new evaluation tests and verify RED**

```bash
.venv/bin/pytest -q tests/test_evaluation.py -k checkpoint
```

Expected: failures because the checkpoint methods do not exist.

- [ ] **Step 3: Implement dataclass-backed evaluation restoration**

Add imports for `fields` and implement strict allowed-field construction:

```python
def _restore_dataclass(cls, payload: dict):
    if not isinstance(payload, dict):
        raise ValueError(f"invalid {cls.__name__} checkpoint")
    expected = {field.name for field in fields(cls)}
    if set(payload) != expected:
        raise ValueError(f"invalid {cls.__name__} fields")
    try:
        return cls(**payload)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {cls.__name__} values") from exc


    def to_checkpoint(self) -> dict:
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
        cls, log_path: Path, pass_bar: float, payload: dict
    ) -> "EvaluationService":
        if not isinstance(payload, dict):
            raise ValueError("evaluation checkpoint must be an object")
        if set(payload) != {"session_id", "started_at", "attempts", "tier_results"}:
            raise ValueError("invalid evaluation checkpoint fields")
        if not isinstance(payload["session_id"], str):
            raise ValueError("invalid session id")
        try:
            started = datetime.fromisoformat(payload["started_at"])
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid evaluation start time") from exc
        if not isinstance(payload["attempts"], dict) or not isinstance(payload["tier_results"], dict):
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
        for tier_text, result in payload["tier_results"].items():
            try:
                tier = int(tier_text)
            except (TypeError, ValueError) as exc:
                raise ValueError("invalid tier key") from exc
            tier_result = _restore_dataclass(TierResult, result)
            if tier not in TIER_SUBLEVELS or tier_result.tier != tier:
                raise ValueError("invalid tier result")
            restored._tier_results[tier] = tier_result
        return restored
```

Validate every restored attempt before assigning `_attempts`:

```python
def _validate_attempt(level: str, attempt: ItemAttempt) -> None:
    if level not in LEVEL_ORDER:
        raise ValueError("invalid attempt level")
    if not isinstance(attempt.item, int) or attempt.item < 1:
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
```

Import `math` and `LEVEL_ORDER`. Construct each `ItemAttempt`, call
`_validate_attempt(level, attempt)`, and append it only after validation.

- [ ] **Step 4: Run evaluation tests and verify GREEN**

```bash
.venv/bin/pytest -q tests/test_evaluation.py
```

Expected: all evaluation tests pass.

- [ ] **Step 5: Commit evaluation checkpoint support**

```bash
git add src/ella_bot/services/evaluation.py tests/test_evaluation.py
git commit -m "feat: serialize active evaluation state" -m "Restore evaluation identity, timing, attempts, and tier results so a resumed reading session retains exact scoring and retry history."
```

---

### Task 3: Add the Atomic Checkpoint Store

**Files:**
- Create: `src/ella_bot/services/session_checkpoint.py`
- Create: `tests/test_session_checkpoint.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: the Task 1 and Task 2 checkpoint methods, `SubLevelResult`, and `TierResult`.
- Produces: `SavedSessionSummary`, `RestoredCheckpoint`, `SessionCheckpointStore.summary()`, `save()`, `restore()`, and `clear()`.

- [ ] **Step 1: Write failing store tests**

Create tests covering missing state, round-trip state, results state, corruption, and atomic write failure:

```python
from dataclasses import asdict

import pytest

from ella_bot.services.evaluation import EvaluationService, SubLevelResult
from ella_bot.services.session_checkpoint import SessionCheckpointStore
from ella_bot.services.session_manager import SessionManager


POOLS = {"1a": ["a", "e"], "1b": ["b"]}


def _state(tmp_path):
    session = SessionManager(POOLS, "1a")
    evaluation = EvaluationService(tmp_path / "sessions.jsonl", 0.70)
    return session, evaluation


def test_missing_checkpoint_has_no_summary(tmp_path):
    store = SessionCheckpointStore(tmp_path / "active_session.json")
    assert store.summary(POOLS, tmp_path / "sessions.jsonl", 0.70) is None


def test_reading_checkpoint_round_trip(tmp_path):
    store = SessionCheckpointStore(tmp_path / "active_session.json")
    session, evaluation = _state(tmp_path)
    evaluation.record_attempt("1a", 1, "a", "a", 1.0, 0.0, True)
    session.completed_in_level = 1
    session.advance_to_next_sentence()

    store.save("1a", "reading", session, evaluation)
    restored = store.restore(POOLS, evaluation.log_path, evaluation.pass_bar)

    assert restored is not None
    assert restored.phase == "reading"
    assert restored.session.expected_sentence == "e"
    assert len(restored.evaluation._attempts["1a"]) == 1
    assert store.summary(POOLS, evaluation.log_path, evaluation.pass_bar).item_number == 2


def test_results_checkpoint_round_trip(tmp_path):
    store = SessionCheckpointStore(tmp_path / "active_session.json")
    session, evaluation = _state(tmp_path)
    result = SubLevelResult(1, "1a", 2, 2, 2, 1.0, "A", True)

    store.save(
        "1a",
        "results",
        session,
        evaluation,
        latest_result={"kind": "sublevel", "payload": asdict(result)},
    )
    restored = store.restore(POOLS, evaluation.log_path, evaluation.pass_bar)

    assert restored.phase == "results"
    assert restored.latest_result_kind == "sublevel"
    assert restored.latest_result == result


def test_corrupt_checkpoint_is_archived(tmp_path):
    path = tmp_path / "active_session.json"
    path.write_text("{broken", encoding="utf-8")
    store = SessionCheckpointStore(path)

    assert store.summary(POOLS, tmp_path / "sessions.jsonl", 0.70) is None
    assert not path.exists()
    assert len(list(tmp_path.glob("active_session.json.invalid-*"))) == 1


def test_failed_replace_preserves_previous_checkpoint(tmp_path, monkeypatch):
    path = tmp_path / "active_session.json"
    store = SessionCheckpointStore(path)
    session, evaluation = _state(tmp_path)
    store.save("1a", "reading", session, evaluation)
    original = path.read_bytes()

    def fail_replace(source, destination):
        raise OSError("disk failure")

    monkeypatch.setattr("ella_bot.services.session_checkpoint.os.replace", fail_replace)
    with pytest.raises(OSError):
        store.save("1b", "reading", SessionManager(POOLS, "1b"), evaluation)

    assert path.read_bytes() == original
```

- [ ] **Step 2: Run the store tests and verify RED**

```bash
.venv/bin/pytest -q tests/test_session_checkpoint.py
```

Expected: import failure because `session_checkpoint.py` does not exist.

- [ ] **Step 3: Implement the complete checkpoint store**

Create these public data types and methods:

```python
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
        kind = None if latest_result is None else latest_result.get("kind")
        result_payload = None if latest_result is None else latest_result.get("payload")
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
                prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
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
                log_path, pass_bar, document["evaluation"]
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
```

Implement the private validation and archival helpers explicitly:

```python
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
    def _restore_result(kind: str | None, payload: dict | None):
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
        if not isinstance(result.tier, int) or result.tier not in TIER_SUBLEVELS:
            raise ValueError("invalid checkpoint result tier")
        if not isinstance(result.passed, bool):
            raise ValueError("invalid checkpoint result pass flag")
        if kind == "sublevel" and result.level not in LEVEL_ORDER:
            raise ValueError("invalid checkpoint result level")
        return result
```

Import `fields` from `dataclasses`, the two result dataclasses from
`evaluation.py`, `LEVEL_ORDER` and `TIER_SUBLEVELS`, and the project logger.

- [ ] **Step 4: Ignore generated checkpoint artifacts**

Append:

```gitignore
# Runtime session checkpoints
/data/active_session.json
/data/active_session.json.invalid-*
/data/.active_session.json.*.tmp
```

- [ ] **Step 5: Run persistence tests and verify GREEN**

```bash
.venv/bin/pytest -q tests/test_session_manager.py tests/test_evaluation.py tests/test_session_checkpoint.py
```

Expected: all persistence tests pass.

- [ ] **Step 6: Commit atomic checkpoint storage**

```bash
git add .gitignore src/ella_bot/services/session_checkpoint.py tests/test_session_checkpoint.py
git commit -m "feat: persist active sessions atomically" -m "Add a versioned active-session store with validated reading/results recovery, corrupt-file archival, and atomic replacement that preserves the previous checkpoint on failure."
```

---

### Task 4: Add Application-Level Session Orchestration

**Files:**
- Modify: `src/ella_bot/ui/pygame_gui/app.py:1-221`
- Create: `tests/test_app_session_flow.py`

**Interfaces:**
- Consumes: `SessionCheckpointStore`, restored checkpoint objects, `SessionManager.from_config_file()`, and `EvaluationService`.
- Produces: the six app orchestration methods in the design specification and `selected_start_level: str | None`.

- [ ] **Step 1: Write failing orchestration tests**

Use a real temporary checkpoint path but mocked speech dependencies:

```python
from dataclasses import asdict
from unittest.mock import MagicMock

from ella_bot.services.evaluation import SubLevelResult
from ella_bot.ui.pygame_gui.app import EllaGUIApp
from ella_bot.ui.pygame_gui.config import GUIConfig


def _make_app(tmp_path):
    return EllaGUIApp(
        expected_sentence="",
        asr=MagicMock(),
        tts=None,
        audio_feedback=False,
        pronunciation_overrides={},
        config=GUIConfig(session_log_path=tmp_path / "sessions.jsonl"),
    )


def test_new_session_is_saved_before_live_state_is_replaced(tmp_path):
    app = _make_app(tmp_path)
    old_session = app.session

    assert app.start_new_session("2c") is True

    assert app.session is not old_session
    assert app.current_level == "2c"
    assert app.selected_start_level == "2c"
    assert app.has_saved_session() is True


def test_invalid_new_level_does_not_replace_state(tmp_path):
    app = _make_app(tmp_path)
    old_session = app.session

    assert app.start_new_session("missing") is False
    assert app.session is old_session
    assert app.has_saved_session() is False


def test_failed_new_session_save_keeps_old_state(tmp_path, monkeypatch):
    app = _make_app(tmp_path)
    old_session = app.session
    monkeypatch.setattr(app.checkpoint_store, "save", MagicMock(side_effect=OSError("full")))

    assert app.start_new_session("2a") is False
    assert app.session is old_session
    assert "could not be saved" in app.message.lower()


def test_continue_restores_reading_checkpoint(tmp_path):
    app = _make_app(tmp_path)
    app.start_new_session("1a")
    app.session.advance_to_next_sentence()
    app.save_active_session("reading")
    replacement = _make_app(tmp_path)

    assert replacement.continue_saved_session() == "reading"
    assert replacement.session.current_item_number() == 2


def test_continue_restores_pending_result(tmp_path):
    app = _make_app(tmp_path)
    app.start_new_session("1a")
    result = SubLevelResult(1, "1a", 5, 4, 6, 0.8, "B", True)
    app.save_active_session(
        "results", {"kind": "sublevel", "payload": asdict(result)}
    )
    replacement = _make_app(tmp_path)

    assert replacement.continue_saved_session() == "results"
    assert replacement.latest_result == result
    assert replacement.latest_result_kind == "sublevel"
```

- [ ] **Step 2: Run orchestration tests and verify RED**

```bash
.venv/bin/pytest -q tests/test_app_session_flow.py
```

Expected: failures because checkpoint orchestration is not initialized.

- [ ] **Step 3: Initialize checkpoint orchestration in `EllaGUIApp`**

Add these constructor fields:

```python
        self._hard_sentences = hard_sentences
        self._seed_sentence = expected_sentence
        self.selected_start_level: str | None = None
        self.checkpoint_phase: str | None = None
        self.checkpoint_latest_result: dict | None = None
        checkpoint_path = self.config.session_log_path.with_name("active_session.json")
        self.checkpoint_store = SessionCheckpointStore(checkpoint_path)
```

Add the public methods:

```python
    def has_saved_session(self) -> bool:
        return self.saved_session_summary() is not None

    def saved_session_summary(self):
        return self.checkpoint_store.summary(
            self.session.level_pools,
            self.evaluation.log_path,
            self.evaluation.pass_bar,
        )

    def start_new_session(self, level: str) -> bool:
        if level not in LEVEL_ORDER:
            return False
        candidate_session = SessionManager.from_config_file(
            start_level=level,
            hard_sentences=self._hard_sentences,
            seed_sentence=self._seed_sentence,
        )
        candidate_evaluation = EvaluationService(
            log_path=self.evaluation.log_path,
            pass_bar=self.evaluation.pass_bar,
        )
        try:
            self.checkpoint_store.save(
                level, "reading", candidate_session, candidate_evaluation
            )
        except Exception as exc:
            logger.error("Unable to create a new session checkpoint: %s", exc)
            self.message = "Progress could not be saved."
            return False
        self.session = candidate_session
        self.evaluation = candidate_evaluation
        self.selected_start_level = level
        self.checkpoint_phase = "reading"
        self.checkpoint_latest_result = None
        self.latest_result = None
        self.latest_result_kind = None
        return True

    def save_active_session(
        self, phase: str, latest_result: dict | None = None
    ) -> bool:
        if self.selected_start_level is None:
            return False
        try:
            self.checkpoint_store.save(
                self.selected_start_level,
                phase,
                self.session,
                self.evaluation,
                latest_result,
            )
            self.checkpoint_phase = phase
            self.checkpoint_latest_result = latest_result
            return True
        except Exception as exc:
            logger.error("Unable to save active session: %s", exc)
            self.message = "Progress could not be saved."
            return False

    def continue_saved_session(self) -> str | None:
        try:
            restored = self.checkpoint_store.restore(
                self.session.level_pools,
                self.evaluation.log_path,
                self.evaluation.pass_bar,
            )
        except Exception as exc:
            logger.error("Unable to restore active session: %s", exc)
            self.message = "Saved progress could not be restored."
            return None
        if restored is None:
            self.message = "Saved progress could not be restored."
            return None
        self.session = restored.session
        self.evaluation = restored.evaluation
        self.selected_start_level = restored.selected_start_level
        self.latest_result_kind = restored.latest_result_kind
        self.latest_result = restored.latest_result
        self.checkpoint_phase = restored.phase
        self.checkpoint_latest_result = (
            None
            if restored.latest_result is None
            else {
                "kind": restored.latest_result_kind,
                "payload": asdict(restored.latest_result),
            }
        )
        return restored.phase

    def clear_active_session(self) -> None:
        self.checkpoint_store.clear()
        self.selected_start_level = None
        self.checkpoint_phase = None
        self.checkpoint_latest_result = None
```

Use the existing project logger rather than introducing `print()` calls.

- [ ] **Step 4: Run orchestration and persistence tests**

```bash
.venv/bin/pytest -q tests/test_app_session_flow.py tests/test_session_checkpoint.py
```

Expected: all tests pass.

- [ ] **Step 5: Commit the application boundary**

```bash
git add src/ella_bot/ui/pygame_gui/app.py tests/test_app_session_flow.py
git commit -m "feat: orchestrate resumable GUI sessions" -m "Give EllaGUIApp transactional new-session, save, restore, summary, and clear operations while keeping scenes independent of checkpoint files."
```

---

### Task 5: Add the Saved-Session Modal to the Main Menu

**Files:**
- Modify: `src/ella_bot/ui/pygame_gui/scenes/main_menu.py:16-205`
- Create: `tests/test_main_menu_scene.py`

**Interfaces:**
- Consumes: app methods from Task 4 and existing `switch_scene()` behavior.
- Produces: `_do_start()`, `_do_continue()`, `_do_new_session()`, and modal rendering/input state.

- [ ] **Step 1: Write failing main-menu flow tests**

```python
from unittest.mock import MagicMock

from ella_bot.services.session_checkpoint import SavedSessionSummary
from ella_bot.ui.pygame_gui.scenes.main_menu import MainMenuScene


def _scene():
    app = MagicMock()
    scene = MainMenuScene(app)
    return scene


def test_start_without_checkpoint_opens_level_selection():
    scene = _scene()
    scene.app.saved_session_summary.return_value = None

    scene._do_start()

    scene.app.switch_scene.assert_called_once_with("level_selection")
    assert scene.show_resume_prompt is False


def test_start_with_checkpoint_opens_resume_prompt():
    scene = _scene()
    summary = SavedSessionSummary("2c", 4, "2026-07-24T10:00:00+08:00", "reading")
    scene.app.saved_session_summary.return_value = summary

    scene._do_start()

    assert scene.show_resume_prompt is True
    assert scene.resume_summary == summary
    scene.app.switch_scene.assert_not_called()


def test_continue_reading_checkpoint_starts_saved_attempt():
    scene = _scene()
    scene.app.continue_saved_session.return_value = "reading"

    scene._do_continue()

    scene.app.switch_scene.assert_called_once_with("reading_prompt")
    scene.app.active_scene._start_attempt.assert_called_once()


def test_continue_results_checkpoint_opens_results_without_attempt():
    scene = _scene()
    scene.app.continue_saved_session.return_value = "results"

    scene._do_continue()

    scene.app.switch_scene.assert_called_once_with("results")
    scene.app.active_scene._start_attempt.assert_not_called()


def test_new_session_choice_does_not_clear_checkpoint():
    scene = _scene()

    scene._do_new_session()

    scene.app.clear_active_session.assert_not_called()
    scene.app.switch_scene.assert_called_once_with("level_selection")


def test_entering_main_menu_does_not_reset_progress():
    scene = _scene()
    scene.on_enter()
    scene.app.session.reset_current_level.assert_not_called()
```

- [ ] **Step 2: Run main-menu tests and verify RED**

```bash
.venv/bin/pytest -q tests/test_main_menu_scene.py
```

Expected: failures for missing action methods and modal state.

- [ ] **Step 3: Implement action methods and remove destructive menu entry reset**

Initialize `show_resume_prompt`, `resume_summary`, and three modal button rects. Remove `self.app.session.reset_current_level()` from `on_enter()`.

```python
    def _do_start(self) -> None:
        summary = self.app.saved_session_summary()
        if summary is None:
            self.app.switch_scene("level_selection")
            return
        self.resume_summary = summary
        self.show_resume_prompt = True

    def _do_continue(self) -> None:
        phase = self.app.continue_saved_session()
        if phase == "reading":
            self.app.switch_scene("reading_prompt")
            self.app.active_scene._start_attempt()
        elif phase == "results":
            self.app.switch_scene("results")

    def _do_new_session(self) -> None:
        self.show_resume_prompt = False
        self.app.switch_scene("level_selection")
```

Route the existing Start mouse-up branch through `_do_start()`. While the resume modal is visible, consume input only for Continue, New Session, and Cancel. Render an opaque overlay and centered dialog showing `Level {summary.level.upper()}`, `Item {summary.item_number}`, and a readable local save timestamp. Cancel closes the modal and leaves the checkpoint unchanged.

- [ ] **Step 4: Run main-menu tests and verify GREEN**

```bash
.venv/bin/pytest -q tests/test_main_menu_scene.py
```

Expected: all main-menu tests pass.

- [ ] **Step 5: Commit the resume choice flow**

```bash
git add src/ella_bot/ui/pygame_gui/scenes/main_menu.py tests/test_main_menu_scene.py
git commit -m "feat: offer saved-session choices from Start" -m "Show saved level, item, and timestamp before restoring exact progress or opening the new-session level picker without deleting the checkpoint."
```

---

### Task 6: Build the All-Unlocked Level Selection Scene

**Files:**
- Create: `src/ella_bot/ui/pygame_gui/scenes/level_selection.py`
- Modify: `src/ella_bot/ui/pygame_gui/app.py:4-14,195-202`
- Create: `tests/test_level_selection_scene.py`

**Interfaces:**
- Consumes: `LEVEL_ORDER`, `app.start_new_session(level)`, `switch_scene()`, and shared app fonts.
- Produces: `LevelSelectionScene`, `level_buttons: Dict[str, pygame.Rect]`, confirmation state, and Back/Confirm/Cancel actions.

- [ ] **Step 1: Write failing level-selection tests**

```python
from unittest.mock import MagicMock

import pygame

from ella_bot.core.constants import LEVEL_ORDER
from ella_bot.ui.pygame_gui.scenes.level_selection import LevelSelectionScene


def _scene():
    pygame.font.init()
    app = MagicMock()
    app.screen = pygame.Surface((1280, 720))
    app.font_title = pygame.font.SysFont(None, 64)
    app.font_body = pygame.font.SysFont(None, 30)
    app.font_button = pygame.font.SysFont(None, 42)
    scene = LevelSelectionScene(app)
    return scene


def test_render_exposes_every_level_as_enabled_button():
    scene = _scene()
    scene.render()
    assert list(scene.level_buttons) == LEVEL_ORDER
    assert all(rect.width > 0 and rect.height > 0 for rect in scene.level_buttons.values())


def test_selecting_level_opens_confirmation_without_replacing_checkpoint():
    scene = _scene()
    scene._select_level("2c")
    assert scene.pending_level == "2c"
    assert scene.show_confirmation is True
    scene.app.start_new_session.assert_not_called()


def test_confirm_starts_selected_level_then_opens_prompt():
    scene = _scene()
    scene.pending_level = "2c"
    scene.show_confirmation = True
    scene.app.start_new_session.return_value = True

    scene._confirm_level()

    scene.app.start_new_session.assert_called_once_with("2c")
    scene.app.switch_scene.assert_called_once_with("reading_prompt")
    scene.app.active_scene._start_attempt.assert_called_once()


def test_failed_checkpoint_save_stays_on_confirmation():
    scene = _scene()
    scene.pending_level = "3"
    scene.show_confirmation = True
    scene.app.start_new_session.return_value = False

    scene._confirm_level()

    scene.app.switch_scene.assert_not_called()
    assert scene.show_confirmation is True


def test_cancel_and_back_preserve_saved_session():
    scene = _scene()
    scene.pending_level = "4"
    scene.show_confirmation = True
    scene._cancel_confirmation()
    scene._go_back()
    scene.app.clear_active_session.assert_not_called()
    scene.app.switch_scene.assert_called_once_with("main_menu")
```

- [ ] **Step 2: Run level-selection tests and verify RED**

```bash
.venv/bin/pytest -q tests/test_level_selection_scene.py
```

Expected: import failure because the scene does not exist.

- [ ] **Step 3: Implement the scene and confirmation actions**

Build the level list directly from `LEVEL_ORDER` and retain insertion order:

```python
class LevelSelectionScene(BaseScene):
    def __init__(self, app):
        super().__init__(app)
        self.level_buttons: Dict[str, pygame.Rect] = {}
        self.back_button = None
        self.confirm_button = None
        self.cancel_button = None
        self.pending_level: str | None = None
        self.show_confirmation = False
        self.pressed_button: str | None = None

    def on_enter(self) -> None:
        self.pending_level = None
        self.show_confirmation = False
        self.pressed_button = None

    def _select_level(self, level: str) -> None:
        if level in LEVEL_ORDER:
            self.pending_level = level
            self.show_confirmation = True

    def _confirm_level(self) -> None:
        if self.pending_level is None:
            return
        if self.app.start_new_session(self.pending_level):
            self.show_confirmation = False
            self.app.switch_scene("reading_prompt")
            self.app.active_scene._start_attempt()

    def _cancel_confirmation(self) -> None:
        self.pending_level = None
        self.show_confirmation = False

    def _go_back(self) -> None:
        self.app.switch_scene("main_menu")
```

Render a card consistent with existing scenes. Place 1A–1G in a labeled Level 1 row, 2A–2D in a Level 2 row, and 3/4 in the final row. Use the same enabled button colors for every entry; do not add lock flags. Render Back outside the grid. The confirmation dialog states the selected level and that previously saved progress will be replaced, with Confirm and Cancel buttons.

Register `LevelSelectionScene(self)` under `"level_selection"` in `EllaGUIApp.run()`.

- [ ] **Step 4: Run level-selection and main-menu tests**

```bash
.venv/bin/pytest -q tests/test_level_selection_scene.py tests/test_main_menu_scene.py
```

Expected: all navigation-scene tests pass.

- [ ] **Step 5: Commit the level picker**

```bash
git add src/ella_bot/ui/pygame_gui/scenes/level_selection.py src/ella_bot/ui/pygame_gui/app.py tests/test_level_selection_scene.py
git commit -m "feat: add unlocked level selection screen" -m "Present all thirteen curriculum levels in grouped enabled rows and require confirmation before replacing saved progress and beginning the selected level."
```

---

### Task 7: Checkpoint Every Completed Attempt

**Files:**
- Modify: `src/ella_bot/services/attempt_runner.py:245-415`
- Modify: `tests/test_attempt_runner.py`

**Interfaces:**
- Consumes: `app.save_active_session()` and `app.clear_active_session()`.
- Produces: one coherent checkpoint after scored/silent progression and results checkpoints before result events.

- [ ] **Step 1: Write failing autosave tests**

Add assertions to real AttemptRunner flows rather than mocking progression itself:

```python
def test_scored_attempt_saves_reading_after_advancing_item(tmp_path, monkeypatch):
    monkeypatch.setattr(runner_mod, "validate_spoken_text", lambda exp, got, **kwargs: _FakeValidation())
    monkeypatch.setattr(runner_mod, "build_feedback", lambda **kwargs: _FakeFeedback())
    monkeypatch.setattr(runner_mod, "build_highlighted_expected", lambda alignment: "")
    monkeypatch.setattr(runner_mod, "normalize", lambda text: ["a"])
    monkeypatch.setattr(runner_mod, "spoken_word_confidence_map", lambda tokens, confidences: {})
    app = _make_app(tmp_path)
    app.session = SessionManager({"1a": ["a", "b"]}, "1a")

    AttemptRunner(app, is_paused=lambda: False).run()

    assert app.session.expected_sentence == "b"
    app.save_active_session.assert_called_once_with("reading")


def test_silent_attempt_saves_reading_retry_state(tmp_path):
    app = _make_app(tmp_path)
    app.asr.transcribe.return_value = _FakeASRResult("")

    AttemptRunner(app, is_paused=lambda: False).run()

    app.save_active_session.assert_called_once_with("reading")


def test_sublevel_completion_saves_results_before_event(tmp_path, monkeypatch):
    monkeypatch.setattr(runner_mod, "validate_spoken_text", lambda exp, got, **kwargs: _FakeValidation())
    monkeypatch.setattr(runner_mod, "build_feedback", lambda **kwargs: _FakeFeedback())
    monkeypatch.setattr(runner_mod, "build_highlighted_expected", lambda alignment: "")
    monkeypatch.setattr(runner_mod, "normalize", lambda text: ["a"])
    monkeypatch.setattr(runner_mod, "spoken_word_confidence_map", lambda tokens, confidences: {})
    app = _make_app(tmp_path)

    AttemptRunner(app, is_paused=lambda: False).run()

    phase, result = app.save_active_session.call_args.args
    assert phase == "results"
    assert result["kind"] == "sublevel"
    assert result["payload"]["level"] == "1a"


def test_full_completion_clears_checkpoint_instead_of_saving_results(tmp_path):
    app = _make_app(tmp_path)
    app.session = SessionManager({"4": ["done"]}, "4")
    app.evaluation = EvaluationService(tmp_path / "s.jsonl", 0.70)
    runner = AttemptRunner(app, is_paused=lambda: False)
    app.evaluation.record_attempt("4", 1, "done", "done", 1.0, 0.0, True)

    runner._advance_after_attempt("4", app.session, True, False)

    app.clear_active_session.assert_called_once()
```

- [ ] **Step 2: Run autosave tests and verify RED**

```bash
.venv/bin/pytest -q tests/test_attempt_runner.py -k "saves or clears_checkpoint"
```

Expected: save/clear mock assertions fail.

- [ ] **Step 3: Save stable reading and result phases**

After `_advance_after_attempt()` returns `False`, call `self.app.save_active_session("reading")` in both the scored and `_handle_no_input()` paths before posting the next user message.

Inside `_advance_after_attempt()`, save the completed result before speech or event delivery:

```python
    def _save_result_checkpoint(self, kind: str, result) -> None:
        self.app.save_active_session(
            "results",
            {"kind": kind, "payload": asdict(result)},
        )
```

Import `asdict` from `dataclasses` at the top of `attempt_runner.py`.
Call `_save_result_checkpoint("sublevel", sub_result)` for an ordinary sublevel and `_save_result_checkpoint("tier", tier_result)` at a tier boundary. On full Level 4 completion, call `self.app.clear_active_session()` immediately after `finish_session()` succeeds and before final-completion speech/event delivery. Do not create a results checkpoint for the completed session.

- [ ] **Step 4: Run all attempt-runner tests**

```bash
.venv/bin/pytest -q tests/test_attempt_runner.py
```

Expected: all attempt tests pass, including scored and silent autosave coverage.

- [ ] **Step 5: Commit stable attempt checkpoints**

```bash
git add src/ella_bot/services/attempt_runner.py tests/test_attempt_runner.py
git commit -m "feat: checkpoint every completed reading attempt" -m "Save retry, advancement, and pending-results state only after attempt progression settles, and clear active progress after final session completion."
```

---

### Task 8: Checkpoint Results, Pause, Reset, and Play-Again Actions

**Files:**
- Modify: `src/ella_bot/ui/pygame_gui/scenes/results.py:62-102`
- Modify: `src/ella_bot/ui/pygame_gui/scenes/reading_prompt.py:80-130`
- Modify: `src/ella_bot/ui/pygame_gui/scenes/settings.py:86-100`
- Modify: `src/ella_bot/ui/pygame_gui/scenes/final_eval.py:33-46`
- Modify: `tests/test_results_scene.py`
- Modify: `tests/test_reading_prompt_auto_continue.py`
- Modify: `tests/test_settings_scene.py`
- Modify: `tests/test_final_eval_scene.py`

**Interfaces:**
- Consumes: app orchestration methods from Task 4.
- Produces: checkpoint-consistent navigation for every non-attempt state mutation.

- [ ] **Step 1: Write failing result-action tests**

Extend existing scene tests with call-order-safe assertions:

```python
def test_next_saves_advanced_reading_state():
    scene = _make_scene(passed=True)
    scene._do_next()
    scene.app.session.advance_to_higher_stage.assert_called_once()
    scene.app.save_active_session.assert_called_once_with("reading")


def test_retry_saves_reset_reading_state():
    scene = _make_scene(kind="sublevel", passed=False, level="1c")
    scene._do_retry()
    scene.app.evaluation.reset_sublevel.assert_called_once_with("1c")
    scene.app.save_active_session.assert_called_once_with("reading")


def test_failure_menu_saves_reset_state_before_navigation():
    scene = _make_scene(kind="sublevel", passed=False, level="1a")
    scene._do_main_menu()
    scene.app.save_active_session.assert_called_once_with("reading")
    scene.app.switch_scene.assert_called_once_with("main_menu")


def test_success_restart_uses_transactional_new_session():
    scene = _make_scene(passed=True)
    scene.app.start_new_session.return_value = True
    scene._do_restart_to_menu()
    scene.app.start_new_session.assert_called_once_with("1a")
    scene.app.evaluation.reset_all.assert_not_called()


def test_failed_transition_save_restores_pending_results_state():
    scene = _make_scene(passed=True)
    scene.app.save_active_session.return_value = False

    scene._do_next()

    scene.app.continue_saved_session.assert_called_once()
    scene.app.switch_scene.assert_not_called()
```

Add focused tests that pause-modal Restart Level saves after reset, Back to Menu saves after aborting, Settings Reset Progress calls `clear_active_session()`, and Final Evaluation Play Again calls `start_new_session("1a")` before navigation.

- [ ] **Step 2: Run the four scene test modules and verify RED**

```bash
.venv/bin/pytest -q tests/test_results_scene.py tests/test_reading_prompt_auto_continue.py tests/test_settings_scene.py tests/test_final_eval_scene.py
```

Expected: new checkpoint assertions fail.

- [ ] **Step 3: Add checkpoint calls after every scene mutation**

Apply this ordering:

```python
def _save_reading_transition_or_restore(self) -> bool:
    if self.app.save_active_session("reading"):
        return True
    self.app.continue_saved_session()
    return False

# Results: passed Next
self.app.session.advance_to_higher_stage()
if not self._save_reading_transition_or_restore():
    return
self.app.switch_scene("reading_prompt")
self.app.active_scene._start_attempt()

# Results: retry or failure-to-menu
self._reset_for_retry()
if not self._save_reading_transition_or_restore():
    return

# Results: success Continue-to-menu
self.app.session.advance_to_higher_stage()
if not self._save_reading_transition_or_restore():
    return

# Results: success Restart-to-menu
if self.app.start_new_session("1a"):
    self.app.switch_scene("main_menu")

# Final evaluation: Play Again
if self.app.start_new_session("1a"):
    self.app.switch_scene("reading_prompt")
    self.app.active_scene._start_attempt()
```

The old on-disk checkpoint remains the pending results phase until a reading
transition saves successfully. Restoring it on save failure prevents a second
button press from advancing or resetting twice.

In the reading pause modal, abort the current runner before mutating session state. Restart Level resets session/evaluation, saves `reading`, and then starts. If that save fails, restore the previous checkpoint and remain paused. Back to Menu aborts, saves `reading`, and then switches scenes. Do not reset the item merely by entering the menu.

In Settings Reset Progress, retain `session.reset_to_start()` and `evaluation.reset_all()`, then call `clear_active_session()` before returning to the menu. Do not checkpoint volume or listening-duration changes.

- [ ] **Step 4: Run affected scene tests and verify GREEN**

```bash
.venv/bin/pytest -q tests/test_results_scene.py tests/test_reading_prompt_auto_continue.py tests/test_settings_scene.py tests/test_final_eval_scene.py
```

Expected: all affected scene tests pass.

- [ ] **Step 5: Commit lifecycle checkpoint coverage**

```bash
git add src/ella_bot/ui/pygame_gui/scenes/results.py src/ella_bot/ui/pygame_gui/scenes/reading_prompt.py src/ella_bot/ui/pygame_gui/scenes/settings.py src/ella_bot/ui/pygame_gui/scenes/final_eval.py tests/test_results_scene.py tests/test_reading_prompt_auto_continue.py tests/test_settings_scene.py tests/test_final_eval_scene.py
git commit -m "feat: keep navigation actions checkpoint-consistent" -m "Persist result advancement, retries, pause-menu exits, and play-again sessions while clearing checkpoints only for explicit progress reset or final completion."
```

---

### Task 9: Remove Silent CLI Recovery and Add Safe Shutdown

**Files:**
- Modify: `src/ella_bot/cli/main.py:166-196`
- Modify: `src/ella_bot/ui/pygame_gui/app.py:149-221`
- Modify: `src/ella_bot/ui/pygame_gui/scenes/reading_prompt.py:21-61`
- Create: `tests/test_cli_gui.py`
- Modify: `tests/test_app_session_flow.py`
- Modify: `tests/test_reading_prompt_auto_continue.py`
- Modify: `tests/test_gui_e2e.py`

**Interfaces:**
- Consumes: active runner abort behavior and `save_active_session("reading")`.
- Produces: `ReadingPromptScene.prepare_shutdown()`, `EllaGUIApp.shutdown()`, and GUI startup that never infers active state from history.

- [ ] **Step 1: Write failing CLI and shutdown tests**

```python
def test_run_gui_does_not_recover_level_from_history(tmp_path, monkeypatch):
    from argparse import Namespace
    from ella_bot.cli import main as cli_main

    log = tmp_path / "sessions.jsonl"
    log.write_text('{"type":"sublevel","level":"2a","passed":true}\n')
    args = Namespace(
        session_log=str(log),
        start_level="1a",
        gui_width=1280,
        gui_height=720,
        fullscreen=False,
        audio_feedback=False,
        pronunciation_overrides="missing.json",
    )
    monkeypatch.setattr(cli_main, "build_asr", lambda value: object())
    monkeypatch.setattr(cli_main, "build_tts_if_enabled", lambda value: None)
    monkeypatch.setattr(cli_main, "load_pronunciation_overrides", lambda value: {})
    app_class = MagicMock()
    monkeypatch.setattr(cli_main, "EllaGUIApp", app_class)

    cli_main.run_gui(args)

    assert app_class.call_args.kwargs["start_level"] == "1a"


def test_prepare_shutdown_aborts_and_joins_attempt_worker():
    scene = _make_scene()
    scene.runner = MagicMock()
    scene.worker_thread = MagicMock()
    scene.worker_thread.is_alive.return_value = True

    scene.prepare_shutdown()

    scene.runner.abort.assert_called_once()
    scene.worker_thread.join.assert_called_once_with(timeout=2.0)


def test_app_shutdown_saves_only_started_active_session(tmp_path):
    app = _make_app(tmp_path)
    app.selected_start_level = "1a"
    app.active_scene = MagicMock()

    app.shutdown()

    app.active_scene.prepare_shutdown.assert_called_once()
    assert app.has_saved_session() is True
```

Build the CLI `Namespace` in the actual test using all attributes accessed by `build_asr`, `build_tts_if_enabled`, and GUI construction, or mock those functions exactly as shown so no unrelated argument is required.

- [ ] **Step 2: Run CLI and shutdown tests and verify RED**

```bash
.venv/bin/pytest -q tests/test_cli_gui.py tests/test_app_session_flow.py tests/test_reading_prompt_auto_continue.py -k "recover or shutdown"
```

Expected: the CLI still recovers a level and shutdown helpers are missing.

- [ ] **Step 3: Remove GUI history inference**

Reduce `run_gui()` to pass the requested start level unchanged:

```python
    gui = EllaGUIApp(
        expected_sentence="",
        asr=build_asr(args),
        tts=build_tts_if_enabled(args),
        audio_feedback=args.audio_feedback,
        pronunciation_overrides=load_pronunciation_overrides(args.pronunciation_overrides),
        start_level=args.start_level,
        config=GUIConfig(
            width=args.gui_width,
            height=args.gui_height,
            fullscreen=args.fullscreen,
            session_log_path=session_log,
        ),
    )
```

Leave `get_resume_level()` available for compatibility unless a repository-wide search confirms no non-GUI consumer; only remove its GUI invocation and automatic-resume print.

- [ ] **Step 4: Add orderly reading-scene and application shutdown**

```python
# ReadingPromptScene
    def prepare_shutdown(self) -> None:
        self._auto_start_at = None
        if self.runner is not None:
            self.runner.abort()
        if self.app.tts is not None:
            try:
                self.app.tts.stop()
            except Exception:
                pass
        if self.worker_thread is not None and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=2.0)


# EllaGUIApp
    def shutdown(self) -> None:
        prepare = getattr(self.active_scene, "prepare_shutdown", None)
        if callable(prepare):
            prepare()
        if self.selected_start_level is not None and self.checkpoint_phase is not None:
            self.save_active_session(
                self.checkpoint_phase,
                self.checkpoint_latest_result,
            )
```

Wrap the pygame run loop in `try/finally` so `shutdown()` runs before `pygame.quit()`. The Task 4 checkpoint-phase fields preserve a pending results checkpoint rather than overwriting it as reading state. For a reading scene, abort and join the worker before the final save.

- [ ] **Step 5: Update the automated GUI harness**

Register `LevelSelectionScene` in `E2EInteractiveApp.scenes`. In `AutoMainMenuScene.update()`, call `start_new_session("1a")` before opening the reading prompt so the automated harness intentionally bypasses mouse-driven selection without bypassing checkpoint initialization.

- [ ] **Step 6: Run CLI, app, reading, and GUI integration tests**

```bash
.venv/bin/pytest -q tests/test_cli_gui.py tests/test_app_session_flow.py tests/test_reading_prompt_auto_continue.py tests/test_gui_e2e.py
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit startup and shutdown behavior**

```bash
git add src/ella_bot/cli/main.py src/ella_bot/ui/pygame_gui/app.py src/ella_bot/ui/pygame_gui/scenes/reading_prompt.py tests/test_cli_gui.py tests/test_app_session_flow.py tests/test_reading_prompt_auto_continue.py tests/test_gui_e2e.py
git commit -m "fix: restore sessions only through explicit GUI choice" -m "Remove silent history-based level recovery and checkpoint the last stable phase only after aborting and joining active attempt work during shutdown."
```

---

### Task 10: Verify the Complete Feature and Commit Any Test-Only Integration Adjustments

**Files:**
- Modify only if required by verified integration behavior: `tests/test_gui_e2e.py`
- Verify: all files changed in Tasks 1-9

**Interfaces:**
- Consumes: the complete checkpoint and navigation feature.
- Produces: a clean full-suite verification and documented manual smoke path.

- [ ] **Step 1: Run formatting and whitespace validation**

```bash
git diff --check
```

Expected: no output and exit code 0.

- [ ] **Step 2: Run the complete automated suite**

Run outside a restricted sandbox if native Piper imports stall there:

```bash
.venv/bin/pytest -q tests
```

Expected: all tests pass with zero failures.

- [ ] **Step 3: Perform a windowed manual smoke test**

Use a temporary session-log directory or back up local runtime data first. Verify this exact path:

1. Start ELLA with no `active_session.json`.
2. Click Start and confirm all 13 levels are enabled.
3. Select 2C, cancel confirmation, and verify no checkpoint replacement.
4. Select 2C again, confirm, complete one attempt, and return to the menu.
5. Restart ELLA, click Start, and verify the modal reports Level 2C and the exact next/retry item.
6. Continue and verify the correct item and prior attempt count.
7. Produce a failing grade and verify advancement remains gated.
8. Start New Session, back out, and verify Continue still restores 2C.
9. Start New Session at 3, confirm, and verify the checkpoint changes only then.
10. Complete Level 4 in a controlled test configuration and verify the active checkpoint is cleared while `sessions.jsonl` retains final history.

- [ ] **Step 4: Inspect repository scope**

```bash
git status --short
git log --oneline --decorate -12
```

Expected: only the intended implementation commits plus pre-existing unrelated local files. Do not stage `data/sessions.jsonl`, invalid checkpoint archives, scratch scripts, or unrelated documentation.

- [ ] **Step 5: Commit only necessary test-harness adjustments, if any**

If Step 2 or Step 3 required a test-only integration correction:

```bash
git add tests/test_gui_e2e.py
git commit -m "test: cover level selection and session recovery flow" -m "Exercise explicit session initialization in the automated GUI harness and retain regression coverage for resumed progression."
```

If no file changed, do not create an empty commit.
