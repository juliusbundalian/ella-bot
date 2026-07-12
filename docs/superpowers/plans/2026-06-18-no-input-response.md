# No-Input (Silent Turn) Response Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Ella respond with a gentle, dedicated re-prompt when the child gives no input (empty ASR transcript) instead of treating silence as a wrong answer with pronunciation coaching.

**Architecture:** Branch inside `AttemptRunner.run()` right after transcription. First extract the existing post-attempt progression into two private helpers (`_register_attempt`, `_advance_after_attempt`) so the scored path and the new silent path share identical bookkeeping. Then add a `_handle_no_input` method that runs that bookkeeping, speaks a no-input phrase, records the attempt, and advances — without scoring or emitting an `AttemptReady` view model.

**Tech Stack:** Python, `pytest`, `unittest.mock`. The runner communicates with the UI via an event queue (`StateChanged`, `MessageChanged`, `AttemptReady`, `SubLevelCompleted`, `SessionCompleted`).

**Spec:** `docs/superpowers/specs/2026-06-18-no-input-response-design.md`

---

## File Structure

- `src/ella_bot/services/attempt_runner.py` — all production changes. Add two phrase lists, two extracted progression helpers, and a `_handle_no_input` method; add a one-line branch in `run()`.
- `tests/test_attempt_runner.py` — extend the `_FakeASRResult` test double to accept a transcript argument; add silent-turn tests.

No new files. This keeps the silence concern in the module that already owns `_EXHAUSTION_PHRASES`, and keeps scoring (`validators.py`, `feedback.py`) untouched.

---

### Task 1: Extract progression helpers (behavior-preserving refactor)

This task introduces no new behavior. The existing test suite is the safety net: it must pass unchanged before and after.

**Files:**
- Modify: `src/ella_bot/services/attempt_runner.py`
- Test (safety net, not modified): `tests/test_attempt_runner.py`

- [ ] **Step 1: Confirm the existing suite is green before refactoring**

Run: `python -m pytest tests/test_attempt_runner.py -v`
Expected: PASS — all tests green. (This is the baseline the refactor must preserve.)

- [ ] **Step 2: Add the two helper methods**

Add these two methods to the `AttemptRunner` class, immediately after the `run()` method and before `replay()` (i.e. just before the line `def replay(self) -> None:`). They reproduce the existing inline logic exactly.

```python
    def _register_attempt(self, level: str, session, correct: bool) -> bool:
        """Increment the per-item attempt counter and report whether the item is exhausted.

        The counter resets whenever the item position changes. Returns True when a
        non-correct attempt has reached the level's attempt limit.
        """
        item_key = (level, session.current_item_number())
        if item_key != self._current_item_key:
            self._current_item_key = item_key
            self._item_attempt_count = 0
        self._item_attempt_count += 1
        max_attempts = max_attempts_for_level(level)
        return not correct and self._item_attempt_count >= max_attempts

    def _advance_after_attempt(
        self, level: str, session, correct: bool, exhausted: bool
    ) -> bool:
        """Apply post-attempt progression shared by scored and silent turns.

        Bumps level progress when the item is finished, emits the success/retry
        state, and runs the sublevel/tier/session completion cascade. Returns True
        when a scene/session transition was emitted and the caller should return.
        """
        if correct or exhausted:
            session.completed_in_level = min(
                session.completed_in_level + 1, session.level_goal
            )
            self._item_attempt_count = 0

        if correct:
            self.app.event_queue.put(StateChanged("success"))
        else:
            self.app.event_queue.put(StateChanged("retry"))

        if session.current_sublevel_complete():
            tier = session.tier_of(level)
            sub_result = self.app.evaluation.finish_sublevel(level)
            if session.is_last_sublevel_of_tier(level):
                tier_result = self.app.evaluation.finish_tier(tier)
                if session.is_last_tier(tier):
                    cumulative = self.app.evaluation.finish_session()
                    if self.app.audio_feedback and self.app.tts is not None and not self._is_paused():
                        self.app.event_queue.put(StateChanged("speaking"))
                        self.app.tts.speak(
                            "Incredible! You finished every level. Let's see how you did!"
                        )
                        self.app.event_queue.put(StateChanged("idle"))
                    self.app.event_queue.put(SessionCompleted(cumulative))
                else:
                    if self.app.audio_feedback and self.app.tts is not None and not self._is_paused():
                        self.app.event_queue.put(StateChanged("speaking"))
                        self.app.tts.speak(
                            f"Wow, you finished Level {tier}! You're doing amazing!"
                        )
                        self.app.event_queue.put(StateChanged("idle"))
                    self.app.event_queue.put(SubLevelCompleted(tier_result, "tier"))
            else:
                if self.app.audio_feedback and self.app.tts is not None and not self._is_paused():
                    self.app.event_queue.put(StateChanged("speaking"))
                    self.app.tts.speak("Great job! Let's see how you did!")
                    self.app.event_queue.put(StateChanged("idle"))
                self.app.event_queue.put(SubLevelCompleted(sub_result, "sublevel"))
            return True

        if correct or exhausted:
            session.advance_to_next_sentence()
        return False
```

