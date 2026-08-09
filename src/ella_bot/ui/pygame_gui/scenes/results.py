from __future__ import annotations

import logging
import time
import pygame

from ella_bot.ui.pygame_gui.scene import BaseScene
from ella_bot.ui.pygame_gui.lottie_bg import load_animated_background
from ella_bot.ui.pygame_gui.components.button import Button
from ella_bot.ui.pygame_gui.components.confetti import ConfettiAnimation
from ella_bot.utils.file_utils import resolve_asset_path
from ella_bot.services.sound_effects import play_level_sound, play_button_click

logger = logging.getLogger(__name__)

_CARD_BG = (0, 0, 0)
_WHITE = (255, 255, 255)
_OUTER_BORDER = (94, 42, 59)
_INNER_BORDER = (255, 185, 207)
_TEXT_DARK = (87, 39, 108)      # #57276C Dark Violet
_RATING_GOLD = (242, 210, 20)    # #F2D214 Gold


def _fmt_duration(seconds: float) -> str:
    s = max(0, int(seconds))
    m, sec = divmod(s, 60)
    if m:
        return f"{m}min {sec} secs"
    return f"{sec} secs"


class ResultsScene(BaseScene):
    def __init__(self, app):
        super().__init__(app)
        self.pressed_button = None
        self._ribbon_img = None
        self._lottie_bg = None
        self._main_menu_svg = None
        self._font_letter = None
        self._font_stats = None
        self._font_complete = None
        self._elapsed = None
        self.next_button = None
        self.menu_button = None
        self.rating_letter_rect = None
        self.metrics_circle_y = None
        self.score_circle_rect = None
        self.fluency_circle_rect = None
        self.ratings_badge_rect = None
        self.time_badge_rect = None
        self._show_menu_confirm = False
        self._confirm_continue_button = None
        self._confirm_restart_button = None
        self.confetti = ConfettiAnimation()

    def on_enter(self) -> None:
        from ella_bot.services.bgm_service import play_menu_bgm

        play_menu_bgm()
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
        if self._lottie_bg is None:
            self._lottie_bg = load_animated_background(
                [
                    "assets/Final_Lightray.lottie",
                    "assets/Lightray.lottie",
                    "assets/shinebg.lottie",
                    "assets/shinebg.json",
                ],
                video_fallback="assets/Comp 1_2.mp4",
            )
            if self._lottie_bg is None:
                self._lottie_bg = False

        if self._main_menu_svg is None:
            try:
                svg2_bg_path = resolve_asset_path("assets/BG/Main Menu (2).svg")
                svg2_path = resolve_asset_path("assets/Main Menu (2).svg")
                p1080_trans = resolve_asset_path("assets/Main Menu 1080p Transparent.png")
                svg1_path = resolve_asset_path("assets/Main Menu (1).svg")
                if svg2_bg_path.exists():
                    self._main_menu_svg = pygame.image.load(str(svg2_bg_path)).convert_alpha()
                elif svg2_path.exists():
                    self._main_menu_svg = pygame.image.load(str(svg2_path)).convert_alpha()
                elif p1080_trans.exists():
                    self._main_menu_svg = pygame.image.load(str(p1080_trans)).convert_alpha()
                elif svg1_path.exists():
                    self._main_menu_svg = pygame.image.load(str(svg1_path)).convert_alpha()
            except Exception:
                self._main_menu_svg = False

        if self._ribbon_img is None:
            try:
                r_png = resolve_asset_path("assets/ribbon_s_2.png")
                r_svg = resolve_asset_path("assets/ribbon s 2.svg")
                if r_png.exists():
                    self._ribbon_img = pygame.image.load(str(r_png)).convert_alpha()
                elif r_svg.exists():
                    self._ribbon_img = pygame.image.load(str(r_svg)).convert_alpha()
            except Exception:
                self._ribbon_img = False

        if self._font_letter is None:
            self._font_letter = self.app._get_sys_font(170)
        if self._font_stats is None:
            self._font_stats = self.app._get_sys_font(32)
        if self._font_complete is None:
            self._font_complete = self.app._get_sys_font(48)

    # --- actions ---

    def _save_reading_transition_or_restore(self) -> bool:
        if self.app.save_active_session("reading"):
            return True
        self.app.continue_saved_session()
        return False

    def _do_next(self) -> None:
        result = self.app.latest_result
        if getattr(self.app, "latest_result_kind", "") == "session":
            if self.app.start_new_session("1a"):
                self.app.switch_scene("reading_prompt")
                self.app.active_scene._start_attempt()
            return
        if result and not getattr(result, "passed", False):
            return
        if hasattr(self.app, "session") and self.app.session:
            self.app.session.advance_to_higher_stage()
        if not self._save_reading_transition_or_restore():
            return
        self.app.switch_scene("reading_prompt")
        self.app.active_scene._start_attempt()

    def _reset_for_retry(self) -> None:
        result = self.app.latest_result
        if not result:
            return
        if getattr(self.app, "latest_result_kind", "") == "tier":
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
        self.app.switch_scene("main_menu")

    def handle_event(self, event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for key, rect in (("next", self.next_button), ("menu", self.menu_button)):
                if rect and rect.collidepoint(event.pos):
                    self.pressed_button = key
                    play_button_click()
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            key = self.pressed_button
            self.pressed_button = None
            if key == "next" and self.next_button and self.next_button.collidepoint(event.pos):
                result = getattr(self.app, "latest_result", None)
                passed = getattr(result, "passed", True) if result else True
                if passed:
                    self._do_next()
                else:
                    self._do_retry()
            elif key == "menu" and self.menu_button and self.menu_button.collidepoint(event.pos):
                self._do_main_menu()

    def render(self) -> None:
        self._load_assets()
        screen = self.app.screen
        width, height = screen.get_size()
        now_ms = pygame.time.get_ticks()

        result = getattr(self.app, "latest_result", None)
        kind = getattr(self.app, "latest_result_kind", "sublevel")

        # 1. Render Lottie Background (same as Main Menu)
        if self._lottie_bg:
            vf = self._lottie_bg.get_frame(now_ms, (width, height))
            if vf:
                screen.blit(vf, (0, 0))
            else:
                screen.fill(_CARD_BG)
        else:
            screen.fill(_CARD_BG)

        cx = width // 2

        # --- LEVEL TITLE ("LEVEL 4" / "LEVEL 1A") ---
        if kind == "session":
            level_str = "LEVEL 4"
        elif result:
            level_str = f"LEVEL {result.tier}" if kind == "tier" else f"LEVEL {result.level.upper()}"
        else:
            level_str = "LEVEL 4"

        lv_font = getattr(self.app, "font_button", self.app.font_title)
        lv_surf = lv_font.render(level_str, True, (87, 39, 108))
        lv_rect = lv_surf.get_rect(centerx=cx, top=45)
        screen.blit(lv_surf, lv_rect)

        # --- YELLOW RIBBON ("Complete") ---
        ribbon_w, ribbon_h = 460, 128
        ribbon_x = cx - ribbon_w // 2
        ribbon_y = lv_rect.bottom + 4

        if self._ribbon_img:
            scaled_ribbon = pygame.transform.smoothscale(self._ribbon_img, (ribbon_w, ribbon_h))
            screen.blit(scaled_ribbon, (ribbon_x, ribbon_y))

        # --- RATING LETTER ("A") ---
        rating_str = (
            result.overall_rating
            if result and kind == "session"
            else result.rating if result else "A"
        )
        letter_surf = self._font_letter.render(rating_str, True, (242, 210, 20))
        letter_shadow = self._font_letter.render(rating_str, True, (175, 141, 55))

        metrics_cy = ribbon_y + ribbon_h + 69
        letter_rect = letter_surf.get_rect(centerx=cx, centery=metrics_cy)
        self.rating_letter_rect = letter_rect.copy()
        for off_x, off_y in ((-3, 0), (3, 0), (0, -3), (0, 3), (3, 3)):
            screen.blit(letter_shadow, letter_rect.move(off_x, off_y))
        screen.blit(letter_surf, letter_rect)

        # --- "RATINGS" PILL BADGE (#7F3F97 without outline) ---
        badge_w, badge_h = 220, 48
        badge_rect = pygame.Rect(
            cx - badge_w // 2,
            ribbon_y + ribbon_h + 29 + letter_rect.height // 2,
            badge_w,
            badge_h,
        )
        self.ratings_badge_rect = badge_rect.copy()
        pygame.draw.rect(screen, (127, 63, 151), badge_rect, border_radius=24)

        rat_surf = self.app.font_body.render("RATINGS", True, (242, 210, 20))
        screen.blit(rat_surf, rat_surf.get_rect(center=badge_rect.center))

        # --- SCORE & FLUENCY CIRCLES (#7F3F97 fill without outlines) ---
        circ_size = 128
        circ_cy = metrics_cy + 16
        self.metrics_circle_y = circ_cy
        font_circ_val = self.app._get_sys_font(32)
        font_circ_label = self.app._get_sys_font(24)

        # LEFT CIRCLE: SCORE ("10/10 SCORE" or "5/5 SCORE")
        score_cx = cx - 210
        self.score_circle_rect = pygame.Rect(0, 0, circ_size, circ_size)
        self.score_circle_rect.center = (score_cx, circ_cy)
        pygame.draw.circle(screen, (127, 63, 151), (score_cx, circ_cy), circ_size // 2)

        score_val = f"{result.first_try_correct}/{result.items_total}" if result else "10/10"
        s1 = font_circ_val.render(score_val, True, (255, 250, 243))
        s2 = font_circ_label.render("SCORE", True, (242, 210, 20))
        screen.blit(s1, s1.get_rect(center=(score_cx, circ_cy - 14)))
        screen.blit(s2, s2.get_rect(center=(score_cx, circ_cy + 21)))

        # RIGHT CIRCLE: FLUENCY ("100% FLUENCY" or "90% FLUENCY")
        fluency_cx = cx + 210
        self.fluency_circle_rect = pygame.Rect(0, 0, circ_size, circ_size)
        self.fluency_circle_rect.center = (fluency_cx, circ_cy)
        pygame.draw.circle(screen, (127, 63, 151), (fluency_cx, circ_cy), circ_size // 2)

        fluency = (
            result.overall_fluency
            if result and kind == "session"
            else result.fluency if result else 1.0
        )
        fl_val = f"{round(fluency * 100)}%"
        f1 = font_circ_val.render(fl_val, True, (255, 250, 243))
        f2 = font_circ_label.render("FLUENCY", True, (242, 210, 20))
        screen.blit(f1, f1.get_rect(center=(fluency_cx, circ_cy - 14)))
        screen.blit(f2, f2.get_rect(center=(fluency_cx, circ_cy + 21)))

        # --- TIME ROW ("TIME 1min 20 secs") (#7F3F97 badge without outline) ---
        time_y = badge_rect.bottom + 6
        time_badge_w, time_badge_h = 120, 34
        time_badge = pygame.Rect(cx - 150, time_y, time_badge_w, time_badge_h)
        self.time_badge_rect = time_badge.copy()
        pygame.draw.rect(screen, (127, 63, 151), time_badge, border_radius=17)

        t_lbl = self.app.font_small.render("TIME", True, (242, 210, 20))
        screen.blit(t_lbl, t_lbl.get_rect(center=time_badge.center))

        t_val_str = _fmt_duration(self._elapsed) if self._elapsed is not None else "1min 20 secs"
        t_val = self.app.font_body.render(t_val_str, True, (87, 39, 108))
        screen.blit(t_val, (time_badge.right + 16, time_y + (time_badge_h - t_val.get_height()) // 2))

        # --- BOTTOM BUTTONS: MAIN MENU (Violet) & CONTINUE/RETRY (Yellow) ---
        btn_w, btn_h = 285, 64
        btn_gap = 30
        btn_y = height - btn_h - 45

        self.menu_button = pygame.Rect(cx - btn_w - btn_gap // 2, btn_y, btn_w, btn_h)
        self.next_button = pygame.Rect(cx + btn_gap // 2, btn_y, btn_w, btn_h)

        menu_btn = Button(self.menu_button, label="Main Menu", variant="violet", font=self.app.font_button, stroke_weight=8)
        menu_btn.is_pressed = (self.pressed_button == "menu")
        menu_btn.draw(screen)

        passed = getattr(result, "passed", True) if result else True
        if kind == "session":
            next_label = "Play Again"
        else:
            next_label = "Continue" if passed else "Retry"

        cont_btn = Button(self.next_button, label=next_label, variant="yellow", font=self.app.font_button, stroke_weight=8)
        cont_btn.is_pressed = (self.pressed_button == "next")
        cont_btn.draw(screen)

        # Celebratory confetti animation on pass
        self.confetti.update_and_render(pygame, screen)
