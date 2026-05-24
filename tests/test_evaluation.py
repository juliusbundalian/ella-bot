import json
from pathlib import Path

import pytest

from ella_bot.services.evaluation import EvaluationService, rating_for


def make_service(tmp_path) -> EvaluationService:
    return EvaluationService(log_path=tmp_path / "sessions.jsonl", pass_bar=0.70)


@pytest.mark.parametrize(
    "fluency,expected",
    [(0.90, "A"), (0.895, "B"), (0.80, "B"), (0.799, "C"),
     (0.70, "C"), (0.699, "D"), (0.60, "D"), (0.599, "F"), (0.0, "F")],
)
def test_rating_for_bands(fluency, expected):
    assert rating_for(fluency) == expected


def test_finish_sublevel_computes_fluency_and_first_try(tmp_path):
    svc = make_service(tmp_path)
    # item 1: wrong then right (retry) ; item 2: right first try
    svc.record_attempt("1a", 1, "a", "uh", 0.40, 0.5, False)
    svc.record_attempt("1a", 1, "a", "a", 1.00, 0.0, True)
    svc.record_attempt("1a", 2, "the", "the", 1.00, 0.0, True)
    result = svc.finish_sublevel("1a")
    assert result.tier == 1
    assert result.level == "1a"
    assert result.items_total == 2
    assert result.first_try_correct == 1            # only item 2 right on first try
    assert result.attempts == 3
    assert result.fluency == pytest.approx((0.40 + 1.00 + 1.00) / 3)
    assert result.rating == rating_for(result.fluency)


def test_finish_sublevel_passed_flag_uses_bar(tmp_path):
    svc = make_service(tmp_path)
    svc.record_attempt("1a", 1, "a", "a", 0.69, 0.0, True)
    assert svc.finish_sublevel("1a").passed is False
    svc.record_attempt("1b", 1, "cat", "cat", 0.70, 0.0, True)
    assert svc.finish_sublevel("1b").passed is True


def test_finish_sublevel_appends_record_with_item_log(tmp_path):
    svc = make_service(tmp_path)
    svc.record_attempt("1a", 1, "a", "a", 1.0, 0.0, True)
    svc.finish_sublevel("1a")
    lines = (tmp_path / "sessions.jsonl").read_text().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["type"] == "sublevel"
    assert rec["level"] == "1a"
    assert rec["tier"] == 1
    assert rec["session_id"] == svc.session_id
    assert rec["items"][0]["expected"] == "a"
    assert rec["items"][0]["accuracy"] == 1.0
