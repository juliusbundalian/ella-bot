# Clear Listening and Processing Status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking. This document authorizes planning only; do not implement or commit without an implementation request.

**Goal:** Help learners know when to speak once, when to wait, and whether their response was correct, needs another attempt, or has reached the attempt limit.

**Architecture:** Add a learner-facing turn-status event alongside the existing animation states. Drive recording status from the ASR response-window lifecycle, display a persistent status panel, and retain each outcome before advancing. Keep Level 1's unscored practice flow distinct from Levels 2–4.

**Tech Stack:** Python, Pygame, the existing event queue, Vosk/sounddevice, pytest. No new runtime dependency or cloud service.

**Spec:** The client's “Clearer Listening / Processing Instructions” request, with the proposed design below. Wording and the 1.5-second outcome hold are recommendations for review.

## Global Constraints

- This plan does not modify application behavior yet.
- Preserve the current working-tree audio fixes, including restored `pilgrimage.wav`, removal of `speaking` from Level 2B, recorded completion prompts 463/464, and exhausted-attempt recording 457.
- Level 1 is practice-only and bypasses ASR; never claim that it is recording or checking an answer.
- Levels 2–4 retain three allowed attempts, the existing correctness threshold, and current scoring/checkpoint rules.
- Preserve the configured `listen_seconds`; do not introduce end-of-speech detection in this change.
- Keep human recordings for Levels 1 and 2; do not introduce TTS status announcements.
- Use text and icons as well as color. Honor pause, abort, shutdown, audio-feedback settings, and automatic continuation.
- No new branch, commit, deployment, or device connection is implied by this planning request.

## Current Findings

1. `ReadingPromptScene._drain_event_queue()` stores `MessageChanged` in `app.message`, but `render()` never draws that message. Changing message wording alone would remain invisible.
2. The thought bubble displayed during listening says **“Waiting…”**, which does not tell the learner to speak. See `bot_sprite.py:draw_thought_bubble()`.
3. `AttemptRunner.run()` emits `StateChanged("listening")` before `VoskASR.transcribe()` prepares the stream, clears old audio, and creates the recognizer. An early learner response can therefore precede the accepted response window.
4. `processing` is emitted only after `transcribe()` returns; slow `FinalResult()` work can still appear to be listening. Silence skips the processing state entirely.
5. `_advance_after_attempt()` represents both retryable failures and exhausted attempts as `retry`. Feedback WAVs can play while the old listening/processing animation is still active.
6. Outcomes are followed by a 0.6-second delay and automatic continuation. `prompt_active` is also cleared before feedback finishes. These mechanisms need a single coordinated turn lifecycle.
7. Level 1's `run()` path plays examples and exposes Replay/Next; it does not listen, validate, or exhaust spoken attempts.

## Proposed Learner Experience

Place one persistent panel below the level/item heading. Reserve layout space for it so it cannot cover the reading item, ELLA, the pause button, or Level 1 controls.

| Phase | Main label | Instruction | Visual cue |
|---|---|---|---|
| Prompt playback | Listen to ELLA | Wait until you see “Speak now.” | Speaker icon, violet |
| ASR preparation | Getting ready… | Please wait. | Small animated dots |
| Response window open | Listening — Speak now | Say it once, then wait. | Microphone icon, teal |
| Recognition/scoring | Processing… | Please wait while ELLA checks your answer. | Thinking icon, blue |
| Correct response | Correct! | Moving to the next item. | Check mark, green |
| Incorrect, attempts remain | Try again | Wait for “Speak now” before trying again. | Retry arrow, amber |
| No input, attempts remain | I didn't hear you | Wait for “Speak now,” then say it once. | Microphone/retry icon, amber |
| Final unsuccessful attempt | Attempts completed | Let's try the next item. | Forward arrow, neutral violet |
| Level 1 practice ready | Your turn to practise | Say the sound. Use Replay to hear it again, then Next. | Practice icon, violet |
| Paused | Paused | Continue when you're ready. | Existing pause modal |
| Microphone/processing error | Please wait — ELLA needs help | Ask the researcher for help. | Error icon; no success/retry implication |

