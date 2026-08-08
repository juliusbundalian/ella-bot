from __future__ import annotations

import io
import time
import queue
import threading
import pygame
from typing import Optional

from ella_bot.ui.pygame_gui.scene import BaseScene
from ella_bot.ui.pygame_gui.ui_helpers import draw_gradient, draw_wrapped_text
from ella_bot.ui.pygame_gui.bot_sprite import BotSprite
from ella_bot.ui.pygame_gui.components.pause_modal import PauseModal
from ella_bot.ui.pygame_gui.components.button import Button
from ella_bot.services.sound_effects import play_button_click
from ella_bot.core.constants import get_level1_sound_and_word, tier_of
from ella_bot.core.events import StateChanged, MessageChanged, ErrorOccurred, AttemptReady, SubLevelCompleted, SessionCompleted
from ella_bot.services.attempt_runner import AttemptRunner, AttemptViewModel
from ella_bot.validation.validators import (
    validate_spoken_text,
    normalize,
    spoken_word_confidence_map,
    build_highlighted_expected,
)
from ella_bot.validation.feedback import (
    build_feedback,
    build_spoken_feedback_with_coaching,
)

class ReadingPromptScene(BaseScene):
    def __init__(self, app):
        super().__init__(app)
        self.worker_thread: Optional[threading.Thread] = None
        self.idle_timeout_seconds = 10
        self.last_activity_monotonic = time.monotonic()
        self.modal = PauseModal(self.app)
        self.is_paused = False
        self.menu_button_rect: Optional[pygame.Rect] = None
        self.replay_button_rect: Optional[pygame.Rect] = None
        self.next_button_rect: Optional[pygame.Rect] = None
        self._icon_menu = None
        self.bot = BotSprite()
        self.runner = AttemptRunner(self.app, lambda: self.is_paused)
        self._auto_start_at: float | None = None
        self.pre_pause_state = "idle"
        self._lottie_bg = None

    def _load_assets(self) -> None:
        if getattr(self, "_lottie_bg", None) is None:
            try:
                from ella_bot.utils.file_utils import resolve_config_path
                from pathlib import Path
                from ella_bot.ui.pygame_gui.lottie_bg import LottieBackground
                lottie_file = resolve_config_path("assets/Reading_bg.lottie")
                if not lottie_file.exists():
                    lottie_file = Path("assets/Reading_bg.lottie")
                self._lottie_bg = LottieBackground(lottie_file)
            except Exception:
                self._lottie_bg = None

        if getattr(self, "_settings_icon", None) is None:
            try:
                from ella_bot.utils.file_utils import resolve_asset_path
                svg_text = resolve_asset_path("assets/ic_settings.svg").read_text(encoding="utf-8")
                svg_tinted = (
                    svg_text.replace('fill="#FFFFFF"', 'fill="#FFFAF3"')
                    .replace('height="24px"', 'height="44px"')
                    .replace('width="24px"', 'width="44px"')
                )
                self._settings_icon = pygame.image.load(io.BytesIO(svg_tinted.encode("utf-8"))).convert_alpha()
            except Exception:
                self._settings_icon = False

    def on_enter(self) -> None:
        from ella_bot.services.bgm_service import pause_bgm

        pause_bgm()
        self._load_assets()
        self.app.state = "idle"
        self.app.message = ""
        self.app.prompt_active = False
        self.modal.close()
        self.is_paused = False
        self._touch_activity()
        self.app.animator.set_state("idle", reset=True)
        self.app.sublevel_start_time = time.monotonic()
        if hasattr(self.app, "session") and hasattr(self.app.session, "last_announced_sentence"):
            self.app.session.last_announced_sentence = ""

        # Drain and clear the event queue to prevent any stale background thread events from leaking
        self._drain_event_queue()
        while not self.app.event_queue.empty():
            try:
                self.app.event_queue.get_nowait()
            except Exception:
                break

        self._auto_start_at = time.monotonic() + 1.5

    def on_exit(self) -> bool:
        self.is_paused = True
        self._auto_start_at = None
        return self._stop_attempt_worker()

    def _stop_attempt_worker(self) -> bool:
        if self.runner:
            self.runner.abort()
        if self.app.tts is not None:
            try:
                self.app.tts.stop()
            except Exception:
                pass
        if self.worker_thread is not None and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=2.0)
        if self.worker_thread is not None and self.worker_thread.is_alive():
            return False
        self.worker_thread = None
        self.app.prompt_active = False
        return True

    def prepare_shutdown(self) -> bool:
        self._auto_start_at = None
        return self._stop_attempt_worker()

    def _touch_activity(self) -> None:
        self.last_activity_monotonic = time.monotonic()

    def handle_event(self, event) -> None:
        is_level_1 = False
        if hasattr(self.app, "session") and hasattr(self.app.session, "current_level"):
            is_level_1 = (tier_of(self.app.session.current_level) == 1)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.modal.visible:
                action = self.modal.hit_test(event.pos)
                if action and action != "consumed":
                    play_button_click()
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
                        self._restart_level_from_pause()
                        return
                    if self.modal.confirm_action == "main_menu":
                        self._return_to_menu_from_pause()
                    return
                if action == "confirm_no":
                    self.modal.show_confirm = False
                    self.modal.confirm_action = None
                    return
                return  # "consumed" — click inside modal but no button hit

            if self.menu_button_rect and self.menu_button_rect.collidepoint(event.pos):
                play_button_click()
                self._set_paused(True)
                return

            if is_level_1:
                if self.replay_button_rect and self.replay_button_rect.collidepoint(event.pos):
                    play_button_click()
                    self._replay_level1_audio()
                    return
                if self.next_button_rect and self.next_button_rect.collidepoint(event.pos):
                    play_button_click()
                    self._advance_level1_item()
                    return
            else:
                self._start_attempt()
        elif event.type == pygame.KEYDOWN:
            if self.modal.visible:
                return
            if event.key == pygame.K_ESCAPE:
                self.app.switch_scene("main_menu")
            elif event.key == pygame.K_SPACE:
                self._touch_activity()
                if is_level_1:
                    self._advance_level1_item()
                else:
                    self._start_attempt()
            elif event.key in (pygame.K_n, pygame.K_RETURN):
                if is_level_1:
                    self._touch_activity()
                    self._advance_level1_item()
            elif event.key == pygame.K_r:
                self._touch_activity()
                if is_level_1:
                    self._replay_level1_audio()
                else:
                    self._speak_last_feedback()
            elif event.key == pygame.K_o:
                self._touch_activity()
                if not is_level_1 and self.app.asr is not None:
                    self.app.asr.bypass_transcription = self.app.expected_sentence
                    self._start_attempt()

    def _abort_paused_attempt(self) -> bool:
        self._auto_start_at = None
        return self._stop_attempt_worker()

    def _restart_level_from_pause(self) -> None:
        if not self._abort_paused_attempt():
            return
        self.app.session.reset_current_level()
        self.app.evaluation.reset_sublevel(self.app.session.current_level)
        if not self.app.save_active_session("reading"):
            self.app.continue_saved_session()
            self.is_paused = True
            return
        self.modal.close()
        self.is_paused = False
        self._start_attempt()

    def _return_to_menu_from_pause(self) -> None:
        if not self._abort_paused_attempt():
            return
        if not self.app.save_active_session("reading"):
            self.app.continue_saved_session()
            self.is_paused = True
            return
        self.modal.close()
        self.is_paused = False
        self.app.switch_scene("main_menu")

    def update(self, now_ms: int) -> None:
        self._drain_event_queue()
        if not self.modal.visible:
            tts_amp = getattr(self.app.tts, "current_amplitude", 0.0) if getattr(self.app, "tts", None) else 0.0
            self.bot.update(now_ms, self.app.state, tts_amplitude=tts_amp)

        if self.modal.visible:
            return

        if not self.is_paused and not self.app.prompt_active:
            if self._auto_start_at is not None and time.monotonic() >= self._auto_start_at:
                self._auto_start_at = None
                self._start_attempt()
            elif self._auto_start_at is None and self.app.state in ("listening", "idle", "success", "retry"):
                is_level_1 = False
                if hasattr(self.app, "session") and hasattr(self.app.session, "current_level") and isinstance(self.app.session.current_level, str):
                    is_level_1 = (tier_of(self.app.session.current_level) == 1)
                if not is_level_1:
                    self._start_attempt()

        if self.app.state == "listening" and not self.app.prompt_active:
            if time.monotonic() - self.last_activity_monotonic >= self.idle_timeout_seconds:
                self.app.event_queue.put(StateChanged("idle"))
                self.app.event_queue.put(MessageChanged(""))

    def render(self) -> None:
        self._load_assets()
        screen = self.app.screen
        width, height = screen.get_size()
        now_ms = pygame.time.get_ticks()

        # Render Lottie Reading Background (Reading_bg.lottie)
        if self._lottie_bg:
            vf = self._lottie_bg.get_frame(now_ms, (width, height))
            if vf:
                screen.blit(vf, (0, 0))
            else:
                draw_gradient(screen, self.app.config, pygame)
        else:
            draw_gradient(screen, self.app.config, pygame)

        prompt_padding = 0
        prompt_rect = pygame.Rect(
            prompt_padding,
            prompt_padding,
            width - prompt_padding * 2,
            height - prompt_padding * 2,
        )

        inner_rect = prompt_rect.inflate(-64, -64)
        outer_border = (94, 42, 59)
        inner_border = (255, 185, 207)

        # 1. Level Indicator (Top-Centered Pill matching Figma spec)
        level_str = str(self.app._display_level_name()).upper()
        item_num = self.app._current_item_number()
        label_text = f"LEVEL {level_str} | Item {item_num}"
        label_bg = (216, 150, 216)   # Pink/violet pill fill
        label_fg = (87, 39, 108)     # Dark violet text
        label_surf = self.app.font_subtitle.render(label_text, True, label_fg)
        label_pad_x = 28
        label_pad_y = 12
        label_rect = label_surf.get_rect(centerx=width // 2, top=44)
        pill_rect = pygame.Rect(
            label_rect.left - label_pad_x,
            label_rect.top - label_pad_y,
            label_rect.width + label_pad_x * 2,
            label_rect.height + label_pad_y * 2,
        )
        pygame.draw.rect(screen, label_bg, pill_rect, border_radius=24)
        pygame.draw.rect(screen, (127, 63, 151), pill_rect, width=3, border_radius=24)
        screen.blit(label_surf, label_rect)

        # 2. Settings / Pause Button (Left-Centered circular gear button matching Main Menu)
        gear_size = 80
        gear_x = inner_rect.left + 40
        gear_y = height // 2 - gear_size // 2
        self.menu_button_rect = pygame.Rect(gear_x, gear_y, gear_size, gear_size)

        pause_btn = Button(
            self.menu_button_rect,
            icon=self._settings_icon if self._settings_icon else None,
            variant="violet",
            stroke_weight=8,
            corner_radius=50,
        )
        pause_btn.is_pressed = (self.is_paused or self.modal.visible)
        pause_btn.draw(screen)

        prompt_font, prompt_text_rect = self._prompt_layout(inner_rect, pygame)
        if prompt_font is not None:
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

        tts_obj = getattr(self.app, "tts", None)
        is_speaking = False
        if tts_obj is not None:
            val = getattr(tts_obj, "is_speaking", False)
            is_speaking = bool(val() if callable(val) else val)
            if not is_speaking and hasattr(tts_obj, "_active_stream"):
                is_speaking = tts_obj._active_stream is not None

        show_bubble = False
        if not self.modal.visible and not is_speaking:
            if self.app.state == "listening" and getattr(self.app, "prompt_active", False):
                show_bubble = True

        self.bot.draw(
            screen,
            inner_rect,
            show_thought_bubble=show_bubble,
            now_ms=now_ms,
            font=self.app.font_body,
        )

        is_level_1 = False
        if hasattr(self.app, "session") and hasattr(self.app.session, "current_level"):
            is_level_1 = (tier_of(self.app.session.current_level) == 1)

        if is_level_1:
            btn_w, btn_h = 180, 56
            gap = 24
            center_x = width // 2
            btn_y = height - 114

            self.replay_button_rect = pygame.Rect(center_x - btn_w - gap // 2, btn_y, btn_w, btn_h)
            self.next_button_rect = pygame.Rect(center_x + gap // 2, btn_y, btn_w, btn_h)

            replay_btn = Button(
                self.replay_button_rect,
                label="Replay",
                variant="violet",
                font=self.app.font_button,
                stroke_weight=6,
            )
            next_btn = Button(
                self.next_button_rect,
                label="Next",
                variant="yellow",
                font=self.app.font_button,
                stroke_weight=6,
            )
            replay_btn.draw(screen)
            next_btn.draw(screen)
        else:
            self.replay_button_rect = None
            self.next_button_rect = None

        self.modal.render(screen, inner_rect)

    @staticmethod
    def _wrapped_height(text, font, width, line_spacing=14):
        lines = []
        current = ""
        for word in text.split():
            candidate = (current + " " + word).strip()
            if font.size(candidate)[0] <= width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)

        return len(lines) * font.get_height() + line_spacing * max(0, len(lines) - 1)

    @staticmethod
    def _bot_safe_bottom(inner_rect):
        """Return a boundary above every frame BotSprite.draw() can render."""
        max_sprite_height = int(inner_rect.height * 0.42)
        overlap = int(max_sprite_height * 0.28)
        return inner_rect.bottom + overlap - 48 - max_sprite_height

    @staticmethod
    def _centered_safe_top(inner_rect, safe_bottom):
        """Center a text region vertically while keeping it above ELLA."""
        return max(inner_rect.top, inner_rect.centery * 2 - safe_bottom)

    def _prompt_layout(self, inner_rect, pygame_module):
        text = self.app.expected_sentence
        session = getattr(self.app, "session", None)
        current_level = getattr(session, "current_level", None)
        if not isinstance(current_level, str):
            current_level = getattr(self.app, "current_level", "")

        current_tier = tier_of(current_level)

        if current_tier in (3, 4):
            safe_bottom = self._bot_safe_bottom(inner_rect)
            text_top = self._centered_safe_top(inner_rect, safe_bottom)
            text_width = max(1, int(inner_rect.width * 0.64))
            text_rect = pygame_module.Rect(
                inner_rect.centerx - text_width // 2,
                text_top,
                text_width,
                max(0, safe_bottom - text_top),
            )
            for font_size in range(80, 11, -2):
                font = self.app._get_prompt_font(font_size)
                if self._wrapped_height(text, font, text_rect.width) <= text_rect.height:
                    return font, text_rect
            return None, text_rect

        if len(text.split()) <= 6:
            if current_tier == 2:
                safe_bottom = self._bot_safe_bottom(inner_rect)
                text_top = self._centered_safe_top(inner_rect, safe_bottom)
                text_rect = pygame_module.Rect(
                    inner_rect.left + 40,
                    text_top,
                    inner_rect.width - 80,
                    max(0, safe_bottom - text_top),
                )
                for font_size in range(72, 11, -2):
                    font = self.app._get_prompt_font(font_size)
                    if font.size(text)[0] <= text_rect.width:
                        return font, text_rect
                return None, text_rect

            text_rect = pygame_module.Rect(
                inner_rect.left + 40,
                inner_rect.top + 120,
                inner_rect.width - 80,
                inner_rect.height - 160,
            )
            font = self.app._prompt_font(pygame_module)
            return font, text_rect

        safe_bottom = self._bot_safe_bottom(inner_rect)
        if current_tier == 2:
            text_top = self._centered_safe_top(inner_rect, safe_bottom)
        else:
            text_top = min(inner_rect.top + 88, safe_bottom)
        text_rect = pygame_module.Rect(
            inner_rect.left + 40,
            text_top,
            max(1, inner_rect.width - 80),
            max(0, safe_bottom - text_top),
        )
        max_font_size = 72 if current_tier == 2 else 82
        for font_size in range(max_font_size, 11, -2):
            font = self.app._get_prompt_font(font_size)
            if self._wrapped_height(text, font, text_rect.width) <= text_rect.height:
                return font, text_rect
        return None, text_rect

    def _start_attempt(self) -> None:
        self._auto_start_at = None
        if self.worker_thread and self.worker_thread.is_alive():
            return
        if self.is_paused:
            return

        self.app.prompt_active = True
        self.runner = AttemptRunner(self.app, lambda: self.is_paused)
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
                sound_target, display_word = get_level1_sound_and_word(sentence)
                is_level_1 = str(self.app.current_level).startswith("1")

                if is_level_1:
                    target_override = self.app.pronunciation_overrides.get(sound_target.lower(), sound_target)
                    self.app.tts.speak(intro)
                    self.app.tts.speak(target_override)
                else:
                    target_override = self.app.pronunciation_overrides.get(sentence.lower(), sentence)
                    self.app.tts.speak(intro)
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
                    is_level_1 = str(self.app.current_level).startswith("1")
                    spoken_lines = build_spoken_feedback_with_coaching(
                        feedback=feedback,
                        overrides=self.app.pronunciation_overrides,
                        expected_sentence=self.app.expected_sentence,
                        max_hints=2,
                        validation=validation,
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

                    is_sound_line = (
                        line.startswith("phonemes:") or
                        len(line.strip()) == 1 or
                        (line.endswith(".") and len(line.strip()) == 2)
                    )

                    if is_level_1:
                        # On Level 1, all feedback and coaching are spoken at normal speed
                        self.app.tts.speak(line)
                    elif is_sound_line:
                        # Sounds and phonemes are always spoken at normal speed to sound natural
                        self.app.tts.speak(line)
                    elif idx > 0 or any(kw in lower_line for kw in [
                        "work on the word", "look at", "tricky", "skipped", "forget",
                        "say it with me", "sounds like", "listen carefully"
                    ]):
                        if "let me read the sentence" in lower_line or "let me make the sound" in lower_line:
                            self.app.tts.speak(line)
                        else:
                            slow_rate = int(self.app.tts.config.rate * 0.8)
                            self.app.tts.speak(line, rate=slow_rate)
                    else:
                        self.app.tts.speak(line)
                print("[DEBUG] Audio feedback finished.")

            # Accuracy >= 95% is considered a successful read
            is_success = (validation.accuracy >= 0.95)

            if is_success:
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
                if is_success:
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
            print("ERROR DURING VALIDATION:")
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
                is_level_1 = str(self.app.current_level).startswith("1")
                lines = build_spoken_feedback_with_coaching(
                    feedback=feedback,
                    overrides=self.app.pronunciation_overrides,
                    expected_sentence=self.app.latest_attempt.expected_sentence,
                    max_hints=2,
                    validation=self.app.latest_attempt.validation,
                )
            except Exception:
                lines = [feedback.level_message]

            for idx, line in enumerate(lines):
                self.app.event_queue.put(("state", "speaking"))
                self.app.event_queue.put(("message", "Replaying feedback..."))
                if line.startswith("SLOW: "):
                    line = line[6:].strip()
                    slow_rate = int(self.app.tts.config.rate * 0.7)
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
            self.pre_pause_state = self.app.state
            self.modal.open()
            if self.app.tts is not None:
                try:
                    self.app.tts.pause()
                except Exception:
                    pass
            if not (self.worker_thread and self.worker_thread.is_alive()):
                self.app.prompt_active = False
            self.app.event_queue.put(StateChanged("idle"))
            self.app.event_queue.put(MessageChanged(""))
        else:
            self.modal.close()
            if self.app.tts is not None:
                try:
                    self.app.tts.resume()
                except Exception:
                    pass
            if not (self.worker_thread and self.worker_thread.is_alive()):
                self._auto_start_at = time.monotonic() + 0.5
                self.app.prompt_active = False
                self.app.event_queue.put(StateChanged("idle"))
                self.app.event_queue.put(MessageChanged(""))
            else:
                self.app.event_queue.put(StateChanged(self.pre_pause_state))

    def _replay_level1_audio(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            return
        if self.is_paused:
            return
        self.worker_thread = threading.Thread(target=self.runner.replay_level1, daemon=True)
        self.worker_thread.start()

    def _advance_level1_item(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            return
        if self.is_paused:
            return
        self.worker_thread = threading.Thread(target=self.runner.advance_level1, daemon=True)
        self.worker_thread.start()
