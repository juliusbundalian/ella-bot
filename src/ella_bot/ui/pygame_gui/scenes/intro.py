from __future__ import annotations

import queue
import threading
import time
import pygame

from ella_bot.ui.pygame_gui.scene import BaseScene

class IntroScene(BaseScene):
    def __init__(self, app):
        super().__init__(app)
        self.startup_thread = None

    def on_enter(self) -> None:
        self.app.animator.set_state("warmup", reset=True)
        self.startup_thread = threading.Thread(target=self._startup_sequence, daemon=True)
        self.startup_thread.start()

    def _startup_sequence(self) -> None:
        self.app.event_queue.put(("state", "warmup"))
        time.sleep(2)
        
        self.app.event_queue.put(("state", "speaking"))
        if self.app.tts is not None:
            try:
                self.app.tts.speak("Hi! I'm ELLA, your Enhanced Learning Literacy Assistant!")
            except Exception as exc:
                self.app.event_queue.put(("error", str(exc)))
                
        self.app.event_queue.put(("intro_done", True))

    def update(self, now_ms: int) -> None:
        while True:
            try:
                event, payload = self.app.event_queue.get_nowait()
            except queue.Empty:
                break

            if event == "state" and isinstance(payload, str):
                self.app.animator.set_state(payload, reset=True)
            elif event == "intro_done":
                self.app.switch_scene("main_menu")

    def render(self) -> None:
        screen = self.app.screen
        width, height = screen.get_size()
        screen.fill((0, 0, 0))
        
        padding = 16
        card_rect = pygame.Rect(padding, padding, width - padding * 2, height - padding * 2)
        pygame.draw.rect(screen, (255, 255, 255), card_rect, border_radius=0)

        avatar_frame = self.app.animator.current_frame()
        frame_w = max(1, avatar_frame.get_width())
        frame_h = max(1, avatar_frame.get_height())
        scale = max(width / frame_w, height / frame_h)

        target_size = (max(1, int(frame_w * scale)), max(1, int(frame_h * scale)))
        rendered_frame = pygame.transform.smoothscale(avatar_frame, target_size)
        avatar_target = rendered_frame.get_rect(center=(width // 2, height // 2))
        screen.blit(rendered_frame, avatar_target)
