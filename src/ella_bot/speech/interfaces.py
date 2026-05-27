from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class ASREngine(Protocol):
    """Anything that can turn speech into a transcript with per-word scores."""

    def transcribe(self, expected_sentence: Optional[str] = None): ...


@runtime_checkable
class TTSEngine(Protocol):
    """Anything that can speak text and be interrupted."""

    def speak(self, text: str) -> None: ...

    def stop(self) -> None: ...
