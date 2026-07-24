from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass
from typing import Callable

from ella_bot.core.constants import max_attempts_for_level
from ella_bot.core.events import (
    StateChanged, MessageChanged, ErrorOccurred, AttemptReady,
    SubLevelCompleted, SessionCompleted,
)
from ella_bot.utils.logging import get_logger
from ella_bot.validation.feedback import (
    FeedbackResult,
    build_feedback,
    build_spoken_feedback_with_coaching,
    overrides_for_level,
)
from ella_bot.validation.validators import (
    ValidationResult,
    validate_spoken_text,
    normalize,
    spoken_word_confidence_map,
    build_highlighted_expected,
)

logger = get_logger(__name__)

_EXHAUSTION_PHRASES = [
    "That's okay! Keep going, you're doing great!",
    "Nice try! Let's move to the next one.",
    "Don't worry, we'll come back to tricky ones. Keep it up!",
    "Good effort! Moving on.",
    "That one was tough! You're still doing amazing.",
]

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


@dataclass
class AttemptViewModel:
    expected_sentence: str
    spoken_sentence: str
    highlighted_expected: str
    validation: ValidationResult
    feedback: FeedbackResult


class AttemptRunner:
    """Runs one reading attempt (announce -> listen -> score -> speak feedback)."""

    def __init__(self, app, is_paused: Callable[[], bool]) -> None:
        self.app = app
        self._is_paused = is_paused
        self.error_log: list[str] = []
        self.max_errors = 5
        self._item_attempt_count: int = 0
        self._current_item_key: tuple = ("", 0)
        self._abort_requested = False

    def abort(self) -> None:
        self._abort_requested = True

    def _wait_if_paused(self) -> bool:
        """Wait if paused. Returns True if aborted, False otherwise."""
        while self._is_paused():
            if self._abort_requested:
                return True
            time.sleep(0.1)
        return self._abort_requested

    def _speak(self, text: str) -> bool:
        """Speak text. Returns True if aborted."""
        if self._abort_requested:
            return True
        self.app.event_queue.put(StateChanged("speaking"))
        rate = None
        if text.startswith("SLOW: "):
            text = text[6:].strip()
            rate = int(self.app.tts.config.rate * 0.7)
        self.app.tts.speak(text, rate=rate)
        return self._abort_requested

    def run(self) -> None:
        self.app.event_queue.put(StateChanged("speaking"))
        self.app.event_queue.put(MessageChanged(""))

        is_retry = False
        target_item = self.app.session.expected_sentence.strip()
        if hasattr(self.app.session, "last_announced_sentence"):
            if self.app.session.last_announced_sentence == target_item:
                is_retry = True
            else:
                self.app.session.last_announced_sentence = target_item

        if not is_retry and self.app.audio_feedback and self.app.tts is not None:
            try:
                if self._wait_if_paused():
                    return
                announcement = self.app.session.build_start_announcement()
                level_overrides = overrides_for_level(
                    self.app.session.current_level, self.app.pronunciation_overrides
                )
                target_override = level_overrides.get(target_item.lower(), target_item)
                if "phonemes:" in target_override:
                    pattern = re.compile(rf'\b{re.escape(target_item)}\b', re.IGNORECASE)
                    parts = pattern.split(announcement, maxsplit=1)
                    if len(parts) == 2:
                        intro_part = parts[0].strip().rstrip(",").rstrip(".")
                        if self._speak(intro_part):
                            return
                        if self._speak(target_override):
                            return
                    else:
                        if self._speak(announcement):
                            return
                else:
                    pattern = re.compile(rf'\b{re.escape(target_item)}\b', re.IGNORECASE)
                    announcement_with_overrides = pattern.sub(target_override, announcement)
                    if self._speak(announcement_with_overrides):
                        return
            except Exception as exc:
                logger.debug("Intro TTS error: %s", exc)
                self.app.event_queue.put(ErrorOccurred(str(exc)))

        if self._wait_if_paused():
            return

        try:
            target_sentence = self.app.session.expected_sentence
            logger.debug("Starting ASR transcription for: %s", target_sentence)

            while True:
                if self._abort_requested:
                    return

                self.app.event_queue.put(StateChanged("listening"))
                self.app.event_queue.put(MessageChanged(""))

                asr_result = self.app.asr.transcribe(expected_sentence=target_sentence, is_paused=self._is_paused)
                logger.debug("Transcription finished. Result: %r", asr_result.transcript)

                if self._is_paused():
                    if self._wait_if_paused():
                        return
                    continue
                break

            self.app.prompt_active = False

            if self._wait_if_paused():
                return

            if not asr_result.transcript.strip():
                self._handle_no_input()
                return

            self.app.event_queue.put(StateChanged("processing"))
            self.app.event_queue.put(MessageChanged("Validating your reading..."))

            logger.debug("Starting validation")
            spoken_tokens = normalize(asr_result.transcript)
            confidences = [w.confidence for w in asr_result.words][: len(spoken_tokens)]
            is_strict = self.app.current_level in ["3", "4"]

            validation = validate_spoken_text(
                target_sentence,
                asr_result.transcript,
                spoken_confidences=confidences,
                strict_fluency=is_strict
            )

            logger.info(
                "Expected: %r | Said: %r | Accuracy: %.1f%% | WER: %.2f",
                target_sentence,
                asr_result.transcript,
                validation.accuracy * 100,
                validation.wer,
            )
            conf_map = spoken_word_confidence_map(spoken_tokens, confidences)
            feedback = build_feedback(validation=validation, spoken_confidence_by_word=conf_map)

            if self._wait_if_paused():
                return

            highlighted = build_highlighted_expected(validation.alignment)
            view_model = AttemptViewModel(
                expected_sentence=self.app.session.expected_sentence,
                spoken_sentence=asr_result.transcript,
                highlighted_expected=highlighted,
                validation=validation,
                feedback=feedback,
            )
            self.app.event_queue.put(AttemptReady(view_model))

            session = self.app.session
            level = session.current_level
            correct = validation.accuracy >= 0.95

            exhausted = self._register_attempt(level, session, correct)

            if self.app.audio_feedback and self.app.tts is not None:
                if exhausted:
                    if self._speak(random.choice(_EXHAUSTION_PHRASES)):
                        return
                else:
                    try:
                        spoken_lines = build_spoken_feedback_with_coaching(
                            feedback=feedback,
                            overrides=overrides_for_level(
                                level, self.app.pronunciation_overrides
                            ),
                            expected_sentence=self.app.session.expected_sentence,
                            max_hints=2,
                            validation=validation,
                        )
                    except Exception:
                        spoken_lines = [feedback.level_message]

                    for line in spoken_lines:
                        if self._wait_if_paused():
                            return
                        self.app.event_queue.put(MessageChanged("Speaking feedback..."))
                        logger.debug("Speaking: %s", line)
                        if self._speak(line):
                            return
                    logger.debug("Audio feedback finished")

            if self._wait_if_paused():
                return

            self.app.evaluation.record_attempt(
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

            if self._wait_if_paused():
                return
            time.sleep(0.6)
            if self._wait_if_paused():
                return
            self.app.event_queue.put(StateChanged("listening"))
            self.app.event_queue.put(MessageChanged(""))

        except Exception as exc:
            logger.exception("Attempt worker crashed")
            error_msg = str(exc)
            self.error_log.append(error_msg)
            if len(self.error_log) > self.max_errors:
                self.error_log.pop(0)

            self.app.prompt_active = False
            self.app.event_queue.put(StateChanged("retry"))
            self.app.event_queue.put(MessageChanged(f"Error: {error_msg}"))
            self.app.event_queue.put(ErrorOccurred(error_msg))
        finally:
            self.app.prompt_active = False

    def _register_attempt(self, level: str, session, correct: bool) -> bool:
        """Increment the per-item attempt counter and report whether the item is exhausted.

        The counter resets whenever the item position changes. Returns True when a
        non-correct attempt has reached the level's attempt limit.
        """
        item_key = (level, session.current_item_number())
        if item_key != self._current_item_key:
            self._current_item_key = item_key

        recorded_attempts = 0
        if level in self.app.evaluation._attempts:
            recorded_attempts = sum(1 for a in self.app.evaluation._attempts[level] if a.item == session.current_item_number())
        self._item_attempt_count = recorded_attempts + 1

        max_attempts = max_attempts_for_level(level)
        return not correct and self._item_attempt_count >= max_attempts

    def _advance_after_attempt(
        self, level: str, session, correct: bool, exhausted: bool
    ) -> bool:
        """Apply post-attempt progression shared by scored and silent turns.

        Side effects a direct caller must know about:
        - Bumps ``session.completed_in_level`` (capped at ``session.level_goal``)
          when the item is finished (correct or exhausted).
        - Resets ``self._item_attempt_count`` to 0 when the item is finished.
        - Emits ``StateChanged("success")`` on a correct attempt, otherwise
          ``StateChanged("retry")``.
        - Runs the sublevel/tier/session completion cascade when
          ``session.current_sublevel_complete()`` is True: calls
          ``evaluation.finish_sublevel``, ``evaluation.finish_tier``, and/or
          ``evaluation.finish_session`` as appropriate, emits TTS and the
          relevant ``SubLevelCompleted`` / ``SessionCompleted`` event, then
          returns True so the caller exits immediately (scene transition).
        - Otherwise, when the item is finished (correct or exhausted) without a
          scene transition, calls ``session.advance_to_next_sentence()`` and
          returns False.
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
                    if self.app.audio_feedback and self.app.tts is not None:
                        if self._speak("Incredible! You finished every level. Let's see how you did!"):
                            return True
                    self.app.event_queue.put(SessionCompleted(cumulative))
                else:
                    if self.app.audio_feedback and self.app.tts is not None:
                        if self._speak(f"Wow, you finished Level {tier}! You're doing amazing!"):
                            return True
                    self.app.event_queue.put(SubLevelCompleted(tier_result, "tier"))
            else:
                if self.app.audio_feedback and self.app.tts is not None:
                    if self._speak("Great job! Let's see how you did!"):
                        return True
                self.app.event_queue.put(SubLevelCompleted(sub_result, "sublevel"))
            return True

        if correct or exhausted:
            session.advance_to_next_sentence()
        return False

    def _handle_no_input(self) -> None:
        """Respond to a silent turn (empty transcript).

        Counts as an attempt — same progression bookkeeping as a wrong answer —
        but speaks a dedicated no-input phrase instead of pronunciation coaching,
        and never emits an AttemptReady view model (nothing was spoken to show).
        """
        session = self.app.session
        level = session.current_level

        if self._wait_if_paused():
            return

        exhausted = self._register_attempt(level, session, correct=False)
        advancing = exhausted  # silence is never correct, so the item only moves on when exhausted

        if self.app.audio_feedback and self.app.tts is not None:
            phrase = random.choice(
                _NO_INPUT_MOVE_ON_PHRASES if advancing else _NO_INPUT_PHRASES
            )
            if self._speak(phrase):
                return

        if self._wait_if_paused():
            return

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

        if self._wait_if_paused():
            return
        time.sleep(0.6)
        if self._wait_if_paused():
            return
        self.app.event_queue.put(StateChanged("listening"))
        self.app.event_queue.put(MessageChanged(""))

    def replay(self) -> None:
        if (
            not self.app.audio_feedback
            or self.app.tts is None
            or self.app.latest_attempt is None
        ):
            return

        feedback = self.app.latest_attempt.feedback
        try:
            lines = build_spoken_feedback_with_coaching(
                feedback=feedback,
                overrides=overrides_for_level(
                    self.app.session.current_level, self.app.pronunciation_overrides
                ),
                expected_sentence=self.app.latest_attempt.expected_sentence,
                max_hints=2,
                validation=self.app.latest_attempt.validation,
            )
        except Exception:
            lines = [feedback.level_message]

        for line in lines:
            if self._wait_if_paused():
                return
            self.app.event_queue.put(MessageChanged("Replaying feedback..."))
            if self._speak(line):
                return

        if self._wait_if_paused():
            return

        if feedback.level_message == "Correct!":
            self.app.event_queue.put(StateChanged("success"))
        else:
            self.app.event_queue.put(StateChanged("retry"))
        self.app.event_queue.put(MessageChanged("Replay finished."))