- Show **Attempt 1 of 3**, **Attempt 2 of 3**, or **Attempt 3 of 3** on scored turns. The number describes the current/just-completed attempt; increment it only when the next response window is about to open. Omit the counter in Level 1.
- Keep the existing item visible until its result has been shown for at least **1.5 seconds of unpaused time**, or until feedback playback completes, whichever is longer. This is a minimum total result duration, not an extra 1.5 seconds after a long recording.
- Publish the result label before playing praise, retry coaching, or WAV 457. During coaching, add a secondary “Listen to ELLA; wait for Speak now” instruction without displaying a live microphone cue.
- Display the next item or open results only after the outcome hold and feedback finish. Finalize and save the scored attempt before the hold so leaving the screen cannot lose a completed response or create an extra attempt on resume. Keep the previous item visible using the status event's item snapshot while the saved session already points to its next valid position. Show “Listen to ELLA”/“Getting ready” for the next turn before “Listening.”
- Replace the misleading reading-screen “Waiting…” bubble with this status panel. Do not change unrelated uses of ELLA's bubble.
- First release uses visual cues and existing recorded prompts. A new chime or voice announcement is optional follow-up work; playing a cue inside the accepted response window could contaminate the answer.
- The response window remains fixed-duration. “Say it once, then wait” is explicit because the app does not yet stop listening automatically when a learner finishes speaking. Evaluate end-of-speech detection separately if repeats persist.

## Review Focus

- Slow microphone initialization and slow Vosk finalization: the displayed phase must match the accepted response window.
- Pause/abort during preparation, recording, feedback, or the result hold: no consumed attempt or stale “Speak now” after cancellation.
- Silent attempts and the third unsuccessful response: show an accurate outcome and never start a fourth attempt for that item.
- Last item of a sublevel/session and checkpoint resume: preserve the result long enough to read, without advancing or recording twice.
- Long reading text and small Pi screens: status, prompt, ELLA, and controls must remain readable without overlapping.

## Task 1: Expose the ASR Response-Window Lifecycle

**Files:** Modify `src/ella_bot/speech/asr/vosk_engine.py` and `src/ella_bot/speech/asr/simulated.py`; add `tests/test_asr_lifecycle.py`; update the ASR fixture in `tests/test_gui_e2e.py`.

**Interface:** Extend the adapter `transcribe()` signatures with optional keyword callbacks `on_capture_started: Callable[[], None] | None = None` and `on_capture_stopped: Callable[[], None] | None = None`. Existing callers without callbacks continue to work. The callbacks report an accepted response window, not whether the persistent background microphone stream physically exists.

- [x] Write tests `test_capture_started_after_queue_reset_and_recognizer_ready`, `test_capture_stopped_before_final_result`, and `test_cancelled_preparation_does_not_open_response_window`. Use a fake audio queue, recognizer, and clock; assert callback order relative to actual acceptance/finalization, not source text.
- [x] Run `.venv/bin/python -m pytest -q tests/test_asr_lifecycle.py`; verify failures demonstrate the missing callback behavior.
- [x] Emit started only after initialization, recognizer setup, and the final stale-audio purge, immediately before accepting response frames. Emit stopped before `FinalResult()` begins. On errors or cancellation, close any opened window exactly once without treating cancellation as learner silence.
- [x] Update the active simulated adapter and E2E fake to accept and honor the callbacks. Preserve the existing transcript and `is_paused` contracts; do not refactor the duplicate legacy ASR implementations as part of this work.
- [x] Run lifecycle, factory, and simulated-engine/E2E contract tests. Confirm default callers remain compatible.

## Task 2: Publish and Hold a Distinct Learner Outcome

