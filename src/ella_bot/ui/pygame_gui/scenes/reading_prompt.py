import time
import queue
import threading
import re
from pathlib import Path
import pygame
from dataclasses import dataclass
from typing import Optional

from ella_bot.ui.pygame_gui.scene import BaseScene
from ella_bot.ui.pygame_gui.ui_helpers import draw_gradient, draw_wrapped_text
from ella_bot.validation.feedback import FeedbackResult, build_feedback, build_spoken_feedback_with_coaching
from ella_bot.validation.validators import ValidationResult, validate_spoken_text, normalize, spoken_word_confidence_map, build_highlighted_expected
from ella_bot.utils.file_utils import get_project_root

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
        self.show_pause_modal = False
        self.show_confirm_modal = False
        self.confirm_action: Optional[str] = None
        self.is_paused = False
        self.menu_button_rect: Optional[pygame.Rect] = None
        self.pause_resume_rect: Optional[pygame.Rect] = None
        self.pause_main_menu_rect: Optional[pygame.Rect] = None
        self.pause_exit_rect: Optional[pygame.Rect] = None
        self.confirm_yes_rect: Optional[pygame.Rect] = None
        self.confirm_no_rect: Optional[pygame.Rect] = None
        self.bot_frames = self._load_bot_frames()
        self.bot_state = "idle"
        self.bot_frame_index = 0
        self.bot_last_tick_ms = 0
        self.bot_intervals_ms = {
            "idle": 1400,
            "listening": 320,
            "speaking": 160,
            "thinking": 200,
            "warmup": 200,
            "error": 1200,
        }

    def on_enter(self) -> None:
        self.app.state = "idle"
        self.app.message = ""
        self.app.prompt_active = False
        self.show_pause_modal = False
        self.show_confirm_modal = False
        self.confirm_action = None
        self.is_paused = False
        self._touch_activity()
        self.app.animator.set_state("idle", reset=True)

    def _touch_activity(self) -> None:
        self.last_activity_monotonic = time.monotonic()

    def handle_event(self, event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.show_confirm_modal:
                if self.confirm_yes_rect and self.confirm_yes_rect.collidepoint(event.pos):
                    if self.confirm_action == "main_menu":
                        self.show_confirm_modal = False
                        self.show_pause_modal = False
                        self.confirm_action = None
                        self.is_paused = False
                        self.app.switch_scene("main_menu")
                    elif self.confirm_action == "exit":
                        self.app.running = False
                    return
                if self.confirm_no_rect and self.confirm_no_rect.collidepoint(event.pos):
                    self.show_confirm_modal = False
                    self.confirm_action = None
                    return
                return

            if self.show_pause_modal:
                if self.pause_resume_rect and self.pause_resume_rect.collidepoint(event.pos):
                    self._set_paused(False)
                    return
                if self.pause_main_menu_rect and self.pause_main_menu_rect.collidepoint(event.pos):
                    self.show_confirm_modal = True
                    self.confirm_action = "main_menu"
                    return
                if self.pause_exit_rect and self.pause_exit_rect.collidepoint(event.pos):
                    self.show_confirm_modal = True
                    self.confirm_action = "exit"
                    return
                return

            if self.menu_button_rect and self.menu_button_rect.collidepoint(event.pos):
                self._set_paused(True)
                return

            self._start_attempt()
        elif event.type == pygame.KEYDOWN:
            if self.show_pause_modal or self.show_confirm_modal:
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
        if not self.show_pause_modal and not self.show_confirm_modal:
            self._update_bot_animation(now_ms)
        
        if self.show_pause_modal or self.show_confirm_modal:
            return

        if self.app.state == "listening" and not self.app.prompt_active:
            if time.monotonic() - self.last_activity_monotonic >= self.idle_timeout_seconds:
                self.app.event_queue.put(("state", "idle"))
                self.app.event_queue.put(("message", ""))

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
        outer_border = (230, 127, 159)
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
        pygame.draw.rect(screen, label_bg, menu_rect, border_radius=12)
        line_color = (255, 255, 255)
        line_thickness = 3
        line_gap = 6
        line_len = int(menu_rect.width * 0.52)
        total_height = line_thickness * 3 + line_gap * 2
        start_y = menu_rect.centery - total_height // 2
        line_x_left = menu_rect.centerx - line_len // 2
        line_x_right = menu_rect.centerx + line_len // 2
        for idx in range(3):
            y = start_y + idx * (line_thickness + line_gap)
            pygame.draw.line(
                screen,
                line_color,
                (line_x_left, y),
                (line_x_right, y),
                width=line_thickness,
            )

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

        self._draw_bot(screen, inner_rect)

        pygame.draw.rect(screen, outer_border, prompt_rect, width=12, border_radius=68)
        pygame.draw.rect(screen, inner_border, inner_rect, width=12, border_radius=36)

        self._draw_pause_modal(screen, inner_rect)

    def _start_attempt(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            return
        if self.is_paused:
            return

        self.app.prompt_active = True
        self.worker_thread = threading.Thread(target=self._attempt_worker, daemon=True)
        self.worker_thread.start()

    def _attempt_worker(self) -> None:
        self.app.event_queue.put(("state", "speaking"))
        self.app.event_queue.put(("message", ""))

        if self.app.audio_feedback and self.app.tts is not None:
            try:
                if self.is_paused:
                    return
                announcement = self.app._build_start_announcement()
                target_item = self.app.expected_sentence.strip()
                target_override = self.app.pronunciation_overrides.get(target_item.lower(), target_item)
                pattern = re.compile(rf'\b{re.escape(target_item)}\b', re.IGNORECASE)
                announcement_with_overrides = pattern.sub(target_override, announcement)
                self.app.tts.speak(announcement_with_overrides)
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

                for line in spoken_lines:
                    if self.is_paused:
                        break
                    self.app.event_queue.put(("state", "speaking"))
                    self.app.event_queue.put(("message", "Speaking feedback..."))
                    print(f"[DEBUG] Speaking: {line}")
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

    def _load_bot_frames(self) -> dict[str, list[pygame.Surface]]:
        base = get_project_root() / "bot"
        mapping = {
            "idle": base / "idle",
            "listening": base / "listening",
            "speaking": base / "speaking",
            "thinking": base / "thinking",
            "warmup": base / "warmup",
            "error": base / "error",
        }
        frames: dict[str, list[pygame.Surface]] = {}
        for state, folder in mapping.items():
            images: list[pygame.Surface] = []
            if folder.exists():
                for image_path in sorted(folder.glob("*.png")):
                    try:
                        image = pygame.image.load(str(image_path)).convert_alpha()
                        images.append(image)
                    except Exception:
                        continue
            if images:
                frames[state] = images
        return frames

    def _bot_state_for_app(self) -> str:
        state = self.app.state
        if state == "processing":
            return "thinking"
        if state == "retry":
            return "error"
        if state == "success":
            return "idle"
        if state in {"idle", "listening", "speaking", "warmup"}:
            return state
        return "idle"

    def _update_bot_animation(self, now_ms: int) -> None:
        next_state = self._bot_state_for_app()
        if next_state != self.bot_state:
            self.bot_state = next_state
            self.bot_frame_index = 0
            self.bot_last_tick_ms = 0

        frames = self.bot_frames.get(self.bot_state, [])
        if len(frames) <= 1:
            return

        if self.bot_last_tick_ms == 0:
            self.bot_last_tick_ms = now_ms
            return

        interval_ms = self.bot_intervals_ms.get(self.bot_state, 240)
        if now_ms - self.bot_last_tick_ms >= interval_ms:
            self.bot_frame_index = (self.bot_frame_index + 1) % len(frames)
            self.bot_last_tick_ms = now_ms

    def _draw_bot(self, screen: pygame.Surface, prompt_rect: pygame.Rect) -> None:
        frames = self.bot_frames.get(self.bot_state) or self.bot_frames.get("idle")
        if not frames:
            return
        frame = frames[self.bot_frame_index % len(frames)]

        max_width = int(prompt_rect.width * 0.32)
        max_height = int(prompt_rect.height * 0.42)
        frame_w = max(1, frame.get_width())
        frame_h = max(1, frame.get_height())
        scale = min(max_width / frame_w, max_height / frame_h)
        target_size = (max(1, int(frame_w * scale)), max(1, int(frame_h * scale)))
        rendered = pygame.transform.smoothscale(frame, target_size)

        # Position the bot so its lower part extends beyond the inner card bottom,
        # then clip the blit to the inner card rect so the lower portion is hidden.
        overlap = int(target_size[1] * 0.28)
        target_rect = rendered.get_rect(
            bottomright=(prompt_rect.right - 26, prompt_rect.bottom + overlap - 48)
        )

        # Clip drawing to the prompt_rect (inner card) so the sprite appears 'cut off'
        old_clip = screen.get_clip()
        try:
            screen.set_clip(prompt_rect)
            screen.blit(rendered, target_rect)
        finally:
            screen.set_clip(old_clip)

    def _draw_pause_modal(self, screen: pygame.Surface, prompt_rect: pygame.Rect) -> None:
        if not (self.show_pause_modal or self.show_confirm_modal):
            return

        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        screen.blit(overlay, (0, 0))

        dialog_w = int(prompt_rect.width * 0.72)
        dialog_h = int(prompt_rect.height * 0.40)
        dialog_x = prompt_rect.centerx - dialog_w // 2
        dialog_y = prompt_rect.centery - dialog_h // 2
        dialog_rect = pygame.Rect(dialog_x, dialog_y, dialog_w, dialog_h)

        pygame.draw.rect(screen, (255, 255, 255), dialog_rect, border_radius=18)
        pygame.draw.rect(screen, (230, 127, 159), dialog_rect, width=6, border_radius=18)

        title_text = "Paused" if not self.show_confirm_modal else "Confirm"
        title_surf = self.app.font_body.render(title_text, True, (40, 40, 40))
        title_rect = title_surf.get_rect(center=(dialog_rect.centerx, dialog_rect.top + 46))
        screen.blit(title_surf, title_rect)

        button_w = int(dialog_rect.width * 0.34)
        button_h = 64
        button_y = dialog_rect.bottom - button_h - 28
        left_x = dialog_rect.centerx - button_w - 16
        right_x = dialog_rect.centerx + 16

        if self.show_confirm_modal:
            msg = "Return to main menu?" if self.confirm_action == "main_menu" else "Exit the app?"
            msg_surf = self.app.font_small.render(msg, True, (50, 50, 50))
            msg_rect = msg_surf.get_rect(center=(dialog_rect.centerx, dialog_rect.centery))
            screen.blit(msg_surf, msg_rect)

            yes_rect = pygame.Rect(left_x, button_y, button_w, button_h)
            no_rect = pygame.Rect(right_x, button_y, button_w, button_h)
            self.confirm_yes_rect = yes_rect
            self.confirm_no_rect = no_rect
            self.pause_main_menu_rect = None
            self.pause_exit_rect = None

            pygame.draw.rect(screen, (236, 133, 165), yes_rect, border_radius=14)
            pygame.draw.rect(screen, (230, 127, 159), yes_rect, width=4, border_radius=14)
            yes_text = self.app.font_small.render("Yes", True, (255, 255, 255))
            screen.blit(yes_text, yes_text.get_rect(center=yes_rect.center))

            pygame.draw.rect(screen, (236, 133, 165), no_rect, border_radius=14)
            pygame.draw.rect(screen, (230, 127, 159), no_rect, width=4, border_radius=14)
            no_text = self.app.font_small.render("No", True, (255, 255, 255))
            screen.blit(no_text, no_text.get_rect(center=no_rect.center))
            return

        button_w = int(dialog_rect.width * 0.48)
        button_h = 62
        stack_gap = 16
        stack_height = button_h * 3 + stack_gap * 2
        stack_top = dialog_rect.centery - stack_height // 2 + 12

        resume_rect = pygame.Rect(
            dialog_rect.centerx - button_w // 2,
            stack_top,
            button_w,
            button_h,
        )
        main_rect = pygame.Rect(
            dialog_rect.centerx - button_w // 2,
            stack_top + button_h + stack_gap,
            button_w,
            button_h,
        )
        exit_rect = pygame.Rect(
            dialog_rect.centerx - button_w // 2,
            stack_top + (button_h + stack_gap) * 2,
            button_w,
            button_h,
        )

        self.pause_resume_rect = resume_rect
        self.pause_main_menu_rect = main_rect
        self.pause_exit_rect = exit_rect
        self.confirm_yes_rect = None
        self.confirm_no_rect = None

        pygame.draw.rect(screen, (236, 133, 165), resume_rect, border_radius=14)
        pygame.draw.rect(screen, (230, 127, 159), resume_rect, width=4, border_radius=14)
        resume_text = self.app.font_small.render("Resume", True, (255, 255, 255))
        screen.blit(resume_text, resume_text.get_rect(center=resume_rect.center))

        pygame.draw.rect(screen, (236, 133, 165), main_rect, border_radius=14)
        pygame.draw.rect(screen, (230, 127, 159), main_rect, width=4, border_radius=14)
        main_text = self.app.font_small.render("Main Menu", True, (255, 255, 255))
        screen.blit(main_text, main_text.get_rect(center=main_rect.center))

        pygame.draw.rect(screen, (236, 133, 165), exit_rect, border_radius=14)
        pygame.draw.rect(screen, (230, 127, 159), exit_rect, width=4, border_radius=14)
        exit_text = self.app.font_small.render("Exit", True, (255, 255, 255))
        screen.blit(exit_text, exit_text.get_rect(center=exit_rect.center))

    def _set_paused(self, paused: bool) -> None:
        self.is_paused = paused
        self.show_pause_modal = paused
        if not paused:
            self.show_confirm_modal = False
            self.confirm_action = None
        if paused and self.app.tts is not None:
            try:
                self.app.tts.stop()
            except Exception:
                pass
        self.app.prompt_active = False
        self.app.event_queue.put(("state", "idle"))
        self.app.event_queue.put(("message", ""))