- [ ] **Step 3: Replace the inline progression block in `run()` with calls to the helpers**

In `run()`, find the block that currently starts at:

```python
            session = self.app.session
            evaluation = self.app.evaluation
            level = session.current_level
            correct = validation.accuracy >= 0.95
```

and runs all the way through the end of the `try` body:

```python
            time.sleep(0.6)
            self.app.event_queue.put(StateChanged("listening"))
            self.app.event_queue.put(MessageChanged(""))
```

Replace that entire block with the following (the feedback-speaking section in the middle is unchanged from the original; only the attempt-tracking, completion cascade, and advance lines are now delegated to the helpers):

```python
            session = self.app.session
            evaluation = self.app.evaluation
            level = session.current_level
            correct = validation.accuracy >= 0.95

            exhausted = self._register_attempt(level, session, correct)

            if self.app.audio_feedback and self.app.tts is not None:
                if exhausted:
                    if not self._is_paused():
                        self.app.event_queue.put(StateChanged("speaking"))
                        self.app.tts.speak(random.choice(_EXHAUSTION_PHRASES))
                        self.app.event_queue.put(StateChanged("idle"))
                else:
                    try:
                        spoken_lines = build_spoken_feedback_with_coaching(
                            feedback=feedback,
                            overrides=overrides_for_level(
                                level, self.app.pronunciation_overrides
                            ),
                            expected_sentence=self.app.session.expected_sentence,
                            max_hints=2,
                        )
                    except Exception:
                        spoken_lines = [feedback.level_message]

                    for line in spoken_lines:
                        if self._is_paused():
                            break
                        self.app.event_queue.put(StateChanged("speaking"))
                        self.app.event_queue.put(MessageChanged("Speaking feedback..."))
                        logger.debug("Speaking: %s", line)
                        self.app.tts.speak(line)
                        self.app.event_queue.put(StateChanged("idle"))
                    logger.debug("Audio feedback finished")

            evaluation.record_attempt(
                level=level,
                item=session.current_item_number(),
                expected=session.expected_sentence,
                heard=asr_result.transcript,
                accuracy=validation.accuracy,
                wer=validation.wer,
                correct=correct,
            )

            if self._advance_after_attempt(level, session, correct, exhausted):
                return

            if correct:
                self.app.event_queue.put(MessageChanged("Nice work! Moving to the next one."))
            elif exhausted:
                self.app.event_queue.put(MessageChanged("Let's move on."))
            else:
                self.app.event_queue.put(MessageChanged("Give it another try!"))

            time.sleep(0.6)
            self.app.event_queue.put(StateChanged("listening"))
            self.app.event_queue.put(MessageChanged(""))
```

- [ ] **Step 4: Run the suite to confirm behavior is unchanged**

Run: `python -m pytest tests/test_attempt_runner.py -v`
Expected: PASS — the same tests that passed in Step 1 still pass. No test changes were needed.

- [ ] **Step 5: Commit**

```bash
git add src/ella_bot/services/attempt_runner.py
git commit -m "refactor: extract attempt progression helpers in AttemptRunner

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Add the no-input (silent turn) response

**Files:**
- Modify: `src/ella_bot/services/attempt_runner.py`
- Test: `tests/test_attempt_runner.py`

- [ ] **Step 1: Make the ASR test double accept a transcript**

In `tests/test_attempt_runner.py`, replace the existing `_FakeASRResult` class:

```python
class _FakeASRResult:
    transcript = "a"
    words = []
```

with a version that defaults to `"a"` (so existing callers using `_FakeASRResult()` are unaffected) but allows an empty transcript:

```python
class _FakeASRResult:
    def __init__(self, transcript: str = "a"):
        self.transcript = transcript
        self.words = []