**Files:** Modify `src/ella_bot/core/events.py`, `src/ella_bot/services/attempt_runner.py`, `tests/test_attempt_runner.py`, and `tests/test_level1_practice.py`.

**Interfaces:** Add frozen event `TurnStatusChanged(phase: str, level: str, item_number: int, expected_sentence: str, attempt_number: int | None = None, attempt_limit: int | None = None)`. Phase values are `prompting`, `preparing`, `listening`, `processing`, `correct`, `retry`, `no_input`, `exhausted`, `practice`, and `error`. Existing animation states remain a separate concern.

`AttemptRunner._publish_turn_status(phase: str) -> None` snapshots the current item and derives the attempt number from recorded attempts. `AttemptRunner._wait_for_outcome_hold(started_at: float) -> bool` waits interruptibly until 1.5 seconds of unpaused outcome visibility has elapsed; returns true on abort. These helpers do not change correctness or progression rules.

For scored turns, extract data-only finalization from the existing progression path into `_finalize_scored_attempt(level: str, session, *, heard: str, accuracy: float, wer: float, correct: bool, exhausted: bool) -> SubLevelCompleted | SessionCompleted | None`. It records the attempt, applies the existing progression/completion rules, saves the appropriate reading/results checkpoint (or clears it for final completion), and returns any pending navigation event without playing audio or switching scenes. Snapshot the outcome before calling it. Publish that navigation event only after feedback/hold; if the learner leaves during the hold, the saved session is already consistent and no stale navigation event is emitted. Retain Level 1's existing practice progression.

- [x] Add event-order tests for a correct response, wrong response with retries left, silence, and final failure. Assert `prompting/preparing → listening → processing → outcome`, with no listening indication during example/coaching audio. Use ASR callbacks from Task 1.
- [x] Add tests asserting exactly one evaluation record, no fourth attempt, the same item during retries, and a new displayed item only after the result hold. Include the last sublevel item and final session item.
- [x] Add fake-clock tests for the minimum result duration, long feedback consuming the hold, and pause not consuming visible time. Test that abort before scoring consumes no attempt, while leaving after scoring preserves exactly one finalized result and a valid next reading/results checkpoint without stale navigation. Add a Level 1 test asserting practice status and no capture/processing/scored outcome.
- [x] Run the targeted tests and confirm the new expectations fail against current behavior.
- [x] Emit learner phases from real capture callbacks; emit processing for both speech and silence. Guard callbacks after pause/abort. Snapshot the outcome and finalize the scored attempt exactly once before feedback; retain WAV 457 for exhaustion. Wait before displaying the next item or publishing pending results navigation.
- [x] Retain ownership of the turn through feedback and the hold; clear `prompt_active` in final cleanup rather than immediately after recognition. Derive counters from the pre-finalization snapshot, and keep checkpoints consistent through the data-only finalizer. Distinguish setup/device errors from silent learner attempts.
- [x] Verify Task 1 and runner/practice regression tests together, including the already-added recording fixes.

## Task 3: Draw the Status and Coordinate Automatic Continuation

**Files:** Add `src/ella_bot/ui/pygame_gui/components/turn_status.py` and `tests/test_turn_status.py`; modify `src/ella_bot/ui/pygame_gui/scenes/reading_prompt.py`, `tests/test_reading_prompt_auto_continue.py`, and `tests/test_gui_e2e.py`. Touch `bot_sprite.py` only if needed to suppress the reading-only waiting bubble without affecting other callers.

**Interfaces:** The reading scene owns `_turn_status: TurnStatusChanged | None`. In the component, `status_text(status: TurnStatusChanged) -> tuple[str, str, str]` returns the main label, instruction, and optional attempt-counter text. `draw_turn_status(screen, rect, status, title_font, body_font) -> None` draws text and a phase cue using existing Pygame/fonts/assets. Worker threads enqueue events; only the main thread draws.

