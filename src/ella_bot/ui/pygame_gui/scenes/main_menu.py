from __future__ import annotations

import io
from datetime import datetime

import pygame

from ella_bot.ui.pygame_gui.scene import BaseScene
from ella_bot.ui.pygame_gui.bot_sprite import BotSprite
from ella_bot.ui.pygame_gui.video_bg import VideoBackground
from ella_bot.ui.pygame_gui.lottie_bg import LottieBackground
from ella_bot.ui.pygame_gui.components.button import Button
from ella_bot.utils.file_utils import resolve_asset_path
from ella_bot.services.sound_effects import play_button_click

_CARD_BG = (0, 0, 0)
_WHITE = (255, 255, 255)
_OUTER_BORDER = (94, 42, 59)
_INNER_BORDER = (255, 185, 207)
_BTN_FILL = (255, 182, 193)
_BTN_OUTLINE = (94, 42, 59)
_BTN_PRESSED = (251, 165, 193)
_TEXT = (50, 50, 50)


class MainMenuScene(BaseScene):
    def __init__(self, app):
        super().__init__(app)
        self.pressed_button = None
        self.show_exit_confirm = False
        self.show_resume_prompt = False
        self.show_profile_required_prompt = False
        self.profile_required_message = ''
        self.resume_summary = None

        self.menu_start_button = None
        self.menu_profiles_button = None
        self.menu_exit_button = None
        self.menu_gear_button = None
        self.menu_confirm_yes_button = None
        self.menu_confirm_no_button = None
        self.resume_continue_button = None
        self.resume_new_button = None
        self.resume_cancel_button = None
        self.profile_required_open_button = None
        self.profile_required_cancel_button = None

        self.bot = BotSprite()
        self._title_img = None
        self._settings_icon = None
        self._video_bg = None
        self._main_menu_svg = None

    def on_enter(self) -> None:
        from ella_bot.services.bgm_service import play_menu_bgm

        play_menu_bgm()
        self.show_exit_confirm = False
        self.show_resume_prompt = False
        self.show_profile_required_prompt = False
        self.profile_required_message = ''
        self.resume_summary = None
        self.pressed_button = None
        self.menu_profiles_button = None
        self.profile_required_open_button = None
        self.profile_required_cancel_button = None

    def _do_profiles(self) -> None:
        self.app.switch_scene('profiles')

    def _do_start(self) -> None:
        if self.app.active_profile() is None:
            self.profile_required_message = (
                'Create a profile before starting.'
                if not self.app.profiles()
                else 'Choose a profile before starting.'
            )
            self.show_profile_required_prompt = True
            return
        summary = self.app.saved_session_summary()
        if summary is None:
            self.app.switch_scene("level_selection")
            return
        self.resume_summary = summary
        self.show_resume_prompt = True

    def _do_continue(self) -> None:
        phase = self.app.continue_saved_session()
        if phase == "reading":
            self.show_resume_prompt = False
            self.app.switch_scene("reading_prompt")
            self.app.active_scene._start_attempt()
        elif phase == "results":
            self.show_resume_prompt = False
            self.app.switch_scene("results")

    def _do_new_session(self) -> None:
        self.show_resume_prompt = False
        self.app.switch_scene("level_selection")

    def _load_assets(self) -> None:
        if self._video_bg is None:
            try:
                final_lightray_path = resolve_asset_path("assets/Final_Lightray.lottie")
                lightray_path = resolve_asset_path("assets/Lightray.lottie")
                lottie_path = resolve_asset_path("assets/shinebg.lottie")
                if final_lightray_path.exists():
                    self._video_bg = LottieBackground(final_lightray_path)
                elif lightray_path.exists():
                    self._video_bg = LottieBackground(lightray_path)
                elif lottie_path.exists():
                    self._video_bg = LottieBackground(lottie_path)
                else:
                    v_path = resolve_asset_path("assets/Comp 1_2.mp4")
                    self._video_bg = VideoBackground(v_path)
            except Exception:
                self._video_bg = False

        if self._main_menu_svg is None:
            try:
                svg2_bg_path = resolve_asset_path("assets/BG/Main Menu (2).svg")
                svg2_path = resolve_asset_path("assets/Main Menu (2).svg")
                svg1_path = resolve_asset_path("assets/Main Menu (1).svg")
                svg_path = resolve_asset_path("assets/Main Menu.svg")
                p1080_trans = resolve_asset_path("assets/Main Menu 1080p Transparent.png")
                png_path = resolve_asset_path("assets/Main Menu.png")

                if svg2_bg_path.exists():
                    self._main_menu_svg = pygame.image.load(str(svg2_bg_path)).convert_alpha()
                elif svg2_path.exists():
                    self._main_menu_svg = pygame.image.load(str(svg2_path)).convert_alpha()
                elif p1080_trans.exists():
                    self._main_menu_svg = pygame.image.load(str(p1080_trans)).convert_alpha()
                elif svg1_path.exists():
                    self._main_menu_svg = pygame.image.load(str(svg1_path)).convert_alpha()
                elif png_path.exists():
                    self._main_menu_svg = pygame.image.load(str(png_path)).convert_alpha()
                elif svg_path.exists():
                    surf = pygame.image.load(str(svg_path)).convert_alpha()
                    if (pygame.surfarray.pixels_alpha(surf) > 0).sum() > 0:
                        self._main_menu_svg = surf
                    else:
                        import re, base64
                        svg_text = svg_path.read_text(encoding="utf-8")
                        match = re.search(r'data:image/png;base64,([A-Za-z0-9+/=]+)', svg_text)
                        if match:
                            png_bytes = base64.b64decode(match.group(1))
                            self._main_menu_svg = pygame.image.load(io.BytesIO(png_bytes)).convert_alpha()
            except Exception:
                self._main_menu_svg = False

        if self._title_img is None:
            try:
                raw = pygame.image.load(
                    str(resolve_asset_path("assets/menu-title.png"))
                ).convert_alpha()
                white = pygame.Surface(raw.get_size())
                white.fill((255, 255, 255))
                white.blit(raw, (0, 0))
                self._title_img = white
            except Exception:
                self._title_img = False

        if self._settings_icon is None:
            try:
                svg_text = resolve_asset_path("assets/ic_settings.svg").read_text(encoding="utf-8")
                svg_tinted = (
                    svg_text.replace('fill="#FFFFFF"', 'fill="#FFFAF3"')
                    .replace('height="24px"', 'height="48px"')
                    .replace('width="24px"', 'width="48px"')
                )
                self._settings_icon = pygame.image.load(io.BytesIO(svg_tinted.encode("utf-8"))).convert_alpha()
            except Exception:
                self._settings_icon = False

    def update(self, now_ms: int) -> None:
        self.bot.update(now_ms, "idle")

    def handle_event(self, event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_mouse_down(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._handle_mouse_up(event.pos)

    def _handle_mouse_down(self, mouse_pos) -> None:
        if self.show_profile_required_prompt:
            if (
                self.profile_required_open_button
                and self.profile_required_open_button.collidepoint(mouse_pos)
            ):
                self.pressed_button = 'profile_required_open'
            elif (
                self.profile_required_cancel_button
                and self.profile_required_cancel_button.collidepoint(mouse_pos)
            ):
                self.pressed_button = 'profile_required_cancel'
            if self.pressed_button:
                play_button_click()
            return

        if self.show_resume_prompt:
            if self.resume_continue_button and self.resume_continue_button.collidepoint(mouse_pos):
                self.pressed_button = "resume_continue"
            elif self.resume_new_button and self.resume_new_button.collidepoint(mouse_pos):
                self.pressed_button = "resume_new"
            elif self.resume_cancel_button and self.resume_cancel_button.collidepoint(mouse_pos):
                self.pressed_button = "resume_cancel"
            if self.pressed_button:
                play_button_click()
            return

        if self.show_exit_confirm:
            if self.menu_confirm_yes_button and self.menu_confirm_yes_button.collidepoint(mouse_pos):
                self.pressed_button = "confirm_yes"
            elif self.menu_confirm_no_button and self.menu_confirm_no_button.collidepoint(mouse_pos):
                self.pressed_button = "confirm_no"
            if self.pressed_button:
                play_button_click()
            return

        if self.menu_profiles_button and self.menu_profiles_button.collidepoint(mouse_pos):
            self.pressed_button = 'profiles'
        elif self.menu_start_button and self.menu_start_button.collidepoint(mouse_pos):
            self.pressed_button = "start"
        elif self.menu_exit_button and self.menu_exit_button.collidepoint(mouse_pos):
            self.pressed_button = "exit"
        elif self.menu_gear_button and self.menu_gear_button.collidepoint(mouse_pos):
            self.pressed_button = "gear"

        if self.pressed_button:
            play_button_click()

    def _handle_mouse_up(self, mouse_pos) -> None:
        try:
            if (
                self.pressed_button == 'profile_required_open'
                and self.profile_required_open_button
                and self.profile_required_open_button.collidepoint(mouse_pos)
            ):
                self.show_profile_required_prompt = False
                self._do_profiles()
                return
            if (
                self.pressed_button == 'profile_required_cancel'
                and self.profile_required_cancel_button
                and self.profile_required_cancel_button.collidepoint(mouse_pos)
            ):
                self.show_profile_required_prompt = False
                return
            if (
                self.pressed_button == 'profiles'
                and self.menu_profiles_button
                and self.menu_profiles_button.collidepoint(mouse_pos)
            ):
                self._do_profiles()
                return
            if self.pressed_button == "resume_continue" and self.resume_continue_button and self.resume_continue_button.collidepoint(mouse_pos):
                self._do_continue()
            elif self.pressed_button == "resume_new" and self.resume_new_button and self.resume_new_button.collidepoint(mouse_pos):
                self._do_new_session()
            elif self.pressed_button == "resume_cancel" and self.resume_cancel_button and self.resume_cancel_button.collidepoint(mouse_pos):
                self.show_resume_prompt = False
            elif self.pressed_button == "start" and self.menu_start_button and self.menu_start_button.collidepoint(mouse_pos):
                self._do_start()
            elif self.pressed_button == "exit" and self.menu_exit_button and self.menu_exit_button.collidepoint(mouse_pos):
                self.show_exit_confirm = True
            elif self.pressed_button == "gear" and self.menu_gear_button and self.menu_gear_button.collidepoint(mouse_pos):
                self.app.switch_scene("settings")
            elif self.pressed_button == "confirm_yes" and self.menu_confirm_yes_button and self.menu_confirm_yes_button.collidepoint(mouse_pos):
                self.app.running = False
            elif self.pressed_button == "confirm_no" and self.menu_confirm_no_button and self.menu_confirm_no_button.collidepoint(mouse_pos):
                self.show_exit_confirm = False
        finally:
            self.pressed_button = None

    def _draw_button(self, screen, rect, label, key, radius=20) -> None:
        is_pressed = self.pressed_button == key
        bg = _BTN_PRESSED if is_pressed else _BTN_FILL
        if not is_pressed:
            pygame.draw.rect(screen, _BTN_OUTLINE,
                             pygame.Rect(rect.left + 4, rect.top + 4, rect.width, rect.height),
                             border_radius=radius)
        pygame.draw.rect(screen, bg, rect, border_radius=radius)
        pygame.draw.rect(screen, _BTN_OUTLINE, rect, width=2, border_radius=radius)
        surf = self.app.font_body.render(label, True, _WHITE)
        screen.blit(surf, surf.get_rect(center=rect.center))

    def _draw_welcome_speech_bubble(
        self,
        screen: pygame.Surface,
        inner_rect: pygame.Rect,
    ) -> None:
        profile = self.app.active_profile()
        name_str = profile.name if profile else "Unique User"
        text_str = f"Hello, {name_str} !"

        font = self.app.font_body
        text_surf = font.render(text_str, True, (255, 250, 243))

        # Max allowed width before shrinking font
        max_bubble_w = int(inner_rect.width * 0.38)
        if text_surf.get_width() + 48 > max_bubble_w and hasattr(self.app, "font_small"):
            font = self.app.font_small
            text_surf = font.render(text_str, True, (255, 250, 243))

            if text_surf.get_width() + 48 > max_bubble_w:
                truncated_name = name_str[:14] + "..."
                text_str = f"Hello, {truncated_name} !"
                text_surf = font.render(text_str, True, (255, 250, 243))

        # Dynamic bubble width (min 287, auto-expands for long text)
        bubble_w = max(287, text_surf.get_width() + 48)
        bubble_h = 70

        # Anchor right side relative to robot head
        bubble_right = inner_rect.right - 45
        bubble_x = bubble_right - bubble_w
        bubble_y = inner_rect.top + int(inner_rect.height * 0.31)

        bubble_rect = pygame.Rect(bubble_x, bubble_y, bubble_w, bubble_h)

        # Drop shadow
        shadow_rect = pygame.Rect(bubble_rect.left + 4, bubble_rect.top + 4, bubble_w, bubble_h)
        pygame.draw.rect(screen, (25, 5, 35), shadow_rect, border_radius=35)

        # Main pill body (#7F3F97)
        pygame.draw.rect(screen, (127, 63, 151), bubble_rect, border_radius=35)
        # Outline stroke (#3B0C4C)
        pygame.draw.rect(screen, (59, 12, 76), bubble_rect, width=3, border_radius=35)

        # Speech bubble tail pointing DOWNWARDS directly into the top of ELLA's head
        p1 = (bubble_rect.right - 65, bubble_rect.bottom - 2)
        p2 = (bubble_rect.right - 35, bubble_rect.bottom - 2)
        p3 = (bubble_rect.right - 45, bubble_rect.bottom + 38)

        pygame.draw.polygon(screen, (127, 63, 151), [p1, p2, p3])
        pygame.draw.line(screen, (59, 12, 76), p1, p3, 3)
        pygame.draw.line(screen, (59, 12, 76), p2, p3, 3)
        pygame.draw.line(screen, (127, 63, 151), p1, p2, 5)

        # Text render
        text_rect = text_surf.get_rect(center=bubble_rect.center)
        screen.blit(text_surf, text_rect)

    def render(self) -> None:
        screen = self.app.screen
        width, height = screen.get_size()
        self._load_assets()

        now_ms = pygame.time.get_ticks()
        prompt_rect = pygame.Rect(0, 0, width, height)
        inner_rect = prompt_rect.inflate(-64, -64)

        # 1. Render Video / Lottie Background
        if self._video_bg:
            vf = self._video_bg.get_frame(now_ms, (width, height))
            if vf:
                screen.blit(vf, (0, 0))
            else:
                screen.fill(_CARD_BG)
        else:
            screen.fill(_CARD_BG)

        # 2. Render Main Menu SVG/PNG Overlay
        if self._main_menu_svg:
            if self._main_menu_svg.get_size() != (width, height):
                overlay = pygame.transform.smoothscale(self._main_menu_svg, (width, height))
            else:
                overlay = self._main_menu_svg
            screen.blit(overlay, (0, 0))

        # 3. Render Bot Sprite (idle SVG robot in bottom right corner)
        self.bot.draw(screen, prompt_rect)

        content_top = inner_rect.top + int(inner_rect.height * 0.28)

        button_area_bottom = inner_rect.bottom - 36
        available_height = max(3, button_area_bottom - content_top)
        btn_w = 325
        btn_h = 64
        btn_gap = 12
        total_height = 3 * btn_h + 2 * btn_gap
        # Shift main buttons down by 28px
        btn_y = content_top + (available_height - total_height) // 2 + 28
        btn_x = inner_rect.centerx - btn_w // 2

        self.menu_start_button = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
        self.menu_profiles_button = pygame.Rect(
            btn_x,
            btn_y + btn_h + btn_gap,
            btn_w,
            btn_h,
        )
        self.menu_exit_button = pygame.Rect(
            btn_x,
            btn_y + 2 * (btn_h + btn_gap),
            btn_w,
            btn_h,
        )

        start_btn = Button(self.menu_start_button, label='Start', variant='yellow', font=self.app.font_button, stroke_weight=8)
        start_btn.is_pressed = (self.pressed_button == 'start')
        start_btn.draw(screen)

        profile_btn = Button(self.menu_profiles_button, label='Profile', variant='yellow', font=self.app.font_button, stroke_weight=8)
        profile_btn.is_pressed = (self.pressed_button == 'profiles')
        profile_btn.draw(screen)

        exit_btn = Button(self.menu_exit_button, label='Exit', variant='violet', font=self.app.font_button, stroke_weight=8)
        exit_btn.is_pressed = (self.pressed_button == 'exit')
        exit_btn.draw(screen)

        # --- Welcome Speech Bubble (positioned right next to pink robot head) ---
        self._draw_welcome_speech_bubble(screen, inner_rect)

        # --- Gear/Settings button (moved further left next to outer border) ---
        gear_size = 90
        gear_x = inner_rect.left + 40
        gear_y = inner_rect.centery - 45
        self.menu_gear_button = pygame.Rect(
            gear_x,
            gear_y,
            gear_size,
            gear_size,
        )

        gear_btn = Button(
            self.menu_gear_button,
            icon=self._settings_icon if self._settings_icon else None,
            variant="violet",
            stroke_weight=8,
            corner_radius=50,
        )
        gear_btn.is_pressed = (self.pressed_button == "gear")
        gear_btn.draw(screen)

        if self.show_profile_required_prompt:
            self._draw_profile_required_prompt(screen, width, height)
        elif self.show_exit_confirm:
            self._draw_exit_confirm(screen, width, height)
        elif self.show_resume_prompt:
            self._draw_resume_prompt(screen, width, height)

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

    def _draw_profile_required_prompt(self, screen, width, height) -> None:
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        dlg_w = min(660, max(360, int(width * 0.62)))
        dlg_h = min(300, max(210, int(height * 0.46)))
        dlg_rect = pygame.Rect(
            (width - dlg_w) // 2,
            (height - dlg_h) // 2,
            dlg_w,
            dlg_h,
        )
        pygame.draw.rect(screen, (25, 5, 35), dlg_rect.move(4, 4), border_radius=30)
        pygame.draw.rect(screen, (87, 39, 108), dlg_rect, border_radius=30)
        pygame.draw.rect(screen, (127, 63, 151), dlg_rect, width=6, border_radius=30)

        title_size = max(22, min(38, int(dlg_h * 0.14)))
        title = self._render_adaptive_text("Profile Required", title_size, (255, 250, 243), max_w=dlg_w - 40, bold=True)
        if title:
            screen.blit(
                title,
                title.get_rect(centerx=dlg_rect.centerx, top=dlg_rect.top + int(dlg_h * 0.10)),
            )

        message = self.app.font_body.render(
            self.profile_required_message,
            True,
            (227, 198, 236),
        )
        if isinstance(message, pygame.Surface):
            if message.get_width() > dlg_w - 40:
                scale = (dlg_w - 40) / message.get_width()
                message = pygame.transform.smoothscale(message, (dlg_w - 40, max(1, int(message.get_height() * scale))))
            screen.blit(
                message,
                message.get_rect(centerx=dlg_rect.centerx, top=dlg_rect.top + int(dlg_h * 0.35)),
            )

        btn_w = min(190, (dlg_w - 60) // 2)
        btn_h = min(58, max(42, int(dlg_h * 0.22)))
        btn_gap = 20
        total_w = 2 * btn_w + btn_gap
        btn_x = dlg_rect.centerx - total_w // 2
        btn_y = dlg_rect.bottom - btn_h - int(dlg_h * 0.10)
        self.profile_required_open_button = pygame.Rect(
            btn_x,
            btn_y,
            btn_w,
            btn_h,
        )
        self.profile_required_cancel_button = pygame.Rect(
            btn_x + btn_w + btn_gap,
            btn_y,
            btn_w,
            btn_h,
        )

        button_font_size = max(18, min(28, int(btn_h * 0.50)))
        button_font = self._get_adaptive_font(button_font_size, bold=True)

        btn_open = Button(
            self.profile_required_open_button,
            label="Profiles",
            variant="yellow",
            font=button_font,
            stroke_weight=5,
        )
        btn_open.is_pressed = (self.pressed_button == "profile_required_open")
        btn_open.draw(screen)

        btn_cancel = Button(
            self.profile_required_cancel_button,
            label="Cancel",
            variant="yellow",
            font=button_font,
            stroke_weight=5,
        )
        btn_cancel.is_pressed = (self.pressed_button == "profile_required_cancel")
        btn_cancel.draw(screen)

    def _draw_resume_prompt(self, screen, width, height) -> None:
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        dlg_w = min(740, max(400, int(width * 0.70)))
        dlg_h = min(360, max(250, int(height * 0.56)))
        dlg_rect = pygame.Rect(
            (width - dlg_w) // 2,
            (height - dlg_h) // 2,
            dlg_w,
            dlg_h,
        )
        pygame.draw.rect(screen, (25, 5, 35), dlg_rect.move(4, 4), border_radius=30)
        pygame.draw.rect(screen, (87, 39, 108), dlg_rect, border_radius=30)
        pygame.draw.rect(screen, (127, 63, 151), dlg_rect, width=6, border_radius=30)

        title_size = max(24, min(42, int(dlg_h * 0.13)))
        title = self._render_adaptive_text("Saved Session", title_size, (255, 250, 243), max_w=dlg_w - 40, bold=True)
        if title:
            screen.blit(title, title.get_rect(centerx=dlg_rect.centerx, top=dlg_rect.top + int(dlg_h * 0.08)))

        summary = self.resume_summary
        if summary is not None:
            profile = self.app.active_profile()
            user_name = profile.name if profile else "User"

            name_size = max(22, min(36, int(dlg_h * 0.12)))
            name_surf = self._render_adaptive_text(f"User: {user_name}", name_size, (255, 250, 243), max_w=dlg_w - 40, bold=True)
            if name_surf:
                screen.blit(
                    name_surf,
                    name_surf.get_rect(centerx=dlg_rect.centerx, top=dlg_rect.top + int(dlg_h * 0.23)),
                )

            details_size = max(18, min(30, int(dlg_h * 0.10)))
            details = f"Level {summary.level.upper()}  •  Item {summary.item_number}"
            detail_surf = self._render_adaptive_text(details, details_size, (242, 210, 20), max_w=dlg_w - 40, bold=True)
            if detail_surf:
                screen.blit(
                    detail_surf,
                    detail_surf.get_rect(centerx=dlg_rect.centerx, top=dlg_rect.top + int(dlg_h * 0.38)),
                )

            try:
                saved = datetime.fromisoformat(summary.saved_at).astimezone()
                saved_text = saved.strftime("Saved %b %d, %Y at %I:%M %p")
            except (TypeError, ValueError):
                saved_text = f"Saved {summary.saved_at}"
            small_size = max(15, min(24, int(dlg_h * 0.08)))
            saved_surf = self.app.font_small.render(saved_text, True, (227, 198, 236))
            if isinstance(saved_surf, pygame.Surface):
                if saved_surf.get_width() > dlg_w - 40:
                    scale = (dlg_w - 40) / saved_surf.get_width()
                    saved_surf = pygame.transform.smoothscale(saved_surf, (dlg_w - 40, max(1, int(saved_surf.get_height() * scale))))
                screen.blit(
                    saved_surf,
                    saved_surf.get_rect(centerx=dlg_rect.centerx, top=dlg_rect.top + int(dlg_h * 0.52)),
                )

        btn_gap = 14
        btn_w = min(200, (dlg_w - 40 - 2 * btn_gap) // 3)
        btn_h = min(58, max(42, int(dlg_h * 0.20)))
        total_w = 3 * btn_w + 2 * btn_gap
        btn_x = dlg_rect.centerx - total_w // 2
        btn_y = dlg_rect.bottom - btn_h - int(dlg_h * 0.09)
        self.resume_cancel_button = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
        self.resume_new_button = pygame.Rect(
            btn_x + btn_w + btn_gap,
            btn_y,
            btn_w,
            btn_h,
        )
        self.resume_continue_button = pygame.Rect(
            btn_x + 2 * (btn_w + btn_gap),
            btn_y,
            btn_w,
            btn_h,
        )

        button_font_size = max(16, min(26, int(btn_h * 0.48)))
        button_font = self._get_adaptive_font(button_font_size, bold=True)

        btn_cont = Button(
            self.resume_continue_button,
            label="Continue",
            variant="yellow",
            font=button_font,
            stroke_weight=5,
        )
        btn_cont.is_pressed = (self.pressed_button == "resume_continue")
        btn_cont.draw(screen)

        btn_new = Button(
            self.resume_new_button,
            label="New Session",
            variant="yellow",
            font=button_font,
            stroke_weight=5,
        )
        btn_new.is_pressed = (self.pressed_button == "resume_new")
        btn_new.draw(screen)

        btn_cancel = Button(
            self.resume_cancel_button,
            label="Cancel",
            variant="violet",
            font=button_font,
            stroke_weight=5,
        )
        btn_cancel.is_pressed = (self.pressed_button == "resume_cancel")
        btn_cancel.draw(screen)

    def _draw_exit_confirm(self, screen, width, height) -> None:
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        dlg_w = min(640, max(340, int(width * 0.60)))
        dlg_h = min(280, max(200, int(height * 0.42)))
        dlg_x = (width - dlg_w) // 2
        dlg_y = (height - dlg_h) // 2
        dlg_rect = pygame.Rect(dlg_x, dlg_y, dlg_w, dlg_h)

        pygame.draw.rect(screen, (25, 5, 35), dlg_rect.move(4, 4), border_radius=30)
        pygame.draw.rect(screen, (87, 39, 108), dlg_rect, border_radius=30)
        pygame.draw.rect(screen, (127, 63, 151), dlg_rect, width=6, border_radius=30)

        title_size = max(22, min(38, int(dlg_h * 0.15)))
        msg = self._render_adaptive_text("Are you sure you want to exit?", title_size, (255, 250, 243), max_w=dlg_w - 40, bold=True)
        if msg:
            screen.blit(msg, msg.get_rect(centerx=dlg_rect.centerx, top=dlg_rect.top + int(dlg_h * 0.18)))

        btn_w = min(170, (dlg_w - 60) // 2)
        btn_h = min(58, max(42, int(dlg_h * 0.24)))
        gap = 20
        btn_y = dlg_rect.bottom - btn_h - int(dlg_h * 0.10)
        yes_rect = pygame.Rect(dlg_rect.centerx - btn_w - gap // 2, btn_y, btn_w, btn_h)
        no_rect = pygame.Rect(dlg_rect.centerx + gap // 2, btn_y, btn_w, btn_h)
        self.menu_confirm_yes_button = yes_rect
        self.menu_confirm_no_button = no_rect

        button_font_size = max(18, min(28, int(btn_h * 0.50)))
        button_font = self._get_adaptive_font(button_font_size, bold=True)

        btn_yes = Button(
            yes_rect,
            label="Yes",
            variant="violet",
            font=button_font,
            stroke_weight=5,
        )
        btn_yes.is_pressed = (self.pressed_button == "confirm_yes")
        btn_yes.draw(screen)

        btn_no = Button(
            no_rect,
            label="No",
            variant="yellow",
            font=button_font,
            stroke_weight=5,
        )
        btn_no.is_pressed = (self.pressed_button == "confirm_no")
        btn_no.draw(screen)
