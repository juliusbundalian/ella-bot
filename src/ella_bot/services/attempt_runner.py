from __future__ import annotations

import re
import time
import traceback
from dataclasses import dataclass
from typing import Callable

from ella_bot.core.events import StateChanged, MessageChanged, ErrorOccurred, AttemptReady
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

        if self.app.audio_feedback and self.app.tts is not None:
            try:
                if self._is_paused():
                    return
                announcement = self.app.session.build_start_announcement()
                target_item = self.app.session.expected_sentence.strip()
                target_override = self.app.pronunciation_overrides.get(target_item.lower(), target_item)
                pattern = re.compile(rf'\b{re.escape(target_item)}\b', re.IGNORECASE)
                announcement_with_overrides = pattern.sub(target_override, announcement)
                self.app.tts.speak(announcement_with_overrides)
            except Exception as exc:
                print(f"[DEBUG] Intro TTS Error: {exc}")
                self.app.event_queue.put(ErrorOccurred(str(exc)))

        self.app.event_queue.put(StateChanged("listening"))
        self.app.event_queue.put(MessageChanged(""))

        try:
            target_sentence = self.app.session.expected_sentence
            print(f"[DEBUG] Starting ASR transcription for: {target_sentence}")
            asr_result = self.app.asr.transcribe(expected_sentence=target_sentence)
            print(f"[DEBUG] Transcription finished. Result: '{asr_result.transcript}'")

            if self._is_paused():
                self.app.prompt_active = False
                self.app.event_queue.put(StateChanged("idle"))
                self.app.event_queue.put(MessageChanged(""))
                return

            self.app.prompt_active = False
            self.app.event_queue.put(StateChanged("processing"))
            self.app.event_queue.put(MessageChanged("Validating your reading..."))

            print("[DEBUG] Starting validation...")
            validation = validate_spoken_text(target_sentence, asr_result.transcript)
            print(f"\n{'='*60}")
            print(f"Expected: {target_sentence}")
            print(f"You said:  {asr_result.transcript}")
            print(f"Accuracy: {validation.accuracy:.1%}, WER: {validation.wer:.2f}")
            print(f"{'='*60}\n")
            spoken_tokens = normalize(asr_result.transcript)
            confidences = [w.confidence for w in asr_result.words][: len(spoken_tokens)]
            conf_map = spoken_word_confidence_map(spoken_tokens, confidences)
            feedback = build_feedback(validation=validation, spoken_confidence_by_word=conf_map)
            print(f"[DEBUG] Validation finished. Accuracy: {validation.accuracy:.2f}")

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
                    print(f"[DEBUG] Speaking: {line}")
                    self.app.tts.speak(line)
                print("[DEBUG] Audio feedback finished.")

            if feedback.level_message == "Correct!":
                self.app.session.completed_in_level = min(
                    self.app.session.completed_in_level + 1, self.app.session.level_goal
                )
                self.app.event_queue.put(StateChanged("success"))
            else:
                self.app.event_queue.put(StateChanged("retry"))

            if self.app.session.try_level_up(validation.accuracy):
                level_name = self.app.session.display_level_name()
                if self.app.audio_feedback and self.app.tts is not None:
                    if self._is_paused():
                        return
                    self.app.tts.speak(
                        f"Wow, you leveled up! Welcome to the {level_name} level. You're doing amazing!"
                    )
                self.app.event_queue.put(MessageChanged(f"Level up! You reached {level_name}!"))
            else:
                if feedback.level_message.startswith(
                    ("Excellent", "Great", "Wonderful", "That's right", "Perfect")
                ):
                    self.app.session.advance_to_next_sentence()
                    self.app.event_queue.put(MessageChanged("Nice work! Moving to the next one."))
                else:
                    self.app.event_queue.put(MessageChanged("Give it another try!"))

            time.sleep(0.6)
            self.app.event_queue.put(StateChanged("listening"))
            self.app.event_queue.put(MessageChanged(""))

        except Exception as exc:
            print("\n[!!!] WORKER THREAD CRITICAL ERROR:")
            traceback.print_exc()
            error_msg = str(exc)
            tb = traceback.format_exc()
            print(f"\n{'='*60}")
            print("ERROR DURING VALIDATION:")
            print(tb)
            print(f"{'='*60}\n")
            self.error_log.append(error_msg)
            if len(self.error_log) > self.max_errors:
                self.error_log.pop(0)

            self.app.prompt_active = False
            self.app.event_queue.put(StateChanged("retry"))
            self.app.event_queue.put(MessageChanged(f"Error: {error_msg}"))
            self.app.event_queue.put(ErrorOccurred(error_msg))
            print(f"DEBUG: Worker thread encountered error: {error_msg}")
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
