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
from ella_bot.core.events import StateChanged, MessageChanged, ErrorOccurred, AttemptReady
from ella_bot.services.attempt_runner import AttemptRunner

class ReadingPromptScene(BaseScene):
    def __init__(self, app):
        super().__init__(app)
        self.worker_thread: Optional[threading.Thread] = None
        self.idle_timeout_seconds = 10
        self.last_activity_monotonic = time.monotonic()
        self.modal = PauseModal()
        self.is_paused = False
        self.menu_button_rect: Optional[pygame.Rect] = None
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
                if action == "ask_main_menu":
                    self.modal.show_confirm = True
                    self.modal.confirm_action = "main_menu"
                    return
                if action == "ask_exit":
                    self.modal.show_confirm = True
                    self.modal.confirm_action = "exit"
                    return
                if action == "confirm_yes":
                    if self.modal.confirm_action == "main_menu":
                        self.modal.close()
                        self.is_paused = False
                        self.app.switch_scene("main_menu")
                    elif self.modal.confirm_action == "exit":
                        self.app.running = False
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

        self.bot.draw(screen, inner_rect)

        pygame.draw.rect(screen, outer_border, prompt_rect, width=12, border_radius=68)
        pygame.draw.rect(screen, inner_border, inner_rect, width=12, border_radius=36)

        self.modal.render(screen, self.app.font_body, self.app.font_small, inner_rect)

    def _start_attempt(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            return
        if self.is_paused:
            return

        self.app.prompt_active = True
        self.worker_thread = threading.Thread(target=self.runner.run, daemon=True)
        self.worker_thread.start()

    def _speak_last_feedback(self) -> None:
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
