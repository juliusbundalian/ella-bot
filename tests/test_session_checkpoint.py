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
