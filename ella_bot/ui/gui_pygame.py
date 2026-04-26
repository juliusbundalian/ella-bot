from __future__ import annotations

import random
import queue
import threading
from dataclasses import dataclass
from typing import Dict, List, Optional

from ella_bot.feedback.feedback_engine import (
    FeedbackResult,
    build_feedback,
    build_spoken_feedback_with_coaching,
)
from ella_bot.ui.avatar_animator import AvatarAnimator
from ella_bot.ui.gui_config import GUIConfig
from ella_bot.validation.text_validation import (
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
        self.message = "Press Start or Space to begin reading."
        self.latest_attempt: Optional[AttemptViewModel] = None
        self.worker_thread: Optional[threading.Thread] = None

        self.event_queue: queue.Queue[tuple[str, object]] = queue.Queue()

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

        flags = pygame.FULLSCREEN if self.config.fullscreen else 0
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
        )

        self.running = True
        while self.running:
            now_ms = pygame.time.get_ticks()
            self._handle_pygame_events(pygame)
            self._drain_event_queue()
            self.animator.update(now_ms)
            self._render(pygame)
            pygame.display.flip()
            self.clock.tick(self.config.fps)

        pygame.quit()

    def _start_attempt(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            return

        self.worker_thread = threading.Thread(target=self._attempt_worker, daemon=True)
        self.worker_thread.start()

    def _attempt_worker(self) -> None:
        self.event_queue.put(("state", "listening"))
        self.event_queue.put(("message", "Listening... please read the sentence aloud."))

        try:
            target_sentence = self.expected_sentence
            asr_result = self.asr.transcribe(expected_sentence=target_sentence)
            self.event_queue.put(("state", "processing"))
            self.event_queue.put(("message", "Analyzing your reading..."))

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

        except Exception as exc:
            self.event_queue.put(("state", "retry"))
            self.event_queue.put(("message", f"Error: {exc}"))

    def _drain_event_queue(self) -> None:
        while True:
            try:
                event, payload = self.event_queue.get_nowait()
            except queue.Empty:
                break

            if event == "state" and isinstance(payload, str):
                self.state = payload
                if payload in {"idle", "success", "retry"}:
                    self.animator.set_state(payload if payload != "idle" else "neutral", reset=True)
                elif payload in {"listening", "processing", "speaking"}:
                    self.animator.set_state(payload, reset=True)
            elif event == "message" and isinstance(payload, str):
                self.message = payload
            elif event == "attempt_ready" and isinstance(payload, AttemptViewModel):
                self.latest_attempt = payload

    def _handle_pygame_events(self, pygame_module) -> None:
        for event in pygame_module.event.get():
            if event.type == pygame_module.QUIT:
                self.running = False
            elif event.type == pygame_module.KEYDOWN:
                if event.key == pygame_module.K_ESCAPE:
                    self.running = False
                elif event.key == pygame_module.K_SPACE:
                    self._start_attempt()
                elif event.key == pygame_module.K_r:
                    self._speak_last_feedback()
            elif event.type == pygame_module.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_click(event.pos)

    def _handle_click(self, mouse_pos: tuple[int, int]) -> None:
        if self.start_button.collidepoint(mouse_pos):
            self._start_attempt()
        elif self.replay_button.collidepoint(mouse_pos):
            self._speak_last_feedback()
        elif self.quit_button.collidepoint(mouse_pos):
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

        card_color = self.config.card
        sentence_rect = pygame_module.Rect(40, 26, width - 80, 132)
        avatar_panel = pygame_module.Rect(40, 168, int(width * 0.46), height - 248)
        feedback_panel = pygame_module.Rect(avatar_panel.right + 24, 168, width - avatar_panel.right - 64, height - 248)
        actions_rect = pygame_module.Rect(40, height - 70, width - 80, 40)

        pygame_module.draw.rect(self.screen, card_color, sentence_rect, border_radius=24)
        pygame_module.draw.rect(self.screen, card_color, avatar_panel, border_radius=24)
        pygame_module.draw.rect(self.screen, card_color, feedback_panel, border_radius=24)

        title = self.font_title.render("E.L.L.A.", True, self.config.text_primary)
        level_label = self._display_level_name()
        subtitle = self.font_subtitle.render("AI Reading Assistant", True, self.config.text_secondary)
        level_badge = self.font_small.render(f"Level: {level_label}", True, self.config.accent)
        self.screen.blit(title, (sentence_rect.left + 22, sentence_rect.top + 14))
        self.screen.blit(subtitle, (sentence_rect.left + 24, sentence_rect.top + 58))
        self.screen.blit(level_badge, (sentence_rect.left + 24, sentence_rect.top + 88))

        sentence_label = self.font_small.render("Read this sentence:", True, self.config.text_secondary)
        self.screen.blit(sentence_label, (sentence_rect.left + 430, sentence_rect.top + 14))

        sentence_text_rect = pygame_module.Rect(sentence_rect.left + 430, sentence_rect.top + 42, sentence_rect.width - 450, 72)
        self._draw_wrapped_text(self.expected_sentence, self.font_body, self.config.text_primary, sentence_text_rect)

        avatar_frame = self.animator.current_frame()
        avatar_target = avatar_frame.get_rect(center=avatar_panel.center)
        self.screen.blit(avatar_frame, avatar_target)

        status_color = self.config.accent
        if self.state in {"retry"}:
            status_color = self.config.danger
        elif self.state in {"processing"}:
            status_color = self.config.warn

        status = self.font_subtitle.render(f"State: {self.state}", True, status_color)
        self.screen.blit(status, (feedback_panel.left + 20, feedback_panel.top + 16))

        progress_text = f"{level_label}, {self.completed_in_level} out of {self.level_goal} completed"
        progress = self.font_small.render(progress_text, True, self.config.text_secondary)
        self.screen.blit(progress, (feedback_panel.left + 20, feedback_panel.top + 44))

        msg_rect = pygame_module.Rect(feedback_panel.left + 20, feedback_panel.top + 68, feedback_panel.width - 40, 58)
        self._draw_wrapped_text(self.message, self.font_small, self.config.text_secondary, msg_rect, line_spacing=4)

        if self.latest_attempt is None:
            hint = self.font_body.render("No attempt yet.", True, self.config.text_secondary)
            self.screen.blit(hint, (feedback_panel.left + 20, feedback_panel.top + 130))
        else:
            attempt = self.latest_attempt
            y = feedback_panel.top + 130

            level = self.font_body.render(f"Feedback: {attempt.feedback.level_message}", True, self.config.text_primary)
            self.screen.blit(level, (feedback_panel.left + 20, y))
            y += 44

            accuracy = self.font_small.render(
                f"Accuracy: {attempt.validation.accuracy * 100:.1f}%    WER: {attempt.validation.wer:.2f}",
                True,
                self.config.text_secondary,
            )
            self.screen.blit(accuracy, (feedback_panel.left + 20, y))
            y += 34

            spoken_label = self.font_small.render("Spoken:", True, self.config.text_secondary)
            self.screen.blit(spoken_label, (feedback_panel.left + 20, y))
            y += 24
            spoken_rect = pygame_module.Rect(feedback_panel.left + 20, y, feedback_panel.width - 40, 48)
            self._draw_wrapped_text(attempt.spoken_sentence or "(silence)", self.font_small, self.config.text_primary, spoken_rect, 2)
            y += 58

            target_label = self.font_small.render("Target (highlighted):", True, self.config.text_secondary)
            self.screen.blit(target_label, (feedback_panel.left + 20, y))
            y += 24
            target_rect = pygame_module.Rect(feedback_panel.left + 20, y, feedback_panel.width - 40, 56)
            self._draw_wrapped_text(attempt.highlighted_expected, self.font_small, self.config.text_primary, target_rect, 2)
            y += 66

            if attempt.feedback.pronunciation_hints:
                hints_label = self.font_small.render("Pronunciation support:", True, self.config.text_secondary)
                self.screen.blit(hints_label, (feedback_panel.left + 20, y))
                y += 24
                for hint in attempt.feedback.pronunciation_hints[:2]:
                    hint_rect = pygame_module.Rect(feedback_panel.left + 34, y, feedback_panel.width - 54, 42)
                    self._draw_wrapped_text(f"- {hint}", self.font_small, self.config.text_primary, hint_rect, 2)
                    y += 40

        self.start_button = pygame_module.Rect(actions_rect.left, actions_rect.top, 180, actions_rect.height)
        self.replay_button = pygame_module.Rect(actions_rect.left + 196, actions_rect.top, 180, actions_rect.height)
        self.quit_button = pygame_module.Rect(actions_rect.right - 120, actions_rect.top, 120, actions_rect.height)

        pygame_module.draw.rect(self.screen, self.config.accent, self.start_button, border_radius=12)
        pygame_module.draw.rect(self.screen, (64, 100, 121), self.replay_button, border_radius=12)
        pygame_module.draw.rect(self.screen, (126, 81, 87), self.quit_button, border_radius=12)

        start_txt = self.font_small.render("Start (Space)", True, (255, 255, 255))
        replay_txt = self.font_small.render("Replay (R)", True, (255, 255, 255))
        quit_txt = self.font_small.render("Quit (Esc)", True, (255, 255, 255))

        self.screen.blit(start_txt, start_txt.get_rect(center=self.start_button.center))
        self.screen.blit(replay_txt, replay_txt.get_rect(center=self.replay_button.center))
        self.screen.blit(quit_txt, quit_txt.get_rect(center=self.quit_button.center))
