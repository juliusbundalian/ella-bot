# ASR Attempt Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a debug summary that shows whether Vosk decoding falls behind live microphone capture.

**Architecture:** Add a pure formatter in the Vosk ASR module and call it once after each microphone transcription. The capture loop counts processed blocks and bytes, while the summary derives queued-audio duration from the configured sample rate and 16-bit mono audio format.

**Tech Stack:** Python 3, Vosk, sounddevice, pytest.

## Global Constraints

- Diagnostics are debug logs only; no recognition, scoring, audio capture, persistence, or user-facing behavior changes.
- Audio is not saved.

---

### Task 1: Format and emit one ASR attempt diagnostic summary

**Files:**
- Modify: `tests/test_asr_factory.py`
- Modify: `src/ella_bot/speech/asr/vosk_engine.py`

**Interfaces:**
- Produces: `format_attempt_diagnostics(capture_seconds, processed_bytes, processed_blocks, queued_bytes, queued_blocks, sample_rate, decoder_seconds, transcript, words) -> str`.

- [ ] **Step 1: Write the failing formatter test**

```python
from ella_bot.speech.asr.vosk_engine import WordScore, format_attempt_diagnostics


def test_format_attempt_diagnostics_reports_backlog_and_word_confidence():
    message = format_attempt_diagnostics(
        capture_seconds=10.0,
        processed_bytes=320000,
        processed_blocks=40,
        queued_bytes=8000,
        queued_blocks=1,
        sample_rate=16000,
        decoder_seconds=10.2,
        transcript="the cat sat",
        words=[WordScore("the", 0.98), WordScore("cat", 0.62)],
    )

    assert "capture=10.00s" in message
    assert "processed=10.00s/40 blocks" in message
    assert "backlog=0.25s/1 blocks" in message
    assert "decode=10.20s" in message
    assert "transcript='the cat sat'" in message
    assert "the:0.98, cat:0.62" in message
```

- [ ] **Step 2: Verify the test fails**

Run: `.venv/bin/python -m pytest tests/test_asr_factory.py::test_format_attempt_diagnostics_reports_backlog_and_word_confidence -v`

Expected: FAIL with an import error because `format_attempt_diagnostics` does not exist.

- [ ] **Step 3: Implement the formatter and debug call**

```python
def format_attempt_diagnostics(
    capture_seconds: float,
    processed_bytes: int,
    processed_blocks: int,
    queued_bytes: int,
    queued_blocks: int,
    sample_rate: int,
    decoder_seconds: float,
    transcript: str,
    words: List[WordScore],
) -> str:
    bytes_per_second = sample_rate * 2
    processed_seconds = processed_bytes / bytes_per_second
    queued_seconds = queued_bytes / bytes_per_second
    word_confidences = ", ".join(f"{word.word}:{word.confidence:.2f}" for word in words)
    return (
        f"capture={capture_seconds:.2f}s "
        f"processed={processed_seconds:.2f}s/{processed_blocks} blocks "
        f"backlog={queued_seconds:.2f}s/{queued_blocks} blocks "
        f"decode={decoder_seconds:.2f}s "
        f"transcript={transcript!r} words=[{word_confidences}]"
    )
```

Count bytes and blocks when `recognizer.AcceptWaveform(data)` is called. After `FinalResult()`, snapshot the queued bytes and blocks, then log `logger.debug("[ASR] %s", format_attempt_diagnostics(...))`.

- [ ] **Step 4: Verify ASR tests**

Run: `.venv/bin/python -m pytest tests/test_asr_factory.py -v`

Expected: PASS.

- [ ] **Step 5: Review scoped changes**

Run: `git diff -- src/ella_bot/speech/asr/vosk_engine.py tests/test_asr_factory.py`

Expected: only the diagnostics formatter, counters, debug call, and its test are added, apart from pre-existing user changes.
