import pygame

from ella_bot.ui.pygame_gui.scene import BaseScene

_CARD_BG = (0, 0, 0)
_WHITE = (255, 255, 255)
_OUTER_BORDER = (94, 42, 59)
_INNER_BORDER = (255, 185, 207)
_BTN_FILL = (255, 182, 193)
_BTN_OUTLINE = (94, 42, 59)
_BTN_PRESSED = (251, 165, 193)
_BTN_DISABLED = (210, 210, 210)
_TEXT_DARK = (56, 56, 56)
_TITLE_COLOR = (230, 127, 159)
_RATING_COLORS = {"A": (60, 160, 90), "B": (60, 160, 90), "C": (210, 150, 40),
                  "D": (200, 70, 80), "F": (200, 70, 80)}

_SUBTEXT = {"A": "Amazing reading!", "B": "Great job!", "C": "Nice work!",
            "D": "Keep practicing — you've got this!", "F": "Keep practicing — you've got this!"}


class ResultsScene(BaseScene):
    def __init__(self, app):
        super().__init__(app)
        self.pressed_button = None
        self._rating_font = None
        self.next_button = None
        self.retry_button = None
        self.menu_button = None

    def on_enter(self) -> None:
        self.pressed_button = None

    # --- actions (unit-tested) ---

    def _do_next(self) -> None:
        result = self.app.latest_result
        if not getattr(result, "passed", False):
            return
        self.app.session.advance_to_higher_stage()
        self.app.switch_scene("reading_prompt")
        self.app.active_scene._start_attempt()

    def _do_retry(self) -> None:
        result = self.app.latest_result
        if self.app.latest_result_kind == "tier":
            self.app.session.retry_tier(result.tier)
            self.app.evaluation.reset_tier(result.tier)
        else:
            self.app.session.retry_sublevel(result.level)
            self.app.evaluation.reset_sublevel(result.level)
        self.app.switch_scene("reading_prompt")
        self.app.active_scene._start_attempt()

    def _do_main_menu(self) -> None:
        self.app.switch_scene("main_menu")

    # --- input ---

    def handle_event(self, event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for key, rect in (("next", self.next_button), ("retry", self.retry_button),
                              ("menu", self.menu_button)):
                if rect and rect.collidepoint(event.pos):
                    self.pressed_button = key
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            key = self.pressed_button
            self.pressed_button = None
            if key == "next" and self.next_button and self.next_button.collidepoint(event.pos):
                self._do_next()
            elif key == "retry" and self.retry_button and self.retry_button.collidepoint(event.pos):
                self._do_retry()
            elif key == "menu" and self.menu_button and self.menu_button.collidepoint(event.pos):
                self._do_main_menu()

    # --- rendering ---

    def _draw_button(self, screen, rect, label, key, enabled=True) -> None:
        if not enabled:
            pygame.draw.rect(screen, _BTN_DISABLED, rect, border_radius=20)
            pygame.draw.rect(screen, _BTN_OUTLINE, rect, width=2, border_radius=20)
            surf = self.app.font_body.render(label, True, _WHITE)
            screen.blit(surf, surf.get_rect(center=rect.center))
            return
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
        kind = self.app.latest_result_kind

        prompt_rect = pygame.Rect(0, 0, width, height)
        pygame.draw.rect(screen, _CARD_BG, prompt_rect, border_radius=0)
        inner_rect = prompt_rect.inflate(-64, -64)
        pygame.draw.rect(screen, _WHITE, prompt_rect.inflate(-24, -24), border_radius=56)
        pygame.draw.rect(screen, _WHITE, inner_rect, border_radius=36)

        if kind == "tier":
            headline = f"Level {result.tier} Complete — Level Up!"
            next_label = "Next Level"
        else:
            headline = f"Sub-Level {result.level.upper()} Complete!"
            next_label = "Continue"

        title = self.app.font_title.render(headline, True, _TITLE_COLOR)
        screen.blit(title, title.get_rect(centerx=inner_rect.centerx, top=inner_rect.top + 36))

        sub = self.app.font_body.render(_SUBTEXT.get(result.rating, ""), True, _TEXT_DARK)
        screen.blit(sub, sub.get_rect(centerx=inner_rect.centerx, top=inner_rect.top + 120))

        if self._rating_font is None:
            self._rating_font = self.app._get_sys_font(160, bold=True)
        letter = self._rating_font.render(result.rating, True, _RATING_COLORS.get(result.rating, _TEXT_DARK))
        screen.blit(letter, letter.get_rect(center=(inner_rect.centerx, inner_rect.centery - 20)))

        fluency = self.app.font_body.render(f"Fluency: {round(result.fluency * 100)}%", True, _TEXT_DARK)
        screen.blit(fluency, fluency.get_rect(centerx=inner_rect.centerx, centery=inner_rect.centery + 90))

        correct = self.app.font_body.render(
            f"Read first try: {result.first_try_correct} / {result.items_total}", True, _TEXT_DARK)
        screen.blit(correct, correct.get_rect(centerx=inner_rect.centerx, centery=inner_rect.centery + 140))

        btn_w, btn_h, gap = 280, 80, 24
        total_w = btn_w * 3 + gap * 2
        x0 = inner_rect.centerx - total_w // 2
        y = inner_rect.bottom - btn_h - 48
        self.next_button = pygame.Rect(x0, y, btn_w, btn_h)
        self.retry_button = pygame.Rect(x0 + btn_w + gap, y, btn_w, btn_h)
        self.menu_button = pygame.Rect(x0 + (btn_w + gap) * 2, y, btn_w, btn_h)
        self._draw_button(screen, self.next_button, next_label, "next", enabled=bool(result.passed))
        self._draw_button(screen, self.retry_button, "Try Again", "retry")
        self._draw_button(screen, self.menu_button, "Main Menu", "menu")

        pygame.draw.rect(screen, _OUTER_BORDER, prompt_rect, width=12, border_radius=68)
        pygame.draw.rect(screen, _INNER_BORDER, inner_rect, width=12, border_radius=36)
