from __future__ import annotations

from typing import Dict

import pygame

from ella_bot.core.constants import LEVEL_ORDER
from ella_bot.ui.pygame_gui.scene import BaseScene
from ella_bot.ui.pygame_gui.components.button import Button
from ella_bot.ui.pygame_gui.lottie_bg import LottieBackground
from ella_bot.utils.file_utils import resolve_asset_path
from ella_bot.services.sound_effects import play_button_click


_CARD_BG = (0, 0, 0)
_WHITE = (255, 255, 255)
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
        self._lottie_bg = None

    def on_enter(self) -> None:
        self.pending_level = None
        self.show_confirmation = False
        self.pressed_button = None

    def _load_assets(self) -> None:
        if self._lottie_bg is None:
            try:
                reading_bg_path = resolve_asset_path("assets/Reading_bg.lottie")
                final_lightray_path = resolve_asset_path("assets/Final_Lightray.lottie")
                lightray_path = resolve_asset_path("assets/Lightray.lottie")
                if reading_bg_path.exists():
                    self._lottie_bg = LottieBackground(reading_bg_path)
                elif final_lightray_path.exists():
                    self._lottie_bg = LottieBackground(final_lightray_path)
                elif lightray_path.exists():
                    self._lottie_bg = LottieBackground(lightray_path)
            except Exception:
                self._lottie_bg = False

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
        if isinstance(surface, pygame.Surface):
            screen.blit(surface, surface.get_rect(center=rect.center))

    def render(self) -> None:
        self._load_assets()
        screen = self.app.screen
        width, height = screen.get_size()
        now_ms = pygame.time.get_ticks()

        # 1. Render Lottie Background (matching level/main menu)
        if self._lottie_bg:
            vf = self._lottie_bg.get_frame(now_ms, (width, height))
            if vf:
                screen.blit(vf, (0, 0))
            else:
                screen.fill(_CARD_BG)
        else:
            screen.fill(_CARD_BG)

        # 2. Title & Subtitle directly over background matching word color in levels
        cx = width // 2
        title = self.app.font_title.render("Choose a Level", True, (56, 56, 56))
        if isinstance(title, pygame.Surface):
            screen.blit(title, title.get_rect(centerx=cx, top=45))

        subtitle = self.app.font_body.render(
            "All levels are available. Pick where you would like to begin.",
            True,
            (56, 56, 56),
        )
        if isinstance(subtitle, pygame.Surface):
            screen.blit(
                subtitle,
                subtitle.get_rect(centerx=cx, top=115),
            )

        # 3. Level Groups & Yellow 3D Buttons
        self.level_buttons = {}
        groups = [
            ("Level 1", LEVEL_ORDER[:7]),
            ("Level 2", LEVEL_ORDER[7:11]),
            ("Levels 3 and 4", LEVEL_ORDER[11:]),
        ]
        row_tops = [175, 305, 435]
        button_h = 62
        gap = 16
        max_button_w = 118
        available_w = width - 128

        for (group_label, levels), row_top in zip(groups, row_tops):
            label = self.app.font_small.render(group_label, True, (56, 56, 56))
            if isinstance(label, pygame.Surface):
                screen.blit(label, label.get_rect(centerx=cx, top=row_top))
            button_w = min(
                max_button_w,
                (available_w - gap * (len(levels) - 1)) // len(levels),
            )
            total_w = len(levels) * button_w + (len(levels) - 1) * gap
            x = cx - total_w // 2
            y = row_top + 32
            for level in levels:
                rect = pygame.Rect(x, y, button_w, button_h)
                self.level_buttons[level] = rect
                btn = Button(
                    rect,
                    label=level.upper(),
                    variant="yellow",
                    font=self.app.font_body,
                    stroke_weight=5,
                    corner_radius=20,
                )
                btn.is_pressed = (self.pressed_button == f"level:{level}")
                btn.draw(screen)
                x += button_w + gap

        # 4. Violet Back Button (shifted further right for optimal alignment)
        self.back_button = pygame.Rect(160, height - 90, 160, 58)
        font_btn = getattr(self.app, "font_button", None)
        btn_font = font_btn if isinstance(font_btn, pygame.font.Font) else self.app.font_body
        back_btn = Button(
            self.back_button,
            label="Back",
            variant="violet",
            font=btn_font,
            stroke_weight=5,
        )
        back_btn.is_pressed = (self.pressed_button == "back")
        back_btn.draw(screen)

        if self.show_confirmation:
            self._draw_confirmation(screen, width, height)

    def _get_adaptive_font(self, size: int, bold: bool = False):
        if hasattr(self.app, "_get_sys_font"):
            try:
                res = self.app._get_sys_font(size, bold=bold)
                if isinstance(res, pygame.font.Font):
                    return res
            except Exception:
                pass
        font = getattr(self.app, "font_body", None)
        if isinstance(font, pygame.font.Font):
            return font
        return pygame.font.SysFont(None, size, bold=bold)

    def _render_adaptive_text(self, text: str, size: int, color: tuple, max_w: int, bold: bool = False):
        font = self._get_adaptive_font(size, bold=bold)
        surf = font.render(text, True, color)
        if isinstance(surf, pygame.Surface):
            if max_w > 0 and surf.get_width() > max_w:
                scale_ratio = max_w / surf.get_width()
                new_w = max_w
                new_h = max(1, int(surf.get_height() * scale_ratio))
                surf = pygame.transform.smoothscale(surf, (new_w, new_h))
            return surf
        return None

    def _draw_confirmation(self, screen, width: int, height: int) -> None:
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        dlg_w = min(680, max(360, int(width * 0.66)))
        dlg_h = min(320, max(220, int(height * 0.48)))
        dialog = pygame.Rect(
            (width - dlg_w) // 2,
            (height - dlg_h) // 2,
            dlg_w,
            dlg_h,
        )
        pygame.draw.rect(screen, (25, 5, 35), dialog.move(4, 4), border_radius=30)
        pygame.draw.rect(screen, (87, 39, 108), dialog, border_radius=30)
        pygame.draw.rect(screen, (127, 63, 151), dialog, width=6, border_radius=30)

        level = self.pending_level.upper() if self.pending_level else ""
        title_size = max(22, min(38, int(dlg_h * 0.14)))
        title = self._render_adaptive_text(f"Start Level {level}?", title_size, (255, 250, 243), max_w=dlg_w - 40, bold=True)
        if title:
            screen.blit(title, title.get_rect(centerx=dialog.centerx, top=dialog.top + int(dlg_h * 0.10)))

        warning = self.app.font_body.render(
            "Starting here will replace any previously saved progress.",
            True,
            (227, 198, 236),
        )
        if isinstance(warning, pygame.Surface):
            if warning.get_width() > dlg_w - 40:
                scale = (dlg_w - 40) / warning.get_width()
                warning = pygame.transform.smoothscale(warning, (dlg_w - 40, max(1, int(warning.get_height() * scale))))
            screen.blit(
                warning,
                warning.get_rect(centerx=dialog.centerx, top=dialog.top + int(dlg_h * 0.35)),
            )

        btn_w = min(190, (dlg_w - 60) // 2)
        btn_h = min(58, max(42, int(dlg_h * 0.24)))
        gap = 20
        btn_y = dialog.bottom - btn_h - int(dlg_h * 0.10)
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

        button_font_size = max(18, min(28, int(btn_h * 0.50)))
        button_font = self._get_adaptive_font(button_font_size, bold=True)

        btn_confirm = Button(
            self.confirm_button,
            label="Confirm",
            variant="yellow",
            font=button_font,
            stroke_weight=5,
        )
        btn_confirm.is_pressed = (self.pressed_button == "confirm")
        btn_confirm.draw(screen)

        btn_cancel = Button(
            self.cancel_button,
            label="Cancel",
            variant="yellow",
            font=button_font,
            stroke_weight=5,
        )
        btn_cancel.is_pressed = (self.pressed_button == "cancel")
        btn_cancel.draw(screen)
