from __future__ import annotations

from typing import Optional

import pygame


class PauseModal:
    """Pause overlay with a nested confirm dialog. Owns its own rects."""

    def __init__(self) -> None:
        self.show_pause = False
        self.show_confirm = False
        self.confirm_action: Optional[str] = None  # "main_menu" | "exit"

        self.resume_rect: Optional[pygame.Rect] = None
        self.main_menu_rect: Optional[pygame.Rect] = None
        self.exit_rect: Optional[pygame.Rect] = None
        self.close_rect: Optional[pygame.Rect] = None
        self.confirm_yes_rect: Optional[pygame.Rect] = None
        self.confirm_no_rect: Optional[pygame.Rect] = None

    @property
    def visible(self) -> bool:
        return self.show_pause or self.show_confirm

    def open(self) -> None:
        self.show_pause = True

    def close(self) -> None:
        self.show_pause = False
        self.show_confirm = False
        self.confirm_action = None

    def hit_test(self, pos) -> Optional[str]:
        """Return a semantic action for a left-click, or None.

        Actions: "resume", "ask_main_menu", "ask_exit",
                 "confirm_yes", "confirm_no", "close", "consumed".
        """
        if self.show_confirm:
            if self.close_rect and self.close_rect.collidepoint(pos):
                return "close"
            if self.confirm_yes_rect and self.confirm_yes_rect.collidepoint(pos):
                return "confirm_yes"
            if self.confirm_no_rect and self.confirm_no_rect.collidepoint(pos):
                return "confirm_no"
            return "consumed"

        if self.show_pause:
            if self.close_rect and self.close_rect.collidepoint(pos):
                return "resume"
            if self.resume_rect and self.resume_rect.collidepoint(pos):
                return "resume"
            if self.main_menu_rect and self.main_menu_rect.collidepoint(pos):
                return "ask_main_menu"
            if self.exit_rect and self.exit_rect.collidepoint(pos):
                return "ask_exit"
            return "consumed"

        return None

    def render(self, screen, font_body, font_small, prompt_rect) -> None:
        if not self.visible:
            return

        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        screen.blit(overlay, (0, 0))

        dialog_w = int(prompt_rect.width * 0.55)
        dialog_h = int(prompt_rect.height * 0.50)
        dialog_x = prompt_rect.centerx - dialog_w // 2
        dialog_y = prompt_rect.centery - dialog_h // 2
        dialog_rect = pygame.Rect(dialog_x, dialog_y, dialog_w, dialog_h)

        header_height = 92
        header_rect = pygame.Rect(dialog_rect.left, dialog_rect.top, dialog_rect.width, header_height)
        body_rect = pygame.Rect(
            dialog_rect.left, dialog_rect.top + header_height, dialog_rect.width, dialog_rect.height - header_height
        )

        outer_bg = (255, 240, 245)
        header_bg = (255, 217, 228)
        pygame.draw.rect(screen, outer_bg, dialog_rect, border_radius=24)
        pygame.draw.rect(screen, header_bg, header_rect, border_radius=24)
        pygame.draw.rect(screen, (255, 255, 255), body_rect, border_radius=24)
        pygame.draw.rect(screen, (230, 127, 159), dialog_rect, width=6, border_radius=24)

        title_text = "Paused" if not self.show_confirm else "Confirm"
        title_surf = font_body.render(title_text, True, (40, 40, 40))
        title_rect = title_surf.get_rect(topleft=(dialog_rect.left + 24, dialog_rect.top + 24))
        screen.blit(title_surf, title_rect)

        button_w = int(dialog_rect.width * 0.82)
        close_size = 48
        close_rect = pygame.Rect(dialog_rect.right - close_size - 20, dialog_rect.top + 22, close_size, close_size)
        self.close_rect = close_rect
        pygame.draw.rect(screen, (255, 255, 255), close_rect, border_radius=14)
        pygame.draw.rect(screen, (230, 127, 159), close_rect, width=4, border_radius=14)
        pygame.draw.line(
            screen, (230, 127, 159),
            (close_rect.left + 14, close_rect.top + 14), (close_rect.right - 14, close_rect.bottom - 14), width=4,
        )
        pygame.draw.line(
            screen, (230, 127, 159),
            (close_rect.left + 14, close_rect.bottom - 14), (close_rect.right - 14, close_rect.top + 14), width=4,
        )
        left_x = dialog_rect.centerx - button_w // 2

        if self.show_confirm:
            msg = "Return to main menu?" if self.confirm_action == "main_menu" else "Exit the app?"
            msg_surf = font_small.render(msg, True, (50, 50, 50))
            msg_rect = msg_surf.get_rect(center=(dialog_rect.centerx, header_rect.bottom + 44))
            screen.blit(msg_surf, msg_rect)

            button_h = 72
            yes_rect = pygame.Rect(left_x, header_rect.bottom + 88, button_w, button_h)
            no_rect = pygame.Rect(left_x, header_rect.bottom + 88 + button_h + 16, button_w, button_h)
            self.confirm_yes_rect = yes_rect
            self.confirm_no_rect = no_rect
            self.main_menu_rect = None
            self.exit_rect = None

            shadow = pygame.Surface((button_w, button_h), pygame.SRCALPHA)
            shadow.fill((0, 0, 0, 40))
            screen.blit(shadow, (yes_rect.left, yes_rect.top + 6))
            screen.blit(shadow, (no_rect.left, no_rect.top + 6))

            pygame.draw.rect(screen, (255, 255, 255), yes_rect, border_radius=18)
            pygame.draw.rect(screen, (230, 127, 159), yes_rect, width=4, border_radius=18)
            yes_text = font_small.render("Yes", True, (40, 40, 40))
            screen.blit(yes_text, yes_text.get_rect(center=yes_rect.center))

            pygame.draw.rect(screen, (255, 255, 255), no_rect, border_radius=18)
            pygame.draw.rect(screen, (230, 127, 159), no_rect, width=4, border_radius=18)
            no_text = font_small.render("No", True, (40, 40, 40))
            screen.blit(no_text, no_text.get_rect(center=no_rect.center))
            return

        button_h = 78
        stack_gap = 20
        resume_rect = pygame.Rect(left_x, header_rect.bottom + 40, button_w, button_h)
        main_rect = pygame.Rect(left_x, resume_rect.bottom + stack_gap, button_w, button_h)
        exit_rect = pygame.Rect(left_x, main_rect.bottom + stack_gap, button_w, button_h)

        self.resume_rect = resume_rect
        self.main_menu_rect = main_rect
        self.exit_rect = exit_rect
        self.confirm_yes_rect = None
        self.confirm_no_rect = None

        shadow = pygame.Surface((button_w, button_h), pygame.SRCALPHA)
        shadow.fill((0, 0, 0, 28))
        screen.blit(shadow, (resume_rect.left, resume_rect.top + 6))
        screen.blit(shadow, (main_rect.left, main_rect.top + 6))
        screen.blit(shadow, (exit_rect.left, exit_rect.top + 6))

        for rect, label in ((resume_rect, "Resume"), (main_rect, "Main Menu"), (exit_rect, "Exit")):
            pygame.draw.rect(screen, (255, 255, 255), rect, border_radius=22)
            pygame.draw.rect(screen, (230, 127, 159), rect, width=4, border_radius=22)
            text = font_small.render(label, True, (40, 40, 40))
            screen.blit(text, text.get_rect(center=rect.center))
