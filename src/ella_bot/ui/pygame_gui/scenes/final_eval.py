import pygame

from ella_bot.ui.pygame_gui.scene import BaseScene
from ella_bot.services.evaluation import EvaluationService

_CARD_BG = (0, 0, 0)
_WHITE = (255, 255, 255)
_OUTER_BORDER = (94, 42, 59)
_INNER_BORDER = (255, 185, 207)
_BTN_FILL = (255, 182, 193)
_BTN_OUTLINE = (94, 42, 59)
_BTN_PRESSED = (251, 165, 193)
_TEXT_DARK = (56, 56, 56)
_TITLE_COLOR = (230, 127, 159)
_RATING_COLORS = {"A": (60, 160, 90), "B": (60, 160, 90), "C": (210, 150, 40),
                  "D": (200, 70, 80), "F": (200, 70, 80)}


class FinalEvaluationScene(BaseScene):
    def __init__(self, app):
        super().__init__(app)
        self.pressed_button = None
        self._rating_font = None
        self.play_button = None
        self.menu_button = None

    def on_enter(self) -> None:
        self.pressed_button = None

    # --- actions (unit-tested) ---

    def _do_play_again(self) -> None:
        self.app.session.reset_to_start()
        self.app.evaluation = EvaluationService(
            log_path=self.app.evaluation.log_path,
            pass_bar=self.app.evaluation.pass_bar,
        )
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
        screen = self.app.screen
        width, height = screen.get_size()
        result = self.app.latest_result

        prompt_rect = pygame.Rect(0, 0, width, height)
        pygame.draw.rect(screen, _CARD_BG, prompt_rect, border_radius=0)
        inner_rect = prompt_rect.inflate(-64, -64)
        pygame.draw.rect(screen, _WHITE, prompt_rect.inflate(-24, -24), border_radius=56)
        pygame.draw.rect(screen, _WHITE, inner_rect, border_radius=36)

        title = self.app.font_title.render("All Levels Complete!", True, _TITLE_COLOR)
        screen.blit(title, title.get_rect(centerx=inner_rect.centerx, top=inner_rect.top + 32))

        if self._rating_font is None:
            self._rating_font = self.app._get_sys_font(120, bold=True)
        letter = self._rating_font.render(
            result.overall_rating, True, _RATING_COLORS.get(result.overall_rating, _TEXT_DARK))
        screen.blit(letter, letter.get_rect(centerx=inner_rect.centerx, top=inner_rect.top + 110))

        fluency = self.app.font_body.render(
            f"Overall Fluency: {round(result.overall_fluency * 100)}%", True, _TEXT_DARK)
        screen.blit(fluency, fluency.get_rect(centerx=inner_rect.centerx, top=inner_rect.top + 250))

        row_y = inner_rect.top + 300
        for tier in result.tiers:
            row = self.app.font_body.render(
                f"Level {tier.tier}   ·   {tier.rating}   ·   {round(tier.fluency * 100)}%",
                True, _TEXT_DARK)
            screen.blit(row, row.get_rect(centerx=inner_rect.centerx, top=row_y))
            row_y += 40

        totals = self.app.font_body.render(
            f"Read first try: {result.first_try_correct} / {result.items_total}", True, _TEXT_DARK)
        screen.blit(totals, totals.get_rect(centerx=inner_rect.centerx, top=row_y + 12))

        btn_w, btn_h, gap = 300, 80, 28
        total_w = btn_w * 2 + gap
        x0 = inner_rect.centerx - total_w // 2
        y = inner_rect.bottom - btn_h - 48
        self.play_button = pygame.Rect(x0, y, btn_w, btn_h)
        self.menu_button = pygame.Rect(x0 + btn_w + gap, y, btn_w, btn_h)
        self._draw_button(screen, self.play_button, "Play Again", "play")
        self._draw_button(screen, self.menu_button, "Main Menu", "menu")

        pygame.draw.rect(screen, _OUTER_BORDER, prompt_rect, width=12, border_radius=68)
        pygame.draw.rect(screen, _INNER_BORDER, inner_rect, width=12, border_radius=36)
