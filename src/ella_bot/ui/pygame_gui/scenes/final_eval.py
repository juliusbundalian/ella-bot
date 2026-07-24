import pygame

from ella_bot.ui.pygame_gui.scene import BaseScene
from ella_bot.utils.file_utils import resolve_asset_path

_CARD_BG = (0, 0, 0)
_WHITE = (255, 255, 255)
_OUTER_BORDER = (94, 42, 59)
_INNER_BORDER = (255, 185, 207)
_BTN_FILL = (255, 182, 193)
_BTN_OUTLINE = (94, 42, 59)
_BTN_PRESSED = (251, 165, 193)
_TEXT_DARK = (56, 56, 56)
_VALUE_PINK = (255, 155, 185)
_RATING_STROKE = (246, 162, 188)


class FinalEvaluationScene(BaseScene):
    def __init__(self, app):
        super().__init__(app)
        self.pressed_button = None
        self._ribbon_img = None
        self._font_letter = None
        self._font_stats = None
        self._font_complete = None
        self.play_button = None
        self.menu_button = None

    def on_enter(self) -> None:
        self.pressed_button = None

    # --- actions (unit-tested) ---

    def _do_play_again(self) -> None:
        if self.app.start_new_session("1a"):
            self.app.switch_scene("reading_prompt")
            self.app.active_scene._start_attempt()

    def _do_main_menu(self) -> None:
        self.app.switch_scene("main_menu")

    # --- input ---

    def handle_event(self, event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for key, rect in (("play", self.play_button), ("menu", self.menu_button)):
                if rect and rect.collidepoint(event.pos):
                    self.pressed_button = key
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            key = self.pressed_button
            self.pressed_button = None
            if key == "play" and self.play_button and self.play_button.collidepoint(event.pos):
                self._do_play_again()
            elif key == "menu" and self.menu_button and self.menu_button.collidepoint(event.pos):
                self._do_main_menu()

    # --- rendering ---

    def _load_assets(self) -> None:
        if self._ribbon_img is None:
            try:
                self._ribbon_img = pygame.image.load(
                    str(resolve_asset_path("assets/img_ribbon_banner.png"))
                ).convert_alpha()
            except Exception:
                self._ribbon_img = False
        if self._font_letter is None:
            self._font_letter = self.app._get_sys_font(250)
        if self._font_stats is None:
            self._font_stats = self.app._get_sys_font(40)
        if self._font_complete is None:
            self._font_complete = self.app._get_sys_font(82)

    def _draw_outlined_letter(self, screen, x, y) -> None:
        letter = self.app.latest_result.overall_rating
        shadow = self._font_letter.render(letter, True, _TEXT_DARK)
        screen.blit(shadow, (x + 8, y + 8))
        stroke = self._font_letter.render(letter, True, _RATING_STROKE)
        for offset in ((4, 0), (-4, 0), (0, 4), (0, -4),
                       (4, 4), (4, -4), (-4, 4), (-4, -4)):
            screen.blit(stroke, (x + offset[0], y + offset[1]))
        screen.blit(self._font_letter.render(letter, True, _WHITE), (x, y))

    def _draw_button(self, screen, rect, label, key) -> None:
        is_pressed = self.pressed_button == key
        bg = _BTN_PRESSED if is_pressed else _BTN_FILL
        if not is_pressed:
            pygame.draw.rect(screen, _BTN_OUTLINE,
                             pygame.Rect(rect.left + 4, rect.top + 4, rect.width, rect.height),
                             border_radius=20)
        pygame.draw.rect(screen, bg, rect, border_radius=20)
        pygame.draw.rect(screen, _BTN_OUTLINE, rect, width=2, border_radius=20)
        surf = self.app.font_body.render(label, True, _WHITE)
        screen.blit(surf, surf.get_rect(center=rect.center))

    def render(self) -> None:
        self._load_assets()
        screen = self.app.screen
        width, height = screen.get_size()
        result = self.app.latest_result

        prompt_rect = pygame.Rect(0, 0, width, height)
        pygame.draw.rect(screen, _CARD_BG, prompt_rect, border_radius=0)
        pygame.draw.rect(screen, _WHITE, prompt_rect.inflate(-24, -24), border_radius=56)
        inner_rect = prompt_rect.inflate(-64, -64)
        pygame.draw.rect(screen, _WHITE, inner_rect, border_radius=36)

        ix, iy = inner_rect.x, inner_rect.y
        ribbon_w, ribbon_h = 760, 190
        ribbon_x = inner_rect.centerx - ribbon_w // 2
        ribbon_y = iy + 50
        if self._ribbon_img:
            ribbon = pygame.transform.smoothscale(self._ribbon_img, (ribbon_w, ribbon_h))
            screen.blit(ribbon, (ribbon_x, ribbon_y))
        else:
            pygame.draw.rect(screen, _INNER_BORDER,
                             pygame.Rect(ribbon_x, ribbon_y, ribbon_w, ribbon_h), border_radius=20)

        ribbon_cx = inner_rect.centerx
        levels = self.app.font_body.render("ALL LEVELS", True, _TEXT_DARK)
        screen.blit(levels, levels.get_rect(centerx=ribbon_cx, top=ribbon_y + 20))
        complete = self._font_complete.render("COMPLETE!", True, _WHITE)
        complete_shadow = self._font_complete.render("COMPLETE!", True, _TEXT_DARK)
        complete_rect = complete.get_rect(centerx=ribbon_cx, top=ribbon_y + 45)
        screen.blit(complete_shadow, (complete_rect.x + 2, complete_rect.y + 3))
        screen.blit(complete, complete_rect)

        btn_h = 70
        btn_y = inner_rect.bottom - btn_h - 48
        content_cy = (ribbon_y + ribbon_h + btn_y) // 2
        letter = self._font_letter.render(result.overall_rating, True, _WHITE)
        rating_label = self._font_stats.render("Rating", True, _TEXT_DARK)
        label_gap = 18
        group_width = rating_label.get_width() + label_gap + letter.get_width()
        left_center = ix + inner_rect.width * 3 // 8
        group_left = left_center - group_width // 2
        letter_x = group_left + rating_label.get_width() + label_gap
        letter_y = content_cy - letter.get_height() // 2 - 23
        self._draw_outlined_letter(screen, letter_x, letter_y)
        screen.blit(rating_label, rating_label.get_rect(left=group_left, centery=content_cy - 23))

        label_x = inner_rect.centerx + 30
        row_spacing = 68
        rows = [
            ("Score:", f"{result.first_try_correct}/{result.items_total}", content_cy - row_spacing // 2 - 30),
            ("Fluency:", f"{round(result.overall_fluency * 100)}%", content_cy + row_spacing // 2 - 30),
        ]
        for label, value, row_y in rows:
            label_surface = self._font_stats.render(label, True, _TEXT_DARK)
            value_surface = self._font_stats.render(value, True, _VALUE_PINK)
            screen.blit(label_surface, (label_x, row_y))
            screen.blit(value_surface, (label_x + label_surface.get_width() + 14, row_y))

        btn_w = 297
        total_width = btn_w * 2 + 50
        btn_x = inner_rect.centerx - total_width // 2
        self.menu_button = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
        self.play_button = pygame.Rect(btn_x + btn_w + 50, btn_y, btn_w, btn_h)
        self._draw_button(screen, self.play_button, "Play Again", "play")
        self._draw_button(screen, self.menu_button, "Main Menu", "menu")

        pygame.draw.rect(screen, _OUTER_BORDER, prompt_rect, width=12, border_radius=68)
        pygame.draw.rect(screen, _INNER_BORDER, inner_rect, width=12, border_radius=36)
