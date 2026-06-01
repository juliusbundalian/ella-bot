from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Callable

from ella_bot.core.events import (
    StateChanged, MessageChanged, ErrorOccurred, AttemptReady,
    SubLevelCompleted, SessionCompleted,
)
from ella_bot.utils.logging import get_logger
from ella_bot.validation.feedback import (
    FeedbackResult,
    build_feedback,
    build_spoken_feedback_with_coaching,
)
from ella_bot.validation.validators import (
    ValidationResult,
    validate_spoken_text,
    normalize,
    spoken_word_confidence_map,
    build_highlighted_expected,
)

logger = get_logger(__name__)


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
                if self._is_paused():
                    return
                announcement = self.app.session.build_start_announcement()
                target_override = self.app.pronunciation_overrides.get(target_item.lower(), target_item)
                if "phonemes:" in target_override:
                    pattern = re.compile(rf'\b{re.escape(target_item)}\b', re.IGNORECASE)
                    parts = pattern.split(announcement, maxsplit=1)
                    if len(parts) == 2:
                        intro_part = parts[0].strip().rstrip(",").rstrip(".")
                        self.app.tts.speak(intro_part)
                        self.app.tts.speak(target_override)
                    else:
                        self.app.tts.speak(announcement)
                else:
                    pattern = re.compile(rf'\b{re.escape(target_item)}\b', re.IGNORECASE)
                    announcement_with_overrides = pattern.sub(target_override, announcement)
                    self.app.tts.speak(announcement_with_overrides)
            except Exception as exc:
                logger.debug("Intro TTS error: %s", exc)
                self.app.event_queue.put(ErrorOccurred(str(exc)))

        self.app.event_queue.put(StateChanged("listening"))
        self.app.event_queue.put(MessageChanged(""))

        try:
            target_sentence = self.app.session.expected_sentence
            logger.debug("Starting ASR transcription for: %s", target_sentence)
            asr_result = self.app.asr.transcribe(expected_sentence=target_sentence)
            logger.debug("Transcription finished. Result: %r", asr_result.transcript)

            if self._is_paused():
                self.app.prompt_active = False
                self.app.event_queue.put(StateChanged("idle"))
                self.app.event_queue.put(MessageChanged(""))
                return

            self.app.prompt_active = False
            self.app.event_queue.put(StateChanged("processing"))
            self.app.event_queue.put(MessageChanged("Validating your reading..."))

            logger.debug("Starting validation")
            validation = validate_spoken_text(target_sentence, asr_result.transcript)
            logger.info(
                "Expected: %r | Said: %r | Accuracy: %.1f%% | WER: %.2f",
                target_sentence,
                asr_result.transcript,
                validation.accuracy * 100,
                validation.wer,
            )
            spoken_tokens = normalize(asr_result.transcript)
            confidences = [w.confidence for w in asr_result.words][: len(spoken_tokens)]
            conf_map = spoken_word_confidence_map(spoken_tokens, confidences)
            feedback = build_feedback(validation=validation, spoken_confidence_by_word=conf_map)
            logger.debug("Validation finished. Accuracy: %.2f", validation.accuracy)

            highlighted = build_highlighted_expected(validation.alignment)
            view_model = AttemptViewModel(
                expected_sentence=self.app.session.expected_sentence,
                spoken_sentence=asr_result.transcript,
                highlighted_expected=highlighted,
                validation=validation,
                feedback=feedback,
            )
            self.app.event_queue.put(AttemptReady(view_model))

            if self.app.audio_feedback and self.app.tts is not None:
                try:
                    spoken_lines = build_spoken_feedback_with_coaching(
                        feedback=feedback,
                        overrides=self.app.pronunciation_overrides,
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

            session = self.app.session
            evaluation = self.app.evaluation
            level = session.current_level
            correct = feedback.level_message.startswith(
                ("Excellent", "Great", "Wonderful", "That's right", "Perfect")
            )

            evaluation.record_attempt(
                level=level,
                item=session.current_item_number(),
                expected=session.expected_sentence,
                heard=asr_result.transcript,
                accuracy=validation.accuracy,
                wer=validation.wer,
                correct=correct,
            )

            if correct:
                session.completed_in_level = min(
                    session.completed_in_level + 1, session.level_goal
                )
                self.app.event_queue.put(StateChanged("success"))
            else:
                self.app.event_queue.put(StateChanged("retry"))

            if session.current_sublevel_complete():
                tier = session.tier_of(level)
                sub_result = evaluation.finish_sublevel(level)
                if session.is_last_sublevel_of_tier(level):
                    tier_result = evaluation.finish_tier(tier)
                    if session.is_last_tier(tier):
                        cumulative = evaluation.finish_session()
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
                return

            if feedback.level_message.startswith(
                ("Excellent", "Great", "Wonderful", "That's right", "Perfect")
            ):
                session.advance_to_next_sentence()
                self.app.event_queue.put(MessageChanged("Nice work! Moving to the next one."))
            else:
                self.app.event_queue.put(MessageChanged("Give it another try!"))

            time.sleep(0.6)
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

    def replay(self) -> None:
        if (
            self._is_paused()
            or not self.app.audio_feedback
            or self.app.tts is None
            or self.app.latest_attempt is None
        ):
            return

        feedback = self.app.latest_attempt.feedback
        try:
            lines = build_spoken_feedback_with_coaching(
                feedback=feedback,
                overrides=self.app.pronunciation_overrides,
                expected_sentence=self.app.latest_attempt.expected_sentence,
                max_hints=2,
            )
        except Exception:
            lines = [feedback.level_message]

        for line in lines:
            self.app.event_queue.put(StateChanged("speaking"))
            self.app.event_queue.put(MessageChanged("Replaying feedback..."))
            self.app.tts.speak(line)

        if feedback.level_message == "Correct!":
            self.app.event_queue.put(StateChanged("success"))
        else:
            self.app.event_queue.put(StateChanged("retry"))
        self.app.event_queue.put(MessageChanged("Replay finished."))
