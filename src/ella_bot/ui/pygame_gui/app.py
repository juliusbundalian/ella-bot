from __future__ import annotations

import random
import queue
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from ella_bot.validation.feedback import (
    FeedbackResult,
    build_feedback,
    build_spoken_feedback_with_coaching,
)
from ella_bot.ui.pygame_gui.animator import AvatarAnimator
from ella_bot.ui.pygame_gui.config import GUIConfig
from ella_bot.validation.validators import (
    ValidationResult,
    build_highlighted_expected,
    normalize,
    spoken_word_confidence_map,
    validate_spoken_text,
)


@dataclass
class AttemptViewModel:
    expected_sentence: str
    spoken_sentence: str
    highlighted_expected: str
    validation: ValidationResult
    feedback: FeedbackResult


class EllaGUIApp:
    """Pygame GUI loop for E.L.L.A. with event-driven avatar states."""

    def __init__(
        self,
        expected_sentence: str,
        asr,
        tts,
        audio_feedback: bool,
        pronunciation_overrides: Dict[str, str],
        hard_sentences: Optional[List[str]] = None,
        start_level: str = "easy",
        config: Optional[GUIConfig] = None,
    ) -> None:
        self.asr = asr
        self.tts = tts
        self.audio_feedback = audio_feedback
        self.pronunciation_overrides = pronunciation_overrides
        self.config = config or GUIConfig()

        self.level_order = ["easy", "medium-a", "medium-b", "medium-c", "hard"]
        self.level_thresholds = {
            "easy": 0.85,
            "medium-a": 0.88,
            "medium-b": 0.90,
            "medium-c": 0.92,
            "hard": 1.01,
        }

        self.level_pools: Dict[str, List[str]] = {
            "easy": list("abcdefghijklmnopqrstuvwxyz"),
            # Medium A: short CVC-style early decoding words.
            "medium-a": ["cat", "dog", "sun", "hat", "red", "pen", "map", "cup", "bed", "fish"],
            # Medium B: blends, digraphs, and longer vowels.
            "medium-b": ["train", "green", "brush", "clock", "smile", "chair", "storm", "light", "plant", "school"],
            # Medium C: multi-syllable and abstract school vocabulary.
            "medium-c": [
                "animal",
                "battery",
                "celebrate",
                "dinosaur",
                "elephant",
                "favorite",
                "important",
                "library",
                "remember",
                "wonderful",
            ],
            "hard": hard_sentences or ([expected_sentence] if expected_sentence else ["The cat sits on the table."]),
        }

        if start_level not in self.level_order:
            start_level = "easy"
        self.current_level = start_level
        self.level_indices: Dict[str, int] = {level: 0 for level in self.level_order}
        self.expected_sentence = self._pick_sentence_for_level(self.current_level)
        self.completed_in_level = 0
        self.level_goal = len(self.level_pools.get(self.current_level, []))

        self.state = "idle"
        self.message = ""
        self.latest_attempt: Optional[AttemptViewModel] = None
        self.worker_thread: Optional[threading.Thread] = None
        self.startup_thread: Optional[threading.Thread] = None
        self.error_log: List[str] = []  # Track errors for debugging
        self.max_errors = 5  # Show last 5 errors
        self.idle_timeout_seconds = 10
        self.last_activity_monotonic = time.monotonic()
        self.prompt_active = False
        self.show_menu = False
        self.pressed_button: Optional[str] = None  # Track which menu button is pressed
        self.show_exit_confirm: bool = False

        # Confirmation dialog button rects (created during render)
        self.menu_confirm_yes_button = None
        self.menu_confirm_no_button = None

        self.event_queue: queue.Queue[tuple[str, object]] = queue.Queue()

    def _touch_activity(self) -> None:
        self.last_activity_monotonic = time.monotonic()

    def _current_item_number(self) -> int:
        return self.level_indices.get(self.current_level, 0) + 1

    def _build_start_announcement(self) -> str:
        target_sentence = self.expected_sentence.strip() or "the next item"
        return (
            f"We are about to begin. You are on level {self._display_level_name()}, "
            f"item {self._current_item_number()}. First, read: {target_sentence}."
        )

    def _prompt_font(self, pygame_module):
        width, height = self.screen.get_size()
        if len(self.expected_sentence) <= 3:
            return pygame_module.font.SysFont("Avenir Next", max(72, int(height * 0.28)))
        if len(self.expected_sentence.split()) <= 6:
            return pygame_module.font.SysFont("Avenir Next", max(54, int(height * 0.12)))
        return pygame_module.font.SysFont("Avenir Next", max(42, int(height * 0.08)))

    def _startup_sequence(self) -> None:
        self.event_queue.put(("state", "warmup"))
        self.event_queue.put(("message", ""))
        time.sleep(2)

        self.event_queue.put(("state", "speaking"))
        self.event_queue.put(("message", ""))

        if self.tts is not None:
            try:
                self.tts.speak(
                    "Hello, I am Ella, your offline reading assistant. I am ready when you are."
                )
            except Exception as exc:
                self.event_queue.put(("error", str(exc)))

        self.event_queue.put(("show_menu", True))

    def _update_idle_state(self) -> None:
        if self.state != "listening" or self.prompt_active:
            return

        if time.monotonic() - self.last_activity_monotonic >= self.idle_timeout_seconds:
            self.event_queue.put(("state", "idle"))
            self.event_queue.put(("message", ""))

    def _pick_sentence_for_level(self, level: str) -> str:
        pool = self.level_pools.get(level, [])
        if not pool:
            return ""
        if level == "hard":
            return random.choice(pool)

        index = self.level_indices.get(level, 0)
        index = max(0, min(index, len(pool) - 1))
        return pool[index]

    def _display_level_name(self) -> str:
        return self.current_level.replace("-", " ").title()

    def _current_pool_size(self) -> int:
        return len(self.level_pools.get(self.current_level, []))

    def _advance_to_next_sentence(self) -> None:
        if self.current_level == "hard":
            self.expected_sentence = self._pick_sentence_for_level(self.current_level)
            return

        pool = self.level_pools.get(self.current_level, [])
        if not pool:
            self.expected_sentence = ""
            return

        next_index = min(self.level_indices.get(self.current_level, 0) + 1, len(pool) - 1)
        self.level_indices[self.current_level] = next_index
        self.expected_sentence = pool[next_index]

    def _reset_current_level(self) -> None:
        self.completed_in_level = 0
        self.level_goal = self._current_pool_size()
        self.level_indices[self.current_level] = 0
        self.expected_sentence = self._pick_sentence_for_level(self.current_level)

    def _advance_to_higher_stage(self) -> bool:
        idx = self.level_order.index(self.current_level)
        if idx + 1 >= len(self.level_order):
            return False

        self.current_level = self.level_order[idx + 1]
        self._reset_current_level()
        return True

    def _try_level_up(self, accuracy: float) -> bool:
        if self.current_level == "hard":
            return False

        threshold = self.level_thresholds.get(self.current_level, 1.0)
        if self.completed_in_level < self.level_goal:
            return False
        if accuracy < threshold:
            return False

        return self._advance_to_higher_stage()

    def run(self) -> None:
        try:
            import pygame
        except Exception as exc:
            raise RuntimeError("pygame is required for GUI mode. Install with: pip install pygame") from exc

        pygame.init()
        pygame.font.init()

        fullscreen = True if not self.config.fullscreen else self.config.fullscreen
        if fullscreen:
            flags = pygame.FULLSCREEN
            self.screen = pygame.display.set_mode((0, 0), flags)
        else:
            flags = 0
            self.screen = pygame.display.set_mode((self.config.width, self.config.height), flags)
        pygame.display.set_caption(self.config.title)

        self.clock = pygame.time.Clock()
        self.font_title = pygame.font.SysFont("Avenir Next", 42)
        self.font_subtitle = pygame.font.SysFont("Avenir Next", 24)
        self.font_body = pygame.font.SysFont("Avenir Next", 30)
        self.font_small = pygame.font.SysFont("Avenir Next", 22)

        avatar_size = (360, 360)
        self.animator = AvatarAnimator(
            pygame_module=pygame,
            assets_dir=self.config.assets_dir,
            frame_size=avatar_size,
            animation_fps=self.config.animation_fps,
            speaking_fps=self.config.speaking_fps,
            loading_fps=self.config.loading_fps,
            processing_fps=self.config.processing_fps,
        )
        self.animator.set_state("warmup", reset=True)

        self.startup_thread = threading.Thread(target=self._startup_sequence, daemon=True)
        self.startup_thread.start()

        self.running = True
        while self.running:
            now_ms = pygame.time.get_ticks()
            self._handle_pygame_events(pygame)
            self._drain_event_queue()
            self._update_idle_state()
            self.animator.update(now_ms)
            self._render(pygame)
            pygame.display.flip()
            self.clock.tick(self.config.fps)

        pygame.quit()

    def _start_attempt(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            return

        self.prompt_active = True

        self.worker_thread = threading.Thread(target=self._attempt_worker, daemon=True)
        self.worker_thread.start()

    def _attempt_worker(self) -> None:
        self.event_queue.put(("state", "speaking"))
        self.event_queue.put(("message", ""))

        if self.audio_feedback and self.tts is not None:
            try:
                self.tts.speak(self._build_start_announcement())
            except Exception as exc:
                self.event_queue.put(("error", str(exc)))

        self.event_queue.put(("state", "listening"))
        self.event_queue.put(("message", ""))

        try:
            target_sentence = self.expected_sentence
            asr_result = self.asr.transcribe(expected_sentence=target_sentence)
            self.prompt_active = False
            self.event_queue.put(("state", "processing"))
            self.event_queue.put(("message", "Validating your reading..."))
            time.sleep(2.0)

            validation = validate_spoken_text(target_sentence, asr_result.transcript)
            spoken_tokens = normalize(asr_result.transcript)
            confidences = [w.confidence for w in asr_result.words][: len(spoken_tokens)]
            conf_map = spoken_word_confidence_map(spoken_tokens, confidences)
            feedback = build_feedback(validation=validation, spoken_confidence_by_word=conf_map)

            highlighted = build_highlighted_expected(validation.alignment)
            view_model = AttemptViewModel(
                expected_sentence=target_sentence,
                spoken_sentence=asr_result.transcript,
                highlighted_expected=highlighted,
                validation=validation,
                feedback=feedback,
            )
            self.event_queue.put(("attempt_ready", view_model))

            if self.audio_feedback and self.tts is not None:
                spoken_lines = build_spoken_feedback_with_coaching(
                    feedback=feedback,
                    overrides=self.pronunciation_overrides,
                    expected_sentence=target_sentence,
                    max_hints=2,
                )

                for line in spoken_lines:
                    self.event_queue.put(("state", "speaking"))
                    self.event_queue.put(("message", "Speaking feedback..."))
                    self.tts.speak(line)

            if feedback.level_message == "Correct!":
                self.completed_in_level = min(self.completed_in_level + 1, self.level_goal)
                self.event_queue.put(("state", "success"))
            else:
                self.event_queue.put(("state", "retry"))

            if self._try_level_up(validation.accuracy):
                self.event_queue.put(("message", f"Level up! You reached {self._display_level_name()}."))
            else:
                if feedback.level_message == "Correct!":
                    self._advance_to_next_sentence()
                    self.event_queue.put(("message", "Great job. Next item."))
                else:
                    self.event_queue.put(("message", "Try again on the same item."))

            time.sleep(0.6)
            self.event_queue.put(("state", "listening"))
            self.event_queue.put(("message", ""))

        except Exception as exc:
            error_msg = str(exc)
            self.error_log.append(error_msg)
            if len(self.error_log) > self.max_errors:
                self.error_log.pop(0)
            self.event_queue.put(("state", "retry"))
            self.event_queue.put(("message", f"Error: {error_msg}"))
            self.event_queue.put(("error", error_msg))
        finally:
            self.prompt_active = False

    def _drain_event_queue(self) -> None:
        while True:
            try:
                event, payload = self.event_queue.get_nowait()
            except queue.Empty:
                break

            if event == "state" and isinstance(payload, str):
                self.state = payload
                self._touch_activity()
                if payload in {"idle", "warmup", "listening", "processing", "speaking", "success", "retry"}:
                    self.animator.set_state(payload, reset=True)
            elif event == "message" and isinstance(payload, str):
                self.message = payload
            elif event == "error" and isinstance(payload, str):
                # Error logging already handled, just ensure it's tracked
                pass
            elif event == "attempt_ready" and isinstance(payload, AttemptViewModel):
                self.latest_attempt = payload
            elif event == "show_menu" and isinstance(payload, bool):
                self.show_menu = payload

    def _handle_pygame_events(self, pygame_module) -> None:
        for event in pygame_module.event.get():
            if event.type == pygame_module.QUIT:
                self.running = False
            elif event.type == pygame_module.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    if self.show_menu:
                        self._handle_menu_button_down(event.pos)
                    else:
                        self._handle_click(event.pos)
            elif event.type == pygame_module.MOUSEBUTTONUP:
                if event.button == 1:  # Left click release
                    if self.show_menu:
                        self._handle_menu_button_up(event.pos)
                    self.pressed_button = None
            elif event.type == pygame_module.KEYDOWN:
                if event.key == pygame_module.K_ESCAPE:
                    self.running = False
                elif event.key == pygame_module.K_SPACE:
                    self._touch_activity()
                    self._start_attempt()
                elif event.key == pygame_module.K_r:
                    self._touch_activity()
                    self._speak_last_feedback()

    def _handle_menu_button_down(self, mouse_pos: tuple[int, int]) -> None:
        """Handle mouse button down on menu buttons."""
        # If confirmation dialog is visible, check its buttons first
        if self.show_exit_confirm:
            if hasattr(self, 'menu_confirm_yes_button') and self.menu_confirm_yes_button.collidepoint(mouse_pos):
                self.pressed_button = "confirm_yes"
                return
            if hasattr(self, 'menu_confirm_no_button') and self.menu_confirm_no_button.collidepoint(mouse_pos):
                self.pressed_button = "confirm_no"
                return

        if hasattr(self, 'menu_start_button') and self.menu_start_button.collidepoint(mouse_pos):
            self.pressed_button = "start"
        elif hasattr(self, 'menu_tutorial_button') and self.menu_tutorial_button.collidepoint(mouse_pos):
            self.pressed_button = "tutorial"
        elif hasattr(self, 'menu_settings_button') and self.menu_settings_button.collidepoint(mouse_pos):
            self.pressed_button = "settings"
        elif hasattr(self, 'menu_exit_button') and self.menu_exit_button.collidepoint(mouse_pos):
            self.pressed_button = "exit"

    def _handle_menu_button_up(self, mouse_pos: tuple[int, int]) -> None:
        """Handle mouse button up on menu buttons - trigger action if still over button."""
        if self.pressed_button == "start" and hasattr(self, 'menu_start_button') and self.menu_start_button.collidepoint(mouse_pos):
            self.show_menu = False
            self._start_attempt()
        elif self.pressed_button == "tutorial" and hasattr(self, 'menu_tutorial_button') and self.menu_tutorial_button.collidepoint(mouse_pos):
            self.message = "Tutorial coming soon!"
        elif self.pressed_button == "settings" and hasattr(self, 'menu_settings_button') and self.menu_settings_button.collidepoint(mouse_pos):
            self.message = "Settings coming soon!"
        elif self.pressed_button == "exit" and hasattr(self, 'menu_exit_button') and self.menu_exit_button.collidepoint(mouse_pos):
            # Show confirmation dialog instead of exiting immediately
            self.show_exit_confirm = True
        elif self.pressed_button == "confirm_yes" and hasattr(self, 'menu_confirm_yes_button') and self.menu_confirm_yes_button.collidepoint(mouse_pos):
            # User confirmed exit
            self.running = False
        elif self.pressed_button == "confirm_no" and hasattr(self, 'menu_confirm_no_button') and self.menu_confirm_no_button.collidepoint(mouse_pos):
            # Cancel exit
            self.show_exit_confirm = False

    def _handle_click(self, mouse_pos: tuple[int, int]) -> None:
        if hasattr(self, 'start_button') and self.start_button.collidepoint(mouse_pos):
            self._start_attempt()
        elif hasattr(self, 'replay_button') and self.replay_button.collidepoint(mouse_pos):
            self._speak_last_feedback()
        elif hasattr(self, 'quit_button') and self.quit_button.collidepoint(mouse_pos):
            self.running = False

    def _speak_last_feedback(self) -> None:
        if not self.audio_feedback or self.tts is None or self.latest_attempt is None:
            return

        def _worker() -> None:
            feedback = self.latest_attempt.feedback
            lines = build_spoken_feedback_with_coaching(
                feedback=feedback,
                overrides=self.pronunciation_overrides,
                expected_sentence=self.latest_attempt.expected_sentence,
                max_hints=2,
            )

            for line in lines:
                self.event_queue.put(("state", "speaking"))
                self.event_queue.put(("message", "Replaying feedback..."))
                self.tts.speak(line)

            if feedback.level_message == "Correct!":
                self.event_queue.put(("state", "success"))
            else:
                self.event_queue.put(("state", "retry"))
            self.event_queue.put(("message", "Replay finished."))

        if self.worker_thread and self.worker_thread.is_alive():
            return

        self.worker_thread = threading.Thread(target=_worker, daemon=True)
        self.worker_thread.start()

    def _draw_gradient(self, pygame_module) -> None:
        top = self.config.background_top
        bottom = self.config.background_bottom
        width, height = self.screen.get_size()

        for y in range(height):
            t = y / max(1, height - 1)
            color = (
                int(top[0] * (1 - t) + bottom[0] * t),
                int(top[1] * (1 - t) + bottom[1] * t),
                int(top[2] * (1 - t) + bottom[2] * t),
            )
            pygame_module.draw.line(self.screen, color, (0, y), (width, y))

    def _draw_wrapped_text(self, text: str, font, color: tuple[int, int, int], rect, line_spacing: int = 8) -> None:
        words = text.split()
        lines: List[str] = []
        current = ""

        for word in words:
            test = (current + " " + word).strip()
            if font.size(test)[0] <= rect.width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word

        if current:
            lines.append(current)

        y = rect.top
        for line in lines:
            surf = font.render(line, True, color)
            self.screen.blit(surf, (rect.left, y))
            y += surf.get_height() + line_spacing
            if y > rect.bottom:
                break

    def _render(self, pygame_module) -> None:
        self._draw_gradient(pygame_module)
        width, height = self.screen.get_size()

        if self.show_menu:
            self._render_menu(pygame_module)
            return

        if self.prompt_active:
            prompt_padding = 72
            prompt_rect = pygame_module.Rect(
                prompt_padding,
                prompt_padding,
                width - prompt_padding * 2,
                height - prompt_padding * 2,
            )

            level_text = self.font_subtitle.render(
                f"Level {self._display_level_name()}  |  Item {self._current_item_number()}",
                True,
                self.config.text_secondary,
            )
            self.screen.blit(level_text, (prompt_rect.left, prompt_rect.top))

            prompt_font = self._prompt_font(pygame_module)
            prompt_top = prompt_rect.top + 72
            prompt_text_rect = pygame_module.Rect(
                prompt_rect.left,
                prompt_top,
                prompt_rect.width,
                prompt_rect.height - 72,
            )
            self._draw_wrapped_text(self.expected_sentence, prompt_font, self.config.text_primary, prompt_text_rect, line_spacing=14)
            return

        avatar_frame = self.animator.current_frame()
        frame_w = max(1, avatar_frame.get_width())
        frame_h = max(1, avatar_frame.get_height())
        scale = max(width / frame_w, height / frame_h)

        target_size = (
            max(1, int(frame_w * scale)),
            max(1, int(frame_h * scale)),
        )
        rendered_frame = pygame_module.transform.smoothscale(avatar_frame, target_size)
        avatar_target = rendered_frame.get_rect(center=(width // 2, height // 2))
        self.screen.blit(rendered_frame, avatar_target)

    def _render_menu(self, pygame_module) -> None:
        """Render the main menu with Start, Tutorial, and Settings buttons."""
        width, height = self.screen.get_size()
        
        # Custom menu colors for touch screen
        menu_bg_color = (245, 205, 214)  # #F5CDD6
        button_bg_color = (248, 111, 150)  # #F86F96
        button_text_color = (255, 255, 255)  # White
        button_outline_color = (0, 0, 0)  # Black
        
        # Fill background with custom color
        self.screen.fill(menu_bg_color)
        
        # Draw title
        title_surf = self.font_title.render("Welcome to E.L.L.A.", True, (0, 0, 0))
        title_rect = title_surf.get_rect(center=(width // 2, int(height * 0.15)))
        self.screen.blit(title_surf, title_rect)
        
        # Draw menu buttons - larger for touch screen
        button_width = 320
        button_height = 110
        button_y_start = int(height * 0.30)
        button_spacing = 130
        center_x = width // 2
        
        # Start button
        self.menu_start_button = pygame_module.Rect(
            center_x - button_width // 2,
            button_y_start,
            button_width,
            button_height
        )
        self._draw_menu_button(pygame_module, self.menu_start_button, "Start", "start", button_bg_color, button_text_color, button_outline_color)
        
        # Tutorial button
        self.menu_tutorial_button = pygame_module.Rect(
            center_x - button_width // 2,
            button_y_start + button_spacing,
            button_width,
            button_height
        )
        self._draw_menu_button(pygame_module, self.menu_tutorial_button, "Tutorial", "tutorial", button_bg_color, button_text_color, button_outline_color)
        
        # Settings button
        self.menu_settings_button = pygame_module.Rect(
            center_x - button_width // 2,
            button_y_start + button_spacing * 2,
            button_width,
            button_height
        )
        self._draw_menu_button(pygame_module, self.menu_settings_button, "Settings", "settings", button_bg_color, button_text_color, button_outline_color)

        # Exit button (bottom)
        self.menu_exit_button = pygame_module.Rect(
            center_x - button_width // 2,
            button_y_start + button_spacing * 3,
            button_width,
            button_height
        )
        self._draw_menu_button(pygame_module, self.menu_exit_button, "Exit", "exit", button_bg_color, button_text_color, button_outline_color)

        # If exit confirmation requested, draw overlay dialog
        if self.show_exit_confirm:
            # Semi-opaque overlay
            overlay = pygame_module.Surface((width, height), pygame_module.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            self.screen.blit(overlay, (0, 0))

            dialog_w = int(width * 0.8)
            dialog_h = int(height * 0.32)
            dialog_x = (width - dialog_w) // 2
            dialog_y = (height - dialog_h) // 2
            dialog_rect = pygame_module.Rect(dialog_x, dialog_y, dialog_w, dialog_h)
            # Dialog background
            pygame_module.draw.rect(self.screen, (255, 255, 255), dialog_rect, border_radius=12)
            pygame_module.draw.rect(self.screen, (0, 0, 0), dialog_rect, width=6, border_radius=12)

            # Dialog text
            msg = "Are you sure you want to exit?"
            msg_font = pygame_module.font.SysFont("Avenir Next", 28, bold=True)
            msg_surf = msg_font.render(msg, True, (0, 0, 0))
            msg_rect = msg_surf.get_rect(center=(width // 2, dialog_y + int(dialog_h * 0.35)))
            self.screen.blit(msg_surf, msg_rect)

            # Yes/No buttons
            btn_w = 160
            btn_h = 70
            btn_y = dialog_y + dialog_h - btn_h - 24
            yes_rect = pygame_module.Rect((width // 2) - btn_w - 12, btn_y, btn_w, btn_h)
            no_rect = pygame_module.Rect((width // 2) + 12, btn_y, btn_w, btn_h)
            self.menu_confirm_yes_button = yes_rect
            self.menu_confirm_no_button = no_rect

            # Yes button (use pressed state)
            yes_bg = (251, 165, 193) if self.pressed_button == "confirm_yes" else button_bg_color
            pygame_module.draw.rect(self.screen, yes_bg, yes_rect, border_radius=12)
            pygame_module.draw.rect(self.screen, button_outline_color, yes_rect, width=6, border_radius=12)
            yes_text = self.font_body.render("Yes", True, (255, 255, 255))
            self.screen.blit(yes_text, yes_text.get_rect(center=yes_rect.center))

            # No button
            no_bg = (251, 165, 193) if self.pressed_button == "confirm_no" else button_bg_color
            pygame_module.draw.rect(self.screen, no_bg, no_rect, border_radius=12)
            pygame_module.draw.rect(self.screen, button_outline_color, no_rect, width=6, border_radius=12)
            no_text = self.font_body.render("No", True, (255, 255, 255))
            self.screen.blit(no_text, no_text.get_rect(center=no_rect.center))

    def _draw_menu_button(self, pygame_module, rect, text: str, button_id: str, bg_color: tuple[int, int, int], text_color: tuple[int, int, int], outline_color: tuple[int, int, int]) -> None:
        """Draw a menu button with text."""
        # Check if button is pressed and use pressed color
        pressed_color = (251, 165, 193)  # #FBA5C1
        current_bg_color = pressed_color if self.pressed_button == button_id else bg_color
        
        # Draw button background
        pygame_module.draw.rect(self.screen, current_bg_color, rect, border_radius=15)
        # Draw thicker button outline
        pygame_module.draw.rect(self.screen, outline_color, rect, width=6, border_radius=15)
        
        # Draw button text - use larger font for touch screen
        button_font = pygame_module.font.SysFont("Avenir Next", 48, bold=True)
        text_surf = button_font.render(text, True, text_color)
        text_rect = text_surf.get_rect(center=rect.center)
        self.screen.blit(text_surf, text_rect)