```

- [ ] **Step 2: Run the existing suite to confirm the test-double change is non-breaking**

Run: `python -m pytest tests/test_attempt_runner.py -v`
Expected: PASS — all existing tests still pass (they call `_FakeASRResult()` with no argument, which now defaults to `"a"`).

- [ ] **Step 3: Write the failing silent-turn tests**

Append these tests to `tests/test_attempt_runner.py`. Add `AttemptReady` to the imports at the top of the file (it lives in `ella_bot.core.events`); the existing import line is `from ella_bot.core.events import SubLevelCompleted` — change it to:

```python
from ella_bot.core.events import SubLevelCompleted, AttemptReady
```

Then append the tests:

```python
def _drain(app):
    events = []
    while not app.event_queue.empty():
        events.append(app.event_queue.get_nowait())
    return events


def test_silent_turn_tier1_advances_with_move_on_phrase(tmp_path):
    app = _make_app_with_tts(tmp_path, {"1a": ["a", "b"]}, "1a")
    app.asr.transcribe.return_value = _FakeASRResult("")

    runner = AttemptRunner(app, is_paused=lambda: False)
    assert app.session.expected_sentence == "a"
    runner.run()

    # Tier 1 advances after a single non-correct turn.
    assert app.session.expected_sentence == "b"
    assert app.session.completed_in_level == 1
    # Ella speaks a move-on phrase, not a re-prompt.
    assert any(line in runner_mod._NO_INPUT_MOVE_ON_PHRASES for line in _spoken(app))
    # The attempt is recorded with an empty heard transcript.
    assert app.evaluation._attempts["1a"][0].heard == ""


def test_silent_turn_tier2_with_tries_left_stays_with_reprompt(tmp_path):
    app = _make_app_with_tts(tmp_path, {"2a": ["item one", "item two"]}, "2a")
    app.asr.transcribe.return_value = _FakeASRResult("")

    runner = AttemptRunner(app, is_paused=lambda: False)
    runner.run()

    # Tier 2 keeps the same item until the attempt limit is reached.
    assert app.session.expected_sentence == "item one"
    assert app.session.completed_in_level == 0
    # Ella speaks a gentle re-prompt, not a move-on phrase.
    assert any(line in runner_mod._NO_INPUT_PHRASES for line in _spoken(app))


def test_silent_turn_tier2_final_attempt_advances(tmp_path):
    app = _make_app_with_tts(tmp_path, {"2a": ["item one", "item two"]}, "2a")
    app.asr.transcribe.return_value = _FakeASRResult("")

    runner = AttemptRunner(app, is_paused=lambda: False)
    runner.run()  # attempt 1 — re-prompt
    runner.run()  # attempt 2 — re-prompt
    runner.run()  # attempt 3 — exhausted, advance

    assert app.session.expected_sentence == "item two"
    assert app.session.completed_in_level == 1
    assert any(line in runner_mod._NO_INPUT_MOVE_ON_PHRASES for line in _spoken(app))


def test_silent_turn_speaks_no_coaching(tmp_path):
    app = _make_app_with_tts(tmp_path, {"2a": ["item one", "item two"]}, "2a")
    app.asr.transcribe.return_value = _FakeASRResult("")

    AttemptRunner(app, is_paused=lambda: False).run()

    # No pronunciation-coaching lines on a silent turn.
    spoken = _spoken(app)
    assert not any("Now you try!" in line for line in spoken)
    assert not any("let me read" in line.lower() for line in spoken)


def test_silent_turn_emits_no_attempt_ready(tmp_path):
    app = _make_app_with_tts(tmp_path, {"2a": ["item one", "item two"]}, "2a")
    app.asr.transcribe.return_value = _FakeASRResult("")

    AttemptRunner(app, is_paused=lambda: False).run()

    assert not any(isinstance(e, AttemptReady) for e in _drain(app))
```

- [ ] **Step 4: Run the new tests to verify they fail**

Run: `python -m pytest tests/test_attempt_runner.py -k silent -v`
Expected: FAIL — `AttributeError` on `runner_mod._NO_INPUT_PHRASES` / `_NO_INPUT_MOVE_ON_PHRASES` (the phrase lists and the silent-turn branch don't exist yet). The tests for advancing will also fail because silence currently runs full scoring and coaching.

- [ ] **Step 5: Add the no-input phrase lists**

In `src/ella_bot/services/attempt_runner.py`, add these two lists immediately after the existing `_EXHAUSTION_PHRASES` list:

```python
_NO_INPUT_PHRASES = [
    "I didn't quite hear you. Let's try again!",
    "Hmm, I didn't hear anything. Give it a try!",
    "Let's try that again — I'm listening!",
    "Oops, I didn't catch that. Have another go!",
]

