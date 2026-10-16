# Clear Listening / Processing Status Execution Log

Implementation authorized by the user's “okay lets implement this” request.
Base commit: `03e845b`; implementation uses the existing shared workspace.
The user subsequently authorized committing these completed changes.
The previously authorized recording/curriculum changes are preserved.

## Decisions

- Keep implementation in the current workspace because the accepted plan builds
  on its uncommitted audio fixes. No new branch or automatic commit was created
  during implementation; committing was requested separately afterward.
- Scored turns use one outcome-specific feedback sequence. Do not append generic
  completion praise after an exhausted item; it can imply success after WAV 457.
  The results screen still opens after the outcome hold.
- Add scene-driven pause notifications, beyond ASR polling, so a brief pause
  during slow decoding is latched and time spent paused inside blocking TTS does
  not satisfy the outcome hold.

## Verification Ledger

- Task 1: capture lifecycle tests failed first for unsupported callbacks, then
  passed with callbacks after recognizer preparation/audio reset and before
  finalization. Missing microphone streams raise errors rather than silently
  consuming attempts. Active simulated and E2E adapters accept the contract.
- Task 2: turn lifecycle tests failed first for missing learner phase events,
  result holds, and deferred navigation, then passed. Completed scores are saved
  exactly once before feedback; the event retains the answered item and counter.
- Task 3: status copy/layout/event tests failed first, then passed. Updated old
  layout/auto-start expectations to reserve the visible status panel and prevent
  a listening label from triggering another capture. Rendered all ten phases at
  1024×600, 1024×768, and 1280×720 in `/private/tmp/ella-turn-previews/` and inspected
  representative listening, processing, practice, error, and exhaustion images.
- The full suite before the final review fixes produced 410 passes and the same
  five pre-existing failures identified before implementation.
- Final regression run after all review fixes: **413 passed, 5 deselected**.
  The five deselections are exactly those pre-existing failures; their causes
  were confirmed by the earlier full run, not hidden as new failures.
  Reports: `/private/tmp/ella-turn-status-tests.xml` (full suite before the final
  review fixes) and `/private/tmp/ella-turn-status-final-tests.xml` (final run).
- Recording coverage: **478 checked, zero missing**. Syntax compilation and
  `git diff --check` passed. Existing tests changed microphone duration/volume;
  their side effects were restored to the original settings (5 seconds, volume 6).

## Independent Review

One read-only fresh-context reviewer checked the working-tree implementation.
All three actionable findings were reproduced with failing tests before fixes:

1. Level 1 completion pause/exit could leave a completed sublevel stuck. Finalize
   its stage and checkpoint before playing recordings 463/464.
2. Pauses handled inside blocking TTS were counted as outcome visibility. Track
   pauses from the scene independently of worker polling.
3. A brief pause/resume inside slow decoding could be missed. Latch capture
   interruption until the cancelled capture closes and a fresh capture starts.

All three fixes are covered by the final passing regression run. The checkpoint
test also verifies that returning to the main menu after scoring does not
overwrite an already saved results checkpoint with a reading checkpoint.

Deferred minor: retry coaching retains its main outcome instruction (“Wait for
Speak now”) rather than adding a second “Listen to ELLA” line during WAV playback.
There is no active microphone cue during feedback.

Physical Pi timing/readability, audio intelligibility, and learner effectiveness
remain device/researcher acceptance checks. They cannot be claimed from desktop
unit tests or rendered screenshots.
