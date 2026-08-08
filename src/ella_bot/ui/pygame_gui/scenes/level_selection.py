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

LEVEL_NAMES = {
    "1a": "Vowel Sounds",
    "1b": "Consonant Sounds",
    "1c": "Consonant Vowels - CV Pattern",
    "1d": "Vowel Diagraphs",
    "1e": "Consonant Digraphs",
    "1f": "Trigraphs and Quadgraphs",
    "1g": "Consonant Blends",
    "2a": "Sight Words",
    "2b": "Easy",
    "2c": "Average",
    "2d": "Difficult",
    "3": "Phrases",
    "4": "Full Sentences",
}

LEVEL_CAROUSEL_PAGES = (
    ("Level 1 - Practice Levels", ("1a", "1b", "1c", "1d")),
    ("Level 1 - Practice Levels", ("1e", "1f", "1g")),
    ("Level 2", ("2a", "2b", "2c", "2d")),
    ("Levels 3 and 4", ("3", "4")),
)


class LevelSelectionScene(BaseScene):
    """Present every curriculum level as an enabled starting point."""

    def __init__(self, app):
        super().__init__(app)
        self.level_buttons: Dict[str, pygame.Rect] = {}
        self.level_labels: Dict[str, str] = {}
        self.back_button = None
        self.carousel_page = 0
        self.carousel_previous_button: pygame.Rect | None = None
        self.carousel_next_button: pygame.Rect | None = None
        self.page_indicator_rects: list[pygame.Rect] = []
        self.page_indicator_states: list[bool] = []
        self.confirm_button = None
        self.cancel_button = None
        self.pending_level: str | None = None
        self.show_confirmation = False
        self.pressed_button: str | None = None
        self._lottie_bg = None

    def on_enter(self) -> None:
        from ella_bot.services.bgm_service import play_menu_bgm

        play_menu_bgm()
        self.pending_level = None
        self.show_confirmation = False
        self.pressed_button = None
        self.carousel_page = 0

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
        if (
            self.carousel_previous_button
            and self.carousel_previous_button.collidepoint(mouse_pos)
        ):
            self.pressed_button = "carousel_previous"
            play_button_click()
            return
        if (
            self.carousel_next_button
            and self.carousel_next_button.collidepoint(mouse_pos)
        ):
            self.pressed_button = "carousel_next"
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
        elif (
            pressed == "carousel_previous"
            and self.carousel_previous_button
            and self.carousel_previous_button.collidepoint(mouse_pos)
        ):
            self._change_carousel_page(-1)
        elif (
            pressed == "carousel_next"
            and self.carousel_next_button
            and self.carousel_next_button.collidepoint(mouse_pos)
        ):
            self._change_carousel_page(1)
        elif pressed == "back" and self.back_button and self.back_button.collidepoint(mouse_pos):
            self._go_back()
        elif pressed and pressed.startswith("level:"):
            level = pressed.split(":", 1)[1]
            rect = self.level_buttons.get(level)
            if rect and rect.collidepoint(mouse_pos):
                self._select_level(level)

    def _change_carousel_page(self, delta: int) -> None:
        last_page = len(LEVEL_CAROUSEL_PAGES) - 1
        self.carousel_page = max(0, min(self.carousel_page + delta, last_page))
        self.level_buttons = {}
        self.level_labels = {}

    def _draw_carousel_arrow(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        direction: int,
        enabled: bool,
        pressed: bool,
    ) -> None:
        fill = (70, 30, 90) if enabled else (65, 42, 73)
        if pressed and enabled:
            fill = (60, 24, 78)
        stroke = (127, 63, 151) if enabled else (91, 70, 98)
        icon = (255, 250, 243) if enabled else (145, 127, 151)
        if enabled and not pressed:
            pygame.draw.rect(
                screen,
                (35, 10, 45),
                rect.move(3, 3),
                border_radius=18,
            )
        pygame.draw.rect(screen, fill, rect, border_radius=18)
        pygame.draw.rect(screen, stroke, rect, width=4, border_radius=18)
        cx, cy = rect.center
        offset = 6 * direction
        pygame.draw.lines(
            screen,
            icon,
            False,
            [(cx - offset, cy - 12), (cx + offset, cy), (cx - offset, cy + 12)],
            width=5,
        )

    def _draw_level_card(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        level: str,
        level_name: str,
    ) -> None:
        card = Button(
            rect,
            label="",
            variant="yellow",
            corner_radius=20,
            stroke_weight=5,
        )
        card.is_pressed = self.pressed_button == f"level:{level}"
        card.draw(screen)

        code = self._render_adaptive_text(
            f"LEVEL {level.upper()}",
            27,
            (87, 39, 108),
            max_w=rect.width - 32,
            bold=True,
        )
        name = self._render_adaptive_text(
            level_name,
            21,
            (87, 39, 108),
            max_w=rect.width - 32,
        )
        if code:
            screen.blit(code, code.get_rect(centerx=rect.centerx, top=rect.top + 13))
        if name:
            screen.blit(name, name.get_rect(centerx=rect.centerx, bottom=rect.bottom - 15))

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

        # 3. Level carousel with named yellow cards
        self.level_buttons = {}
        self.level_labels = {}
        self.page_indicator_rects = []
        self.page_indicator_states = []
        self.carousel_page = max(
            0,
            min(self.carousel_page, len(LEVEL_CAROUSEL_PAGES) - 1),
        )
        group_label, levels = LEVEL_CAROUSEL_PAGES[self.carousel_page]

        group = self._render_adaptive_text(
            group_label,
            28,
            (56, 56, 56),
            max_w=width - 320,
            bold=True,
        )
        if group:
            screen.blit(group, group.get_rect(centerx=cx, top=166))

        card_gap = 18
        row_gap = 16
        grid_w = min(880, width - 360)
        card_w = (grid_w - card_gap) // 2
        card_h = 100
        cards_top = 207
        cards_area_h = card_h * 2 + row_gap

        arrow_w, arrow_h = 48, 72
        previous_rect = pygame.Rect(
            88,
            cards_top + (cards_area_h - arrow_h) // 2,
            arrow_w,
            arrow_h,
        )
        next_rect = pygame.Rect(
            width - 88 - arrow_w,
            previous_rect.top,
            arrow_w,
            arrow_h,
        )
        previous_enabled = self.carousel_page > 0
        next_enabled = self.carousel_page < len(LEVEL_CAROUSEL_PAGES) - 1
        self.carousel_previous_button = previous_rect if previous_enabled else None
        self.carousel_next_button = next_rect if next_enabled else None
        self._draw_carousel_arrow(
            screen,
            previous_rect,
            -1,
            previous_enabled,
            self.pressed_button == "carousel_previous",
        )
        self._draw_carousel_arrow(
            screen,
            next_rect,
            1,
            next_enabled,
            self.pressed_button == "carousel_next",
        )

        for index, level in enumerate(levels):
            row = index // 2
            row_start = row * 2
            row_count = min(2, len(levels) - row_start)
            row_width = row_count * card_w + (row_count - 1) * card_gap
            row_left = cx - row_width // 2
            column = index - row_start
            rect = pygame.Rect(
                row_left + column * (card_w + card_gap),
                cards_top + row * (card_h + row_gap),
                card_w,
                card_h,
            )
            self.level_buttons[level] = rect
            self.level_labels[level] = LEVEL_NAMES[level]
            self._draw_level_card(screen, rect, level, LEVEL_NAMES[level])

        dot_radius = 6
        dot_gap = 18
        indicators_y = cards_top + cards_area_h + 22
        page_count = len(LEVEL_CAROUSEL_PAGES)
        total_dot_w = page_count * dot_radius * 2 + (page_count - 1) * dot_gap
        dot_x = cx - total_dot_w // 2
        for index in range(page_count):
            dot_rect = pygame.Rect(
                dot_x + index * (dot_radius * 2 + dot_gap),
                indicators_y - dot_radius,
                dot_radius * 2,
                dot_radius * 2,
            )
            self.page_indicator_rects.append(dot_rect)
            is_current = index == self.carousel_page
            self.page_indicator_states.append(is_current)
            color = (242, 210, 20) if is_current else (127, 63, 151)
            pygame.draw.circle(screen, color, dot_rect.center, dot_radius)

        # 4. Centered Violet Back Button
        self.back_button = pygame.Rect(cx - 80, height - 90, 160, 58)
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
