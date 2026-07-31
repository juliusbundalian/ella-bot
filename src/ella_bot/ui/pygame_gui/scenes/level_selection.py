from __future__ import annotations

from typing import Dict

import pygame

from ella_bot.core.constants import LEVEL_ORDER
from ella_bot.ui.pygame_gui.scene import BaseScene
from ella_bot.services.sound_effects import play_button_click


_CARD_BG = (0, 0, 0)
_WHITE = (255, 255, 255)
_TEXT = (50, 50, 50)
_TEXT_MUTED = (95, 78, 84)
_OUTER_BORDER = (94, 42, 59)
_INNER_BORDER = (255, 185, 207)
_BTN_FILL = (255, 182, 193)
_BTN_PRESSED = (251, 165, 193)
_BTN_OUTLINE = (94, 42, 59)


class LevelSelectionScene(BaseScene):
    """Present every curriculum level as an enabled starting point."""

    def __init__(self, app):
        super().__init__(app)
        self.level_buttons: Dict[str, pygame.Rect] = {}
        self.back_button = None
        self.confirm_button = None
        self.cancel_button = None
        self.pending_level: str | None = None
        self.show_confirmation = False
        self.pressed_button: str | None = None

    def on_enter(self) -> None:
        self.pending_level = None
        self.show_confirmation = False
        self.pressed_button = None

    def _select_level(self, level: str) -> None:
        if level in LEVEL_ORDER:
            self.pending_level = level
            self.show_confirmation = True

    def _confirm_level(self) -> None:
        if self.pending_level is None:
            return
        if self.app.start_new_session(self.pending_level):
            self.show_confirmation = False
            self.app.switch_scene("reading_prompt")
            self.app.active_scene._start_attempt()

    def _cancel_confirmation(self) -> None:
        self.pending_level = None
        self.show_confirmation = False

    def _go_back(self) -> None:
        self.app.switch_scene("main_menu")

    def handle_event(self, event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_mouse_down(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._handle_mouse_up(event.pos)

    def _handle_mouse_down(self, mouse_pos) -> None:
        if self.show_confirmation:
            if self.confirm_button and self.confirm_button.collidepoint(mouse_pos):
                self.pressed_button = "confirm"
            elif self.cancel_button and self.cancel_button.collidepoint(mouse_pos):
                self.pressed_button = "cancel"
            if self.pressed_button:
                play_button_click()
            return
        for level, rect in self.level_buttons.items():
            if rect.collidepoint(mouse_pos):
                self.pressed_button = f"level:{level}"
                play_button_click()
                return
        if self.back_button and self.back_button.collidepoint(mouse_pos):
            self.pressed_button = "back"
            play_button_click()

    def _handle_mouse_up(self, mouse_pos) -> None:
        pressed = self.pressed_button
        self.pressed_button = None
        if pressed == "confirm" and self.confirm_button and self.confirm_button.collidepoint(mouse_pos):
            self._confirm_level()
        elif pressed == "cancel" and self.cancel_button and self.cancel_button.collidepoint(mouse_pos):
            self._cancel_confirmation()
        elif pressed == "back" and self.back_button and self.back_button.collidepoint(mouse_pos):
            self._go_back()
        elif pressed and pressed.startswith("level:"):
            level = pressed.split(":", 1)[1]
            rect = self.level_buttons.get(level)
            if rect and rect.collidepoint(mouse_pos):
                self._select_level(level)

    def _draw_button(
        self,
        screen,
        rect: pygame.Rect,
        label: str,
        key: str,
        *,
        font=None,
    ) -> None:
        is_pressed = self.pressed_button == key
        fill = _BTN_PRESSED if is_pressed else _BTN_FILL
        if not is_pressed:
            shadow = rect.move(4, 4)
            pygame.draw.rect(screen, _BTN_OUTLINE, shadow, border_radius=16)
        pygame.draw.rect(screen, fill, rect, border_radius=16)
        pygame.draw.rect(screen, _BTN_OUTLINE, rect, width=2, border_radius=16)
        label_font = font or self.app.font_button
        surface = label_font.render(label, True, _WHITE)
        screen.blit(surface, surface.get_rect(center=rect.center))

    def render(self) -> None:
        screen = self.app.screen
        width, height = screen.get_size()
        outer_rect = pygame.Rect(0, 0, width, height)
        inner_rect = outer_rect.inflate(-64, -64)

        pygame.draw.rect(screen, _CARD_BG, outer_rect)
        pygame.draw.rect(screen, _WHITE, outer_rect.inflate(-24, -24), border_radius=56)
        pygame.draw.rect(screen, _WHITE, inner_rect, border_radius=36)

        title = self.app.font_title.render("Choose a Level", True, _TEXT)
        screen.blit(title, title.get_rect(centerx=inner_rect.centerx, top=inner_rect.top + 22))
        subtitle = self.app.font_body.render(
            "All levels are available. Pick where you would like to begin.",
            True,
            _TEXT_MUTED,
        )
        screen.blit(
            subtitle,
            subtitle.get_rect(centerx=inner_rect.centerx, top=inner_rect.top + 92),
        )

        self.level_buttons = {}
        groups = [
            ("Level 1", LEVEL_ORDER[:7]),
            ("Level 2", LEVEL_ORDER[7:11]),
            ("Levels 3 and 4", LEVEL_ORDER[11:]),
        ]
        row_tops = [inner_rect.top + 158, inner_rect.top + 282, inner_rect.top + 406]
        button_h = 62
        gap = 16
        max_button_w = 118
        available_w = inner_rect.width - 100

        for (group_label, levels), row_top in zip(groups, row_tops):
            label = self.app.font_small.render(group_label, True, _TEXT_MUTED)
            screen.blit(label, label.get_rect(centerx=inner_rect.centerx, top=row_top))
            button_w = min(
                max_button_w,
                (available_w - gap * (len(levels) - 1)) // len(levels),
            )
            total_w = len(levels) * button_w + (len(levels) - 1) * gap
            x = inner_rect.centerx - total_w // 2
            y = row_top + 32
            for level in levels:
                rect = pygame.Rect(x, y, button_w, button_h)
                self.level_buttons[level] = rect
                self._draw_button(
                    screen,
                    rect,
                    level.upper(),
                    f"level:{level}",
                    font=self.app.font_body,
                )
                x += button_w + gap

        self.back_button = pygame.Rect(inner_rect.left + 36, inner_rect.bottom - 78, 150, 58)
        self._draw_button(
            screen,
            self.back_button,
            "Back",
            "back",
            font=self.app.font_body,
        )

        pygame.draw.rect(screen, _OUTER_BORDER, outer_rect, width=12, border_radius=68)
        pygame.draw.rect(screen, _INNER_BORDER, inner_rect, width=12, border_radius=36)

        if self.show_confirmation:
            self._draw_confirmation(screen, width, height)

    def _draw_confirmation(self, screen, width: int, height: int) -> None:
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        dlg_w = min(700, int(width * 0.64))
        dlg_h = min(340, int(height * 0.52))
        dialog = pygame.Rect(
            (width - dlg_w) // 2,
            (height - dlg_h) // 2,
            dlg_w,
            dlg_h,
        )
        pygame.draw.rect(screen, _WHITE, dialog, border_radius=24)
        pygame.draw.rect(screen, _BTN_OUTLINE, dialog, width=4, border_radius=24)

        level = self.pending_level.upper() if self.pending_level else ""
        title = self.app.font_title.render(f"Start Level {level}?", True, _TEXT)
        screen.blit(title, title.get_rect(centerx=dialog.centerx, top=dialog.top + 34))
        warning = self.app.font_body.render(
            "Starting here will replace any previously saved progress.",
            True,
            _TEXT_MUTED,
        )
        screen.blit(
            warning,
            warning.get_rect(centerx=dialog.centerx, top=dialog.top + 130),
        )

        btn_w, btn_h, gap = 190, 66, 24
        btn_y = dialog.bottom - btn_h - 32
        self.confirm_button = pygame.Rect(
            dialog.centerx - gap // 2 - btn_w,
            btn_y,
            btn_w,
            btn_h,
        )
        self.cancel_button = pygame.Rect(
            dialog.centerx + gap // 2,
            btn_y,
            btn_w,
            btn_h,
        )
        self._draw_button(
            screen,
            self.confirm_button,
            "Confirm",
            "confirm",
            font=self.app.font_body,
        )
        self._draw_button(
            screen,
            self.cancel_button,
            "Cancel",
            "cancel",
            font=self.app.font_body,
        )
