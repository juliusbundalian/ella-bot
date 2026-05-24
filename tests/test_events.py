import dataclasses
import pytest

from ella_bot.core.events import StateChanged, MessageChanged, ErrorOccurred, AttemptReady


def test_events_carry_their_payload():
    assert StateChanged("listening").state == "listening"
    assert MessageChanged("hi").message == "hi"
    assert ErrorOccurred("boom").error == "boom"
    vm = object()
    assert AttemptReady(vm).view_model is vm


def test_events_are_frozen():
    evt = StateChanged("idle")
    with pytest.raises(dataclasses.FrozenInstanceError):
        evt.state = "speaking"


def test_sublevel_and_session_events_carry_payload():
    from ella_bot.core.events import SubLevelCompleted, SessionCompleted
    r = object()
    evt = SubLevelCompleted(r, "tier")
    assert evt.result is r
    assert evt.kind == "tier"
    assert SessionCompleted(r).result is r


def test_new_events_are_frozen():
    from ella_bot.core.events import SubLevelCompleted
    evt = SubLevelCompleted(object(), "sublevel")
    with pytest.raises(dataclasses.FrozenInstanceError):
        evt.kind = "tier"
