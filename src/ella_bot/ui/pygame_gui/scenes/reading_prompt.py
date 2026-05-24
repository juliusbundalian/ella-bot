import io
import time
import queue
import threading
from pathlib import Path
import pygame
from typing import Optional

from ella_bot.ui.pygame_gui.scene import BaseScene
from ella_bot.ui.pygame_gui.ui_helpers import draw_gradient, draw_wrapped_text
from ella_bot.ui.pygame_gui.bot_sprite import BotSprite
from ella_bot.ui.pygame_gui.components.pause_modal import PauseModal
from ella_bot.core.events import (
    StateChanged, MessageChanged, ErrorOccurred, AttemptReady,
    SubLevelCompleted, SessionCompleted,
)
from ella_bot.services.attempt_runner import AttemptRunner

class ReadingPromptScene(BaseScene):
    def __init__(self, app):
        super().__init__(app)
        self.worker_thread: Optional[threading.Thread] = None
        self.idle_timeout_seconds = 10
        self.last_activity_monotonic = time.monotonic()
        self.modal = PauseModal(self.app)
        self.is_paused = False
        self.menu_button_rect: Optional[pygame.Rect] = None
        self._icon_menu = None
        self.bot = BotSprite()
        self.runner = AttemptRunner(self.app, lambda: self.is_paused)

    def on_enter(self) -> None:
        self.app.state = "idle"
        self.app.message = ""
        self.app.prompt_active = False
        self.modal.close()
        self.is_paused = False
        self._touch_activity()
        self.app.animator.set_state("idle", reset=True)

    def _touch_activity(self) -> None:
        self.last_activity_monotonic = time.monotonic()

    def handle_event(self, event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.modal.visible:
                action = self.modal.hit_test(event.pos)
                if action == "close":
                    if self.modal.show_confirm:
                        self.modal.show_confirm = False
                        self.modal.confirm_action = None
                    else:
                        self._set_paused(False)
                    return
                if action == "resume":
                    self._set_paused(False)
                    return
                if action == "ask_restart":
                    self.modal.show_confirm = True
                    self.modal.confirm_action = "restart"
                    return
                if action == "ask_main_menu":
                    self.modal.show_confirm = True
                    self.modal.confirm_action = "main_menu"
                    return
                if action == "confirm_yes":
                    if self.modal.confirm_action == "restart":
                        self.modal.close()
                        self._start_attempt()
                        return
                    if self.modal.confirm_action == "main_menu":
                        self.modal.close()
                        self.is_paused = False
                        self.app.switch_scene("main_menu")
                    return
                if action == "confirm_no":
                    self.modal.show_confirm = False
                    self.modal.confirm_action = None
                    return
                return  # "consumed" — click inside modal but no button hit

            if self.menu_button_rect and self.menu_button_rect.collidepoint(event.pos):
                self._set_paused(True)
                return

            self._start_attempt()
        elif event.type == pygame.KEYDOWN:
            if self.modal.visible:
                return
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
        if not self.modal.visible:
            self.bot.update(now_ms, self.app.state)

        if self.modal.visible:
            return

        if self.app.state == "listening" and not self.app.prompt_active:
            if time.monotonic() - self.last_activity_monotonic >= self.idle_timeout_seconds:
                self.app.event_queue.put(StateChanged("idle"))
                self.app.event_queue.put(MessageChanged(""))

    def render(self) -> None:
        screen = self.app.screen
        width, height = screen.get_size()
        draw_gradient(screen, self.app.config, pygame)

        prompt_padding = 0
        prompt_rect = pygame.Rect(
            prompt_padding,
            prompt_padding,
            width - prompt_padding * 2,
            height - prompt_padding * 2,
        )

        card_color = (0, 0, 0)
        inner_card_color = (255, 255, 255)
        outer_border = (94, 42, 59)
        inner_border = (255, 185, 207)
        pygame.draw.rect(screen, card_color, prompt_rect, border_radius=0)

        middle_rect = prompt_rect.inflate(-24, -24)
        pygame.draw.rect(screen, inner_card_color, middle_rect, border_radius=56)

        inner_rect = prompt_rect.inflate(-64, -64)
        pygame.draw.rect(screen, inner_card_color, inner_rect, border_radius=36)

        label_text = f"Level {self.app._display_level_name()} | Item {self.app._current_item_number()}"
        label_bg = (230, 127, 159)
        label_fg = (255, 255, 255)
        label_surf = self.app.font_subtitle.render(label_text, True, label_fg)
        label_pad_x = 24
        label_pad_y = 12
        label_rect = label_surf.get_rect()
        label_rect.topleft = (inner_rect.left + 48, inner_rect.top + 36)
        pill_rect = pygame.Rect(
            label_rect.left - label_pad_x,
            label_rect.top - label_pad_y,
            label_rect.width + label_pad_x * 2,
            label_rect.height + label_pad_y * 2,
        )
        pygame.draw.rect(screen, label_bg, pill_rect, border_radius=12)
        screen.blit(label_surf, label_rect)

        menu_rect = pygame.Rect(inner_rect.right - 84, inner_rect.top + 24, 56, 56)
        self.menu_button_rect = menu_rect
        if self._icon_menu is None:
            try:
                from ella_bot.utils.file_utils import resolve_asset_path
                svg_text = resolve_asset_path("assets/ic_menu.svg").read_text()
                svg_sized = (svg_text
                             .replace('height="24px"', 'height="32px"')
                             .replace('width="24px"', 'width="32px"'))
                self._icon_menu = pygame.image.load(io.BytesIO(svg_sized.encode())).convert_alpha()
            except Exception:
                self._icon_menu = False
        btn_fill = (255, 182, 193)
        btn_outline = (94, 42, 59)
        pygame.draw.rect(screen, btn_outline,
                         pygame.Rect(menu_rect.left + 4, menu_rect.top + 4, menu_rect.width, menu_rect.height),
                         border_radius=12)
        pygame.draw.rect(screen, btn_fill, menu_rect, border_radius=12)
        pygame.draw.rect(screen, btn_outline, menu_rect, width=2, border_radius=12)
        if self._icon_menu not in (None, False):
            screen.blit(self._icon_menu, self._icon_menu.get_rect(center=menu_rect.center))

        prompt_font = self.app._prompt_font(pygame)
        prompt_top = inner_rect.top + 120
        prompt_text_rect = pygame.Rect(
            inner_rect.left + 40,
            prompt_top,
            inner_rect.width - 80,
            inner_rect.height - 160,
        )
        draw_wrapped_text(
            screen,
            self.app.expected_sentence,
            prompt_font,
            (56, 56, 56),
            prompt_text_rect,
            line_spacing=14,
            align="center",
            valign="center",
        )

        self.bot.draw(screen, inner_rect)

        pygame.draw.rect(screen, outer_border, prompt_rect, width=12, border_radius=68)
        pygame.draw.rect(screen, inner_border, inner_rect, width=12, border_radius=36)

        self.modal.render(screen, inner_rect)

    def _start_attempt(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            return
        if self.is_paused:
            return

        self.app.prompt_active = True
        self.worker_thread = threading.Thread(target=self.runner.run, daemon=True)
        self.worker_thread.start()

    def _attempt_worker(self) -> None:
        self.app.event_queue.put(("state", "speaking"))
        self.app.event_queue.put(("message", ""))

        if self.app.audio_feedback and self.app.tts is not None:
            try:
                if self.is_paused:
                    return
                intro, sentence = self.app._build_start_announcement()
                target_override = self.app.pronunciation_overrides.get(sentence.lower(), sentence)
                
                # Speak intro phrase at normal speed
                self.app.tts.speak(intro)
                
                # Speak actual target sentence at slower speed
                slow_rate = int(self.app.tts.config.rate * 0.8)
                self.app.tts.speak(target_override, rate=slow_rate)
            except Exception as exc:
                print(f"[DEBUG] Intro TTS Error: {exc}")
                self.app.event_queue.put(("error", str(exc)))

        self.app.event_queue.put(("state", "listening"))
        self.app.event_queue.put(("message", ""))

        try:
            target_sentence = self.app.expected_sentence
            print(f"[DEBUG] Starting ASR transcription for: {target_sentence}")
            asr_result = self.app.asr.transcribe(expected_sentence=target_sentence)
            print(f"[DEBUG] Transcription finished. Result: '{asr_result.transcript}'")

            if self.is_paused:
                self.app.prompt_active = False
                self.app.event_queue.put(("state", "idle"))
                self.app.event_queue.put(("message", ""))
                return

            self.app.prompt_active = False
            self.app.event_queue.put(("state", "processing"))
            self.app.event_queue.put(("message", "Validating your reading..."))
            
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

                for idx, line in enumerate(spoken_lines):
                    if self.is_paused:
                        break
                    self.app.event_queue.put(("state", "speaking"))
                    self.app.event_queue.put(("message", "Speaking feedback..."))
                    print(f"[DEBUG] Speaking: {line}")
                    lower_line = line.lower()
                    if idx > 0 or any(kw in lower_line for kw in [
                        "work on the word", "look at", "tricky", "skipped", "forget",
                        "say it with me", "sounds like", "listen carefully"
                    ]):
                        if "let me read the sentence" in lower_line:
                            self.app.tts.speak(line)
                        else:
                            slow_rate = int(self.app.tts.config.rate * 0.8)
                            self.app.tts.speak(line, rate=slow_rate)
                    else:
                        self.app.tts.speak(line)
                print("[DEBUG] Audio feedback finished.")

            if feedback.level_message == "Correct!":
                self.app.completed_in_level = min(self.app.completed_in_level + 1, self.app.level_goal)
                self.app.event_queue.put(("state", "success"))
            else:
                self.app.event_queue.put(("state", "retry"))

            if self.app._try_level_up(validation.accuracy):
                level_name = self.app._display_level_name()
                if self.app.audio_feedback and self.app.tts is not None:
                    if self.is_paused:
                        return
                    self.app.tts.speak(f"Wow, you leveled up! Welcome to the {level_name} level. You're doing amazing!")
                self.app.event_queue.put(("message", f"Level up! You reached {level_name}!"))
            else:
                if feedback.level_message.startswith(("Excellent", "Great", "Wonderful", "That's right", "Perfect")):
                    self.app._advance_to_next_sentence()
                    self.app.event_queue.put(("message", "Nice work! Moving to the next one."))
                else:
                    self.app.event_queue.put(("message", "Give it another try!"))

            time.sleep(0.6)
            self.app.event_queue.put(("state", "listening"))
            self.app.event_queue.put(("message", ""))

        except Exception as exc:
            import traceback
            print("\n[!!!] WORKER THREAD CRITICAL ERROR:")
            traceback.print_exc()
            error_msg = str(exc)
            tb = traceback.format_exc()
            print(f"\n{'='*60}")
            print(f"ERROR DURING VALIDATION:")
            print(tb)
            print(f"{'='*60}\n")
            self.error_log.append(error_msg)
            if len(self.error_log) > self.max_errors:
                self.error_log.pop(0)
            
            # Reset GUI state so it doesn't hang
            self.app.prompt_active = False
            self.app.event_queue.put(("state", "retry"))
            self.app.event_queue.put(("message", f"Error: {error_msg}"))
            self.app.event_queue.put(("error", error_msg))
            print(f"DEBUG: Worker thread encountered error: {error_msg}")
        finally:
            self.app.prompt_active = False

    def _speak_last_feedback(self) -> None:
        if self.is_paused or not self.app.audio_feedback or self.app.tts is None or self.app.latest_attempt is None:
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

            for idx, line in enumerate(lines):
                self.app.event_queue.put(("state", "speaking"))
                self.app.event_queue.put(("message", "Replaying feedback..."))
                lower_line = line.lower()
                if idx > 0 or any(kw in lower_line for kw in [
                    "work on the word", "look at", "tricky", "skipped", "forget",
                    "say it with me", "sounds like", "listen carefully"
                ]):
                    if "let me read" in lower_line or "let me make" in lower_line:
                        self.app.tts.speak(line)
                    else:
                        slow_rate = int(self.app.tts.config.rate * 0.8)
                        self.app.tts.speak(line, rate=slow_rate)
                else:
                    self.app.tts.speak(line)

            if feedback.level_message == "Correct!":
                self.app.event_queue.put(("state", "success"))
            else:
                self.app.event_queue.put(("state", "retry"))
            self.app.event_queue.put(("message", "Replay finished."))

        if self.worker_thread and self.worker_thread.is_alive():
            return
        self.worker_thread = threading.Thread(target=self.runner.replay, daemon=True)
        self.worker_thread.start()

    def _drain_event_queue(self) -> None:
        while True:
            try:
                event = self.app.event_queue.get_nowait()
            except queue.Empty:
                break

            if isinstance(event, StateChanged):
                self.app.state = event.state
                self._touch_activity()
                if event.state in {"idle", "warmup", "listening", "processing", "speaking", "success", "retry"}:
                    self.app.animator.set_state(event.state, reset=True)
            elif isinstance(event, MessageChanged):
                self.app.message = event.message
            elif isinstance(event, ErrorOccurred):
                pass
            elif isinstance(event, AttemptReady):
                self.app.latest_attempt = event.view_model
            elif isinstance(event, SubLevelCompleted):
                self.app.latest_result = event.result
                self.app.latest_result_kind = event.kind
                self.app.switch_scene("results")
                return
            elif isinstance(event, SessionCompleted):
                self.app.latest_result = event.result
                self.app.switch_scene("final_eval")
                return

    def _set_paused(self, paused: bool) -> None:
        self.is_paused = paused
        if paused:
            self.modal.open()
        else:
            self.modal.close()
        if paused and self.app.tts is not None:
            try:
                self.app.tts.stop()
            except Exception:
                pass
        self.app.prompt_active = False
        self.app.event_queue.put(StateChanged("idle"))
        self.app.event_queue.put(MessageChanged(""))