_NO_INPUT_MOVE_ON_PHRASES = [
    "I didn't quite hear you that time. Let's try a new one!",
    "That's okay! Let's move on to the next one.",
    "No worries — let's try a different one!",
]
```

- [ ] **Step 6: Add the `_handle_no_input` method**

Add this method to the `AttemptRunner` class, immediately after `_advance_after_attempt` (added in Task 1):

```python
    def _handle_no_input(self) -> None:
        """Respond to a silent turn (empty transcript).

        Counts as an attempt — same progression bookkeeping as a wrong answer —
        but speaks a dedicated no-input phrase instead of pronunciation coaching,
        and never emits an AttemptReady view model (nothing was spoken to show).
        """
        session = self.app.session
        level = session.current_level

        exhausted = self._register_attempt(level, session, correct=False)
        advancing = exhausted  # silence is never correct, so the item only moves on when exhausted

        if self.app.audio_feedback and self.app.tts is not None and not self._is_paused():
            phrase = random.choice(
                _NO_INPUT_MOVE_ON_PHRASES if advancing else _NO_INPUT_PHRASES
            )
            self.app.event_queue.put(StateChanged("speaking"))
            self.app.tts.speak(phrase)
            self.app.event_queue.put(StateChanged("idle"))

        self.app.evaluation.record_attempt(
            level=level,
            item=session.current_item_number(),
            expected=session.expected_sentence,
            heard="",
            accuracy=0.0,
            wer=1.0,
            correct=False,
        )

        if self._advance_after_attempt(level, session, correct=False, exhausted=exhausted):
            return

        if advancing:
            self.app.event_queue.put(MessageChanged("Let's move on."))
        else:
            self.app.event_queue.put(MessageChanged("I didn't hear you — let's try again!"))

        time.sleep(0.6)
        self.app.event_queue.put(StateChanged("listening"))
        self.app.event_queue.put(MessageChanged(""))
```

- [ ] **Step 7: Add the silent-turn branch in `run()`**

In `run()`, find the block right after the post-transcription pause check:

```python
            self.app.prompt_active = False
            self.app.event_queue.put(StateChanged("processing"))
            self.app.event_queue.put(MessageChanged("Validating your reading..."))
```

Insert the silent-turn branch between setting `prompt_active` and the `"processing"` state change, so silence never shows the "Validating your reading..." message or runs scoring:

```python
            self.app.prompt_active = False

            if not asr_result.transcript.strip():
                self._handle_no_input()
                return

            self.app.event_queue.put(StateChanged("processing"))
            self.app.event_queue.put(MessageChanged("Validating your reading..."))
```

- [ ] **Step 8: Run the new tests to verify they pass**

Run: `python -m pytest tests/test_attempt_runner.py -k silent -v`
Expected: PASS — all five silent-turn tests pass.

- [ ] **Step 9: Run the full module suite to confirm no regressions**

Run: `python -m pytest tests/test_attempt_runner.py -v`
Expected: PASS — all existing and new tests pass.

- [ ] **Step 10: Commit**

```bash
git add src/ella_bot/services/attempt_runner.py tests/test_attempt_runner.py
git commit -m "feat: dedicated response when child gives no input

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- Trigger = empty transcript only → Task 2 Step 7 (`if not asr_result.transcript.strip()`).
- Counts as an attempt (counter, advance/exhaust, evaluation record) → `_handle_no_input` calls `_register_attempt`, `record_attempt(heard="")`, and `_advance_after_attempt`.
- Move-on phrase on advancing turn, re-prompt otherwise → `advancing = exhausted` selects the phrase list.
- Skip `AttemptReady` on silence → `_handle_no_input` never emits it; covered by `test_silent_turn_emits_no_attempt_ready`.
- No pronunciation coaching on silence → covered by `test_silent_turn_speaks_no_coaching`.
- Shared progression factored into a helper to prevent drift → Task 1 (`_register_attempt`, `_advance_after_attempt`), reused by both paths.

**Placeholder scan:** No TBD/TODO; every code step shows complete code and exact commands.

**Type/name consistency:** `_register_attempt(level, session, correct) -> bool`, `_advance_after_attempt(level, session, correct, exhausted) -> bool`, and `_handle_no_input()` are referenced with the same signatures everywhere. Phrase list names `_NO_INPUT_PHRASES` / `_NO_INPUT_MOVE_ON_PHRASES` match between production code and tests. `record_attempt` keyword args match the signature in `evaluation.py`.
