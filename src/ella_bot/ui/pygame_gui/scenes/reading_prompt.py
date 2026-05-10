import time
import queue
import threading
import re
import pygame
from dataclasses import dataclass
from typing import Optional

from ella_bot.ui.pygame_gui.scene import BaseScene
from ella_bot.ui.pygame_gui.ui_helpers import draw_gradient, draw_wrapped_text
from ella_bot.validation.feedback import FeedbackResult, build_feedback, build_spoken_feedback_with_coaching
from ella_bot.validation.validators import ValidationResult, validate_spoken_text, normalize, spoken_word_confidence_map, build_highlighted_expected

@dataclass
class AttemptViewModel:
    expected_sentence: str
    spoken_sentence: str
    highlighted_expected: str
    validation: ValidationResult
    feedback: FeedbackResult

class ReadingPromptScene(BaseScene):
    def __init__(self, app):
        super().__init__(app)
        self.worker_thread: Optional[threading.Thread] = None
        self.error_log = []
        self.max_errors = 5
        self.idle_timeout_seconds = 10
        self.last_activity_monotonic = time.monotonic()

    def on_enter(self) -> None:
        self.app.state = "idle"
        self.app.message = ""
        self.app.prompt_active = False
        self._touch_activity()
        self.app.animator.set_state("idle", reset=True)

    def _touch_activity(self) -> None:
        self.last_activity_monotonic = time.monotonic()

    def handle_event(self, event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._start_attempt()
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.app.switch_scene("main_menu")
            elif event.key == pygame.K_SPACE:
                self._touch_activity()
                self._start_attempt()
            elif event.key == pygame.K_r:
                self._touch_activity()
                self._speak_last_feedback()

    def update(self, now_ms: int) -> None:
        self._drain_event_queue()
        
        if self.app.state == "listening" and not self.app.prompt_active:
            if time.monotonic() - self.last_activity_monotonic >= self.idle_timeout_seconds:
                self.app.event_queue.put(("state", "idle"))
                self.app.event_queue.put(("message", ""))

    def render(self) -> None:
        screen = self.app.screen
        width, height = screen.get_size()
        draw_gradient(screen, self.app.config, pygame)

        if self.app.prompt_active:
            prompt_padding = 72
            prompt_rect = pygame.Rect(prompt_padding, prompt_padding, width - prompt_padding * 2, height - prompt_padding * 2)

            level_text = self.app.font_subtitle.render(
                f"Level {self.app._display_level_name()}  |  Item {self.app._current_item_number()}",
                True,
                self.app.config.text_secondary,
            )
            screen.blit(level_text, (prompt_rect.left, prompt_rect.top))

            prompt_font = self.app._prompt_font(pygame)
            prompt_top = prompt_rect.top + 72
            prompt_text_rect = pygame.Rect(prompt_rect.left, prompt_top, prompt_rect.width, prompt_rect.height - 72)
            draw_wrapped_text(screen, self.app.expected_sentence, prompt_font, self.app.config.text_primary, prompt_text_rect, line_spacing=14)
            return

        avatar_frame = self.app.animator.current_frame()
        frame_w = max(1, avatar_frame.get_width())
        frame_h = max(1, avatar_frame.get_height())
        scale = max(width / frame_w, height / frame_h)

        target_size = (max(1, int(frame_w * scale)), max(1, int(frame_h * scale)))
        rendered_frame = pygame.transform.smoothscale(avatar_frame, target_size)
        avatar_target = rendered_frame.get_rect(center=(width // 2, height // 2))
        screen.blit(rendered_frame, avatar_target)

    def _start_attempt(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            return

        self.app.prompt_active = True
        self.worker_thread = threading.Thread(target=self._attempt_worker, daemon=True)
        self.worker_thread.start()

    def _attempt_worker(self) -> None:
        self.app.event_queue.put(("state", "speaking"))
        self.app.event_queue.put(("message", ""))

        if self.app.audio_feedback and self.app.tts is not None:
            try:
                announcement = self.app._build_start_announcement()
                target_item = self.app.expected_sentence.strip()
                target_override = self.app.pronunciation_overrides.get(target_item.lower(), target_item)
                pattern = re.compile(rf'\b{re.escape(target_item)}\b', re.IGNORECASE)
                announcement_with_overrides = pattern.sub(target_override, announcement)
                self.app.tts.speak(announcement_with_overrides)
            except Exception as exc:
                self.app.event_queue.put(("error", str(exc)))

        self.app.event_queue.put(("state", "listening"))
        self.app.event_queue.put(("message", ""))

        try:
            target_sentence = self.app.expected_sentence
            asr_result = self.app.asr.transcribe(expected_sentence=target_sentence)
            self.app.prompt_active = False
            self.app.event_queue.put(("state", "processing"))
            self.app.event_queue.put(("message", "Validating your reading..."))
            time.sleep(2.0)

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

            highlighted = build_highlighted_expected(validation.alignment)
            view_model = AttemptViewModel(
                expected_sentence=self.app.expected_sentence,
                spoken_sentence=asr_result.transcript,
                highlighted_expected=highlighted,
                validation=validation,
                feedback=feedback,
            )
            self.app.event_queue.put(("attempt_ready", view_model))

            if self.app.audio_feedback and self.app.tts is not None:
                try:
                    spoken_lines = build_spoken_feedback_with_coaching(
                        feedback=feedback,
                        overrides=self.app.pronunciation_overrides,
                        expected_sentence=self.app.expected_sentence,
                        max_hints=2,
                    )
                except Exception:
                    spoken_lines = [feedback.level_message]

                for line in spoken_lines:
                    self.app.event_queue.put(("state", "speaking"))
                    self.app.event_queue.put(("message", "Speaking feedback..."))
                    self.app.tts.speak(line)

            if feedback.level_message == "Correct!":
                self.app.completed_in_level = min(self.app.completed_in_level + 1, self.app.level_goal)
                self.app.event_queue.put(("state", "success"))
            else:
                self.app.event_queue.put(("state", "retry"))

            if self.app._try_level_up(validation.accuracy):
                self.app.event_queue.put(("message", f"Level up! You reached {self.app._display_level_name()}."))
            else:
                if feedback.level_message == "Correct!":
                    self.app._advance_to_next_sentence()
                    self.app.event_queue.put(("message", "Great job. Next item."))
                else:
                    self.app.event_queue.put(("message", "Try again on the same item."))

            time.sleep(0.6)
            self.app.event_queue.put(("state", "listening"))
            self.app.event_queue.put(("message", ""))

        except Exception as exc:
            import traceback
            error_msg = str(exc)
            tb = traceback.format_exc()
            print(f"\n{'='*60}")
            print(f"ERROR DURING VALIDATION:")
            print(tb)
            print(f"{'='*60}\n")
            self.error_log.append(error_msg)
            if len(self.error_log) > self.max_errors:
                self.error_log.pop(0)
            self.app.event_queue.put(("state", "retry"))
            self.app.event_queue.put(("message", f"Error: {error_msg}"))
            self.app.event_queue.put(("error", error_msg))
        finally:
            self.app.prompt_active = False

    def _speak_last_feedback(self) -> None:
        if not self.app.audio_feedback or self.app.tts is None or self.app.latest_attempt is None:
            return

        def _worker() -> None:
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
                self.app.event_queue.put(("state", "speaking"))
                self.app.event_queue.put(("message", "Replaying feedback..."))
                self.app.tts.speak(line)

            if feedback.level_message == "Correct!":
                self.app.event_queue.put(("state", "success"))
            else:
                self.app.event_queue.put(("state", "retry"))
            self.app.event_queue.put(("message", "Replay finished."))

        if self.worker_thread and self.worker_thread.is_alive():
            return

        self.worker_thread = threading.Thread(target=_worker, daemon=True)
        self.worker_thread.start()

    def _drain_event_queue(self) -> None:
        while True:
            try:
                event, payload = self.app.event_queue.get_nowait()
            except queue.Empty:
                break

            if event == "state" and isinstance(payload, str):
                self.app.state = payload
                self._touch_activity()
                if payload in {"idle", "warmup", "listening", "processing", "speaking", "success", "retry"}:
                    self.app.animator.set_state(payload, reset=True)
            elif event == "message" and isinstance(payload, str):
                self.app.message = payload
            elif event == "error" and isinstance(payload, str):
                pass
            elif event == "attempt_ready" and isinstance(payload, AttemptViewModel):
                self.app.latest_attempt = payload
