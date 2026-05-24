from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StateChanged:
    state: str


@dataclass(frozen=True)
class MessageChanged:
    message: str


@dataclass(frozen=True)
class ErrorOccurred:
    error: str


@dataclass(frozen=True)
class AttemptReady:
    view_model: Any
