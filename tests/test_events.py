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