- [x] Test the exact learner copy in the design table, absence of an attempt counter for practice, and separate presentations for retry/no-input/exhausted. Assert status is updated through `TurnStatusChanged`, not inferred solely from bot animation or the TTS object's activity flag.
- [x] Test that no additional worker starts while one is alive, during processing/feedback/outcome hold, or while paused. Update the old test that starts a turn merely because the state is `listening` with `prompt_active=False`; a listening label must never serve as permission to begin another capture.
- [x] Test pause, resume, exit, and shutdown so a cancelled worker cannot restore an old listening cue. Preserve existing worker quiescing and event-queue draining.
- [x] Add layout/render tests at 1024×600, 1024×768, and 1280×720, including long Level 4 text, Level 1 Replay/Next, attempt counts, and the pause overlay. Assert non-overlap and readability rather than hard-coding the old prompt rectangles.
- [x] Implement event consumption and the persistent panel. Reserve its height in `_prompt_layout()` and suppress the misleading waiting bubble on this screen. During an outcome, draw the level, item number, and reading text from the event snapshot so the finalized session's next position cannot appear under the previous item's feedback. Keep outcome status stable while recorded feedback is playing.
- [x] Trigger automatic continuation only after the prior turn has finished its feedback/hold and its worker has stopped. Show preparation before the next response window. Continue using existing initial-entry and pause/restart behavior where compatible.
- [x] Run the component, reading-scene, runner, and E2E tests with dummy SDL video/audio drivers. Render screenshots for each phase and the three viewport sizes; inspect their layout before device testing.

## Task 4: Raspberry Pi and Learner Verification

**Files:** Update `scripts/README.md` with the new researcher test sequence once implemented. No deployment is performed by this plan.

- [ ] Run `python scripts/check_recorded_audio.py` and require zero missing recordings before testing recorded levels.
- [ ] Run the full repository test suite with `.venv/bin/python -m pytest -q tests` and appropriate SDL drivers. Compare failures with the current five known baseline failures: the two TTS-expectation tests in `test_attempt_runner.py`, two TTS-expectation tests in `test_level1_practice.py`, and `test_bgm_service_play_pause_stop`. Do not silently report a red suite as passing. Restore any settings-file side effects from existing tests.
- [ ] On the Pi, test one correct response, a wrong first/second response, three wrong responses, three silent responses, a slow answer, and a deliberately repeated word. Verify the labels and actual accepted response window agree; do not change scoring to accept repeated speech as part of this feature.
- [ ] Test pause/resume in preparation, listening, processing, feedback, and the result hold. Test the last item, return from results, and restored progress. Verify exactly one active attempt and no unexpected lost/extra attempt.
- [ ] Verify Level 1 displays practice instructions only, and Levels 1/2 retain human voice for the relevant examples and feedback. Test audio feedback disabled to ensure the visual instructions remain sufficient.
- [ ] Observe a short researcher-led learner session using the same configured response duration. Record whether the learner starts before the prompt ends, repeats the item within one response window, or asks whether ELLA is listening. Compare with the previous interface; decide with the researchers whether further audio cues or end-of-speech work are needed.

## Acceptance and Follow-Up

- The screen clearly tells the learner when to speak once and when to wait.
- The listening cue appears only while the answer window is open; processing covers recognition finalization as well as scoring.
- Correct, retryable failure, no input, and exhausted attempts have distinct readable outcomes; exhaustion never looks like success.
- Results remain readable before automatic continuation or results navigation.
- Level 1 practice never claims to evaluate a spoken answer.
- No additional TTS status prompt, scoring change, attempt-limit change, or microphone-duration change is introduced.
- Pi and learner verification are required before claiming the observed confusion is resolved. A repeated word could still have other causes; this plan does not assume unclear status is the only one.

Optional later work, based on observation: an accessible start/end sound outside accepted audio, a prerecorded instruction, or separately designed end-of-speech detection. These are outside the first implementation.
