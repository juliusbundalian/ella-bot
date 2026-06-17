# No-Input (Silent Turn) Response — Design

**Date:** 2026-06-18
**Status:** Approved design, ready for implementation plan

## Problem

When a child gives no input — they stay silent, or the microphone catches
nothing — the ASR returns `ASRResult(transcript="", words=[])`. Today the
`AttemptRunner` treats that empty transcript exactly like a wrong answer:

- it runs `validate_spoken_text("...", "")`, producing accuracy `0.0`,
- builds pronunciation coaching feedback and speaks it,
- emits an `AttemptReady` view model whose highlighted target renders as
  "every word missed",
- counts the turn as an attempt and (on tier 1) advances past the item.

There is no distinct "I didn't hear you" path. Silence should feel different
from getting the word wrong: Ella should gently re-prompt rather than coach
pronunciation for something that was never spoken.

## Goals

- Detect a genuinely silent turn and respond with a dedicated, encouraging line
  instead of pronunciation coaching.
- Keep the existing progression rules unchanged: a silent turn still counts as
  an attempt.
- Avoid showing the child an all-red "wrong" result panel just for being quiet.

## Non-goals

- Detecting noise / low-confidence / partial mumbles. Only a truly empty
  transcript triggers this path; anything that resolves to words goes through
  normal validation.
- Changing attempt limits, tier rules, or evaluation scoring.
- Adding a re-listen timer or "are you still there?" idle behavior.

## Decisions

| Question | Decision |
|----------|----------|
| What triggers it | Empty transcript only (`transcript.strip() == ""`). |
| Does it count as an attempt | Yes — same bookkeeping as a wrong answer (counter, advance/exhaust, evaluation record). |
| Message on the turn that advances the item | No-input **move-on** phrase (acknowledges the silence *and* the move). |
| Message when staying on the item | No-input **re-prompt** phrase. |
| On-screen result panel | Skip `AttemptReady` on silence; update the status message only. |
| Pronunciation coaching | None on silence — nothing was spoken to coach. |

## Approach

Branch inside `AttemptRunner.run()`, immediately after `asr.transcribe(...)`
returns and after the existing pause check, **before** validation. This mirrors
how `_EXHAUSTION_PHRASES` already lives in this module and keeps the
silence concern out of the scoring code (`validators.py` / `feedback.py`).

Rejected alternatives:
- *Synthesize a "no-input" `FeedbackResult` in `feedback.py`.* Muddies a module
  whose job is scoring *spoken* text, and the coaching builder would still need
  a silence carve-out.
- *Separate phrase module + helper.* Overkill for two short phrase lists.

## Detailed behavior

New module-level phrase lists in `attempt_runner.py`, next to
`_EXHAUSTION_PHRASES`:

- `_NO_INPUT_PHRASES` — gentle re-prompts used when the child will try the same
  item again. Examples:
  - "I didn't quite hear you. Let's try again!"
  - "Hmm, I didn't hear anything. Give it a try!"
  - "Let's try that again — I'm listening!"
- `_NO_INPUT_MOVE_ON_PHRASES` — used on the turn that advances to a new item.
  Examples:
  - "I didn't quite hear you that time. Let's try a new one!"
  - "That's okay! Let's move on to the next one."

Flow when `transcript.strip() == ""`:

1. **Skip** `validate_spoken_text`, `build_feedback`,
   `build_highlighted_expected`, and the `AttemptReady` emission. There is
   nothing to score or display.
2. **Attempt bookkeeping** — identical to the wrong-answer path:
   - reset-or-increment `_item_attempt_count` keyed on
     `(level, session.current_item_number())`,
   - `max_attempts = max_attempts_for_level(level)`,
   - `correct = False`,
   - `exhausted = self._item_attempt_count >= max_attempts`.
   - The item advances this turn when `correct or exhausted` is true — note
     that tier-1 levels have `max_attempts == 1`, so a single silent turn
     exhausts and advances, matching today's tier-1 behavior.
3. **Speak** (when `audio_feedback` and `tts` are available and not paused):
   - if the item advances this turn → `random.choice(_NO_INPUT_MOVE_ON_PHRASES)`,
   - otherwise → `random.choice(_NO_INPUT_PHRASES)`.
   Wrap with the usual `StateChanged("speaking")` → speak →
   `StateChanged("idle")` sequence.
4. **Record** the attempt: `evaluation.record_attempt(level=..., item=...,
   expected=session.expected_sentence, heard="", accuracy=0.0, wer=1.0,
   correct=False)`. Keeps the session log honest since the turn counts.
5. **Progression** — reuse the existing logic: bump `completed_in_level` and
   reset `_item_attempt_count` when `correct or exhausted`; run the
   `current_sublevel_complete()` / `finish_*` / `SubLevelCompleted` /
   `SessionCompleted` cascade exactly as the scored path does; otherwise stay on
   the item.
6. **Status message** — `MessageChanged` set to a short matching line, e.g.
   "I didn't hear you — let's try again!" (re-prompt) or "Let's move on." when
   advancing. `StateChanged("retry")` (silence is never `success`).
7. Return to `listening` as the normal path does.

The `replay()` method is unaffected: because silence skips `AttemptReady`,
`app.latest_attempt` still points at the child's most recent *real* attempt, so
the replay button replays that rather than a blank result.

## Implementation note: shared progression

The wrong/exhausted progression block (steps 5–7) duplicates logic that already
exists for the scored path. To avoid two copies drifting apart, factor the
post-attempt progression (advance/exhaust bookkeeping, sublevel/tier/session
cascade, return-to-listening) into a small private helper on `AttemptRunner`
that both the scored path and the silent path call. Keep the refactor scoped to
what these two paths need — do not restructure unrelated parts of `run()`.

## Testing

New tests in `tests/test_attempt_runner.py`, driving
`app.asr.transcribe.return_value = _FakeASRResult("")` (extend the fake to take
a transcript argument):

1. **Tier-1 silent turn advances** — single tier-1 item, silent turn → item
   advances, `completed_in_level == 1`, a `_NO_INPUT_MOVE_ON_PHRASES` line is
   spoken, and an attempt is recorded with `heard == ""`.
2. **Tier-2+ silent turn with tries left stays** — silent turn does not advance
   (`expected_sentence` unchanged, `completed_in_level == 0`), and a
   `_NO_INPUT_PHRASES` line is spoken.
3. **Tier-2+ final silent turn exhausts** — after exhausting the retry limit via
   silent turns, the item advances and a `_NO_INPUT_MOVE_ON_PHRASES` line is
   spoken.
4. **No coaching on silence** — none of the pronunciation-coaching lines
   ("let me read", "Now you try!") are spoken on a silent turn.
5. **No AttemptReady on silence** — no `AttemptReady` event is emitted for a
   silent turn.

Use the existing `_spoken(app)` helper and the event-draining pattern already in
the test module.
