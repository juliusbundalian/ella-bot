from __future__ import annotations

import time
import pygame
from ella_bot.ui.pygame_gui.scene import BaseScene
from ella_bot.utils.file_utils import resolve_asset_path
from ella_bot.services.sound_effects import play_level_sound, play_button_click
from ella_bot.ui.pygame_gui.components.confetti import ConfettiAnimation

_CARD_BG = (0, 0, 0)
_WHITE = (255, 255, 255)
_OUTER_BORDER = (94, 42, 59)
_INNER_BORDER = (255, 185, 207)
_BTN_FILL = (255, 182, 193)
_BTN_OUTLINE = (94, 42, 59)
_BTN_PRESSED = (251, 165, 193)
_BTN_DISABLED = (210, 210, 210)
_TEXT_DARK = (56, 56, 56)
_VALUE_PINK = (255, 155, 185)
_RATING_STROKE = (246, 162, 188)


def _fmt_duration(seconds: float) -> str:
    s = max(0, int(seconds))
    m, sec = divmod(s, 60)
    if m:
        return f"{m}min {sec}secs"
    return f"{sec}secs"


class ResultsScene(BaseScene):
    def __init__(self, app):
        super().__init__(app)
        self.pressed_button = None
        self._ribbon_img = None
        self._font_letter = None
        self._font_stats = None
        self._font_complete = None
        self._elapsed = None
        self.next_button = None
        self.menu_button = None
        self._show_menu_confirm = False
        self._confirm_continue_button = None
        self._confirm_restart_button = None
        self.confetti = ConfettiAnimation()

    def on_enter(self) -> None:
        self.pressed_button = None
        self._show_menu_confirm = False
        start = getattr(self.app, "sublevel_start_time", None)
        self._elapsed = (time.monotonic() - start) if start is not None else None

        result = getattr(self.app, "latest_result", None)
        if result is not None:
            passed = getattr(result, "passed", True)
            play_level_sound(passed)
            if passed:
                self.confetti.trigger(duration=4.0)


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

    # --- actions ---

    def _save_reading_transition_or_restore(self) -> bool:
        if self.app.save_active_session("reading"):
            return True
        self.app.continue_saved_session()
        return False

    def _do_next(self) -> None:
        result = self.app.latest_result
        if not getattr(result, "passed", False):
            return
        self.app.session.advance_to_higher_stage()
        if not self._save_reading_transition_or_restore():
            return
        self.app.switch_scene("reading_prompt")
        self.app.active_scene._start_attempt()

    def _reset_for_retry(self) -> None:
        result = self.app.latest_result
        if self.app.latest_result_kind == "tier":
            self.app.session.retry_tier(result.tier)
            self.app.evaluation.reset_tier(result.tier)
        else:
            self.app.session.retry_sublevel(result.level)
            self.app.evaluation.reset_sublevel(result.level)

    def _do_retry(self) -> None:
        self._reset_for_retry()
        if not self._save_reading_transition_or_restore():
            return
        self.app.switch_scene("reading_prompt")
        self.app.active_scene._start_attempt()

    def _do_main_menu(self) -> None:
        result = self.app.latest_result
        if not getattr(result, "passed", True):
            self._reset_for_retry()
            if not self._save_reading_transition_or_restore():
                return
            self.app.switch_scene("main_menu")
        else:
            self._show_menu_confirm = True

    def _do_continue_to_menu(self) -> None:
        self.app.session.advance_to_higher_stage()
        if not self._save_reading_transition_or_restore():
            return
        self.app.switch_scene("main_menu")

    def _do_restart_to_menu(self) -> None:
        if self.app.start_new_session("1a"):
            self.app.switch_scene("main_menu")

    # --- input ---

    def handle_event(self, event) -> None:
        if self._show_menu_confirm:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for key, rect in (
                    ("confirm_continue", self._confirm_continue_button),
                    ("confirm_restart", self._confirm_restart_button),
                ):
                    if rect and rect.collidepoint(event.pos):
                        self.pressed_button = key
                        play_button_click()
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                key = self.pressed_button
                self.pressed_button = None
                if key == "confirm_continue" and self._confirm_continue_button and self._confirm_continue_button.collidepoint(event.pos):
                    self._do_continue_to_menu()
                elif key == "confirm_restart" and self._confirm_restart_button and self._confirm_restart_button.collidepoint(event.pos):
                    self._do_restart_to_menu()
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for key, rect in (("next", self.next_button), ("menu", self.menu_button)):
                if rect and rect.collidepoint(event.pos):
                    self.pressed_button = key
                    play_button_click()
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            key = self.pressed_button
            self.pressed_button = None
            if key == "next" and self.next_button and self.next_button.collidepoint(event.pos):
                if getattr(self.app.latest_result, "passed", True):
                    self._do_next()
                else:
                    self._do_retry()
            elif key == "menu" and self.menu_button and self.menu_button.collidepoint(event.pos):
                self._do_main_menu()

    # --- rendering helpers ---

    def _draw_outlined_letter(self, screen, x, y) -> None:
        result = self.app.latest_result
        letter = result.rating
        sh = self._font_letter.render(letter, True, _TEXT_DARK)
        screen.blit(sh, (x + 8, y + 8))
        # stroke (pink outline)
        stroke_surf = self._font_letter.render(letter, True, _RATING_STROKE)
        for off in ((4, 0), (-4, 0), (0, 4), (0, -4), (4, 4), (4, -4), (-4, 4), (-4, -4)):
            screen.blit(stroke_surf, (x + off[0], y + off[1]))
        # white fill
        screen.blit(self._font_letter.render(letter, True, _WHITE), (x, y))

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

    def _draw_confirm_overlay(self, screen) -> None:
        width, height = screen.get_size()
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))

        dlg_w = int(width * 0.62)
        dlg_h = int(height * 0.36)
        dlg_x = (width - dlg_w) // 2
        dlg_y = (height - dlg_h) // 2
        dlg_rect = pygame.Rect(dlg_x, dlg_y, dlg_w, dlg_h)
        pygame.draw.rect(screen, _WHITE, dlg_rect, border_radius=20)
        pygame.draw.rect(screen, _BTN_OUTLINE, dlg_rect, width=4, border_radius=20)

        msg = self.app.font_body.render("Where would you like to go?", True, _TEXT_DARK)
        screen.blit(msg, msg.get_rect(center=(width // 2, dlg_y + int(dlg_h * 0.30))))

        btn_w, btn_h = 190, 62
        gap = 20
        total_w = btn_w * 2 + gap
        btn_y = dlg_y + dlg_h - btn_h - 24
        self._confirm_continue_button = pygame.Rect(
            width // 2 - total_w // 2, btn_y, btn_w, btn_h
        )
        self._confirm_restart_button = pygame.Rect(
            width // 2 - total_w // 2 + btn_w + gap, btn_y, btn_w, btn_h
        )
        self._draw_button(screen, self._confirm_continue_button, "Continue", "confirm_continue")
        self._draw_button(screen, self._confirm_restart_button, "Restart", "confirm_restart")

    def render(self) -> None:
        self._load_assets()
        screen = self.app.screen
        width, height = screen.get_size()
        result = self.app.latest_result
        kind = self.app.latest_result_kind

        # --- card frame (identical to all other scenes) ---
        prompt_rect = pygame.Rect(0, 0, width, height)
        pygame.draw.rect(screen, _CARD_BG, prompt_rect, border_radius=0)
        pygame.draw.rect(screen, _WHITE, prompt_rect.inflate(-24, -24), border_radius=56)
        inner_rect = prompt_rect.inflate(-64, -64)
        pygame.draw.rect(screen, _WHITE, inner_rect, border_radius=36)

        ix, iy = inner_rect.x, inner_rect.y   # 32, 32

        # --- Ribbon banner (centered horizontally) ---
        ribbon_w, ribbon_h = 760, 190
        ribbon_x = inner_rect.centerx - ribbon_w // 2
        ribbon_y = iy + 50

        if self._ribbon_img:
            scaled = pygame.transform.smoothscale(self._ribbon_img, (ribbon_w, ribbon_h))
            screen.blit(scaled, (ribbon_x, ribbon_y))
        else:
            pygame.draw.rect(screen, _INNER_BORDER,
                             pygame.Rect(ribbon_x, ribbon_y, ribbon_w, ribbon_h), border_radius=20)

        ribbon_cx = inner_rect.centerx

        # "LEVEL X" — small, dark, centered on ribbon
        if kind == "tier":
            level_text = f"LEVEL {result.tier}"
        else:
            level_text = f"LEVEL {result.level.upper()}"
        lv_surf = self.app.font_body.render(level_text, True, _TEXT_DARK)
        lv_rect = lv_surf.get_rect(centerx=ribbon_cx, top=ribbon_y + 20)
        screen.blit(lv_surf, lv_rect)

        # "COMPLETE!" / "LEVEL UP!" — large, white, shadow, centered on ribbon
        if kind == "tier" and getattr(result, "passed", True):
            complete_text = "LEVEL UP!"
        else:
            complete_text = "COMPLETE!"
        cmp_surf = self._font_complete.render(complete_text, True, _WHITE)
        cmp_shadow = self._font_complete.render(complete_text, True, _TEXT_DARK)
        cmp_rect = cmp_surf.get_rect(centerx=ribbon_cx, top=ribbon_y + 45)
        screen.blit(cmp_shadow, (cmp_rect.x + 2, cmp_rect.y + 3))
        screen.blit(cmp_surf, cmp_rect)

        # --- Large outlined rating letter + "Rating" label (left section) ---
        # Center the group horizontally in the left half and vertically between ribbon and buttons
        btn_h_ref = 70
        btn_y_ref = inner_rect.bottom - btn_h_ref - 48
        ribbon_bottom = ribbon_y + ribbon_h
        content_cy = (ribbon_bottom + btn_y_ref) // 2

        letter_surf = self._font_letter.render(result.rating, True, _WHITE)
        rating_lbl = self._font_stats.render("Rating", True, _TEXT_DARK)
        lbl_gap = 18

        group_w = rating_lbl.get_width() + lbl_gap + letter_surf.get_width()
        left_section_cx = ix + inner_rect.width * 3 // 8   # 3/8 across = right of left-quarter
        group_left = left_section_cx - group_w // 2

        letter_x = group_left + rating_lbl.get_width() + lbl_gap
        letter_y = content_cy - letter_surf.get_height() // 2 - 23
        self._draw_outlined_letter(screen, letter_x, letter_y)

        rating_rect = rating_lbl.get_rect(
            left=group_left,
            centery=content_cy - 23,
        )
        screen.blit(rating_lbl, rating_rect)

        # --- Stats grid (right section, vertically centered around content_cy) ---
        label_x = inner_rect.centerx + 30
        row_spacing = 68
        rows = [
            ("Score:", f"{result.first_try_correct}/{result.items_total}", content_cy - row_spacing - 30),
            ("Fluency:", f"{round(result.fluency * 100)}%", content_cy - 30),
            ("Time:", _fmt_duration(self._elapsed) if self._elapsed is not None else "--", content_cy + row_spacing - 30),
        ]
        for lbl_text, val_text, row_y in rows:
            lbl_surf = self._font_stats.render(lbl_text, True, _TEXT_DARK)
            val_surf = self._font_stats.render(val_text, True, _VALUE_PINK)
            screen.blit(lbl_surf, (label_x, row_y))
            screen.blit(val_surf, (label_x + lbl_surf.get_width() + 14, row_y))

        # --- Buttons (centered, matching Figma positions) ---
        btn_w, btn_h = 297, 70
        total_btn_w = btn_w * 2 + 50
        btn_x0 = inner_rect.centerx - total_btn_w // 2
        btn_y = inner_rect.bottom - btn_h - 48

        self.menu_button = pygame.Rect(btn_x0, btn_y, btn_w, btn_h)
        self.next_button = pygame.Rect(btn_x0 + btn_w + 50, btn_y, btn_w, btn_h)

        if getattr(result, "passed", True):
            next_label = "Next Level" if kind == "tier" else "Continue"
        else:
            next_label = "Retry"
        self._draw_button(screen, self.menu_button, "Main Menu", "menu")
        self._draw_button(screen, self.next_button, next_label, "next")

        # --- Borders drawn last (on top of all content) ---
        pygame.draw.rect(screen, _OUTER_BORDER, prompt_rect, width=12, border_radius=68)
        pygame.draw.rect(screen, _INNER_BORDER, inner_rect, width=12, border_radius=36)

        # --- Render celebratory confetti animation on pass ---
        self.confetti.update_and_render(pygame, screen)

        if self._show_menu_confirm:
            self._draw_confirm_overlay(screen)

