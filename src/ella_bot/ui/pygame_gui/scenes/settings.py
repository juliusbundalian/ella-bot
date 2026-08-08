from __future__ import annotations

import logging
import pygame

from ella_bot.ui.pygame_gui.scene import BaseScene
from ella_bot.ui.pygame_gui.lottie_bg import load_animated_background
from ella_bot.ui.pygame_gui.components.button import Button
from ella_bot.config.app_config import save_setting
from ella_bot.utils.file_utils import resolve_asset_path
from ella_bot.services.sound_effects import play_button_click

logger = logging.getLogger(__name__)

_VOLUME_MIN = 1
_VOLUME_MAX = 6
_LISTEN_MIN = 5
_LISTEN_MAX = 12


class SettingsScene(BaseScene):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.volume_level: int = _VOLUME_MAX
        self.listen_seconds: int = 5
        self.pressed_button: str | None = None

        self._lottie_bg = None
        self.btn_vol_minus: pygame.Rect | None = None
        self.btn_vol_plus: pygame.Rect | None = None
        self.btn_listen_minus: pygame.Rect | None = None
        self.btn_listen_plus: pygame.Rect | None = None
        self.btn_close: pygame.Rect | None = None
        self.btn_back: pygame.Rect | None = None

    def on_enter(self) -> None:
        self.pressed_button = None
        try:
            from ella_bot.config.app_config import load_settings
            settings = load_settings()
        except Exception:
            settings = {}
        volume_fraction = settings.get("volume", 1.0)
        self.volume_level = max(_VOLUME_MIN, min(_VOLUME_MAX, round(volume_fraction * _VOLUME_MAX)))
        if getattr(self.app, "asr", None) is not None:
            self.listen_seconds = self.app.asr.listen_seconds
        else:
            self.listen_seconds = int(settings.get("listen_seconds", 5))

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

    def handle_event(self, event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._on_mouse_down(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._on_mouse_up(event.pos)

    def _on_mouse_down(self, pos) -> None:
        for name, rect in [
            ("vol_minus", self.btn_vol_minus),
            ("vol_plus", self.btn_vol_plus),
            ("listen_minus", self.btn_listen_minus),
            ("listen_plus", self.btn_listen_plus),
            ("close", self.btn_close),
            ("back", self.btn_back),
        ]:
            if rect and rect.collidepoint(pos):
                self.pressed_button = name
                play_button_click()
                break

    def _on_mouse_up(self, pos) -> None:
        try:
            btn = self.pressed_button
            if btn == "vol_minus" and self.btn_vol_minus and self.btn_vol_minus.collidepoint(pos):
                self._tap_volume(-1)
            elif btn == "vol_plus" and self.btn_vol_plus and self.btn_vol_plus.collidepoint(pos):
                self._tap_volume(1)
            elif btn == "listen_minus" and self.btn_listen_minus and self.btn_listen_minus.collidepoint(pos):
                self._tap_listen(-1)
            elif btn == "listen_plus" and self.btn_listen_plus and self.btn_listen_plus.collidepoint(pos):
                self._tap_listen(1)
            elif (btn in ("close", "back")) and (
                (self.btn_close and self.btn_close.collidepoint(pos))
                or (self.btn_back and self.btn_back.collidepoint(pos))
            ):
                self.app.switch_scene("main_menu")
        finally:
            self.pressed_button = None

    def _tap_volume(self, delta: int) -> None:
        self.volume_level = max(_VOLUME_MIN, min(_VOLUME_MAX, self.volume_level + delta))
        if getattr(self.app, "tts", None) is not None:
            self.app.tts.set_volume(self.volume_level / _VOLUME_MAX)
        save_setting("TTS", "volume", str(self.volume_level))

    def _tap_listen(self, delta: int) -> None:
        self.listen_seconds = max(_LISTEN_MIN, min(_LISTEN_MAX, self.listen_seconds + delta))
        if getattr(self.app, "asr", None) is not None:
            self.app.asr.listen_seconds = self.listen_seconds
        save_setting("Speech", "listen_seconds", str(self.listen_seconds))

    def _draw_circular_button(self, screen: pygame.Surface, rect: pygame.Rect, symbol: str, is_pressed: bool) -> None:
        cx, cy = rect.center
        r = rect.width // 2

        # Shadow
        if not is_pressed:
            pygame.draw.circle(screen, (35, 10, 45), (cx + 3, cy + 3), r)

        fill_col = (70, 30, 90) if is_pressed else (87, 39, 108)  # #57276C
        stroke_col = (127, 63, 151)  # #7F3F97

        pygame.draw.circle(screen, fill_col, (cx, cy), r)
        pygame.draw.circle(screen, stroke_col, (cx, cy), r, width=4)

        font = getattr(self.app, "font_button", self.app.font_title)
        symbol_text = "X" if symbol.lower() == "x" else symbol
        surf = font.render(symbol_text, True, (255, 250, 243))
        screen.blit(surf, surf.get_rect(center=(cx, cy)))

    @staticmethod
    def _get_card_rect(width: int, height: int) -> pygame.Rect:
        card_width = 720
        return pygame.Rect((width - card_width) // 2, 32, card_width, height - 64)

    def render(self) -> None:
        self._load_assets()
        screen = self.app.screen
        width, height = screen.get_size()
        now_ms = pygame.time.get_ticks()

        # 1. Render Lottie Background (same as Main Menu & Results)
        if self._lottie_bg:
            vf = self._lottie_bg.get_frame(now_ms, (width, height))
            if vf:
                screen.blit(vf, (0, 0))
            else:
                screen.fill((0, 0, 0))
        else:
            screen.fill((0, 0, 0))

        # 2. Centered Purple Card Container (#57276C fill, #7F3F97 stroke)
        card_rect = self._get_card_rect(width, height)

        # Drop shadow
        pygame.draw.rect(screen, (25, 5, 35), card_rect.move(4, 4), border_radius=140)
        # Main body (#57276C) & Border (#7F3F97)
        pygame.draw.rect(screen, (87, 39, 108), card_rect, border_radius=140)
        pygame.draw.rect(screen, (127, 63, 151), card_rect, width=8, border_radius=140)

        cx = card_rect.centerx

        # 3. Top Banner "Options"
        banner_w, banner_h = 300, 64
        banner_rect = pygame.Rect(cx - banner_w // 2, card_rect.top + 28, banner_w, banner_h)
        banner_btn = Button(banner_rect, label="Options", variant="yellow", font=self.app.font_button, stroke_weight=8)
        banner_btn.draw(screen)

        self.btn_close = None

        # Section Font
        title_font = getattr(self.app, "font_button", self.app.font_title)

        # 4. VOLUME SECTION (Shifted downward for balanced layout)
        vol_y = banner_rect.bottom + 85
        vol_lbl = title_font.render("Volume", True, (227, 198, 236))
        screen.blit(vol_lbl, vol_lbl.get_rect(centerx=cx, top=vol_y))

        # 6 Volume level indicators
        vol_row_cy = vol_y + vol_lbl.get_height() + 24
        btn_sz = 60
        seg_w, seg_h, seg_gap = 56, 32, 16
        total_seg_w = _VOLUME_MAX * seg_w + (_VOLUME_MAX - 1) * seg_gap
        seg_x0 = cx - total_seg_w // 2

        for i in range(_VOLUME_MAX):
            rx = seg_x0 + i * (seg_w + seg_gap)
            ry = vol_row_cy - seg_h // 2
            pill_r = pygame.Rect(rx, ry, seg_w, seg_h)
            if (i + 1) <= self.volume_level:
                pygame.draw.rect(screen, (242, 210, 20), pill_r, border_radius=16)  # Gold fill
                pygame.draw.rect(screen, (175, 141, 55), pill_r, width=3, border_radius=16)
            else:
                pygame.draw.rect(screen, (70, 30, 90), pill_r, border_radius=16)
                pygame.draw.rect(screen, (127, 63, 151), pill_r, width=3, border_radius=16)

        self.btn_vol_minus = pygame.Rect(seg_x0 - 40 - btn_sz, vol_row_cy - btn_sz // 2, btn_sz, btn_sz)
        self.btn_vol_plus = pygame.Rect(seg_x0 + total_seg_w + 40, vol_row_cy - btn_sz // 2, btn_sz, btn_sz)
        self._draw_circular_button(screen, self.btn_vol_minus, "-", self.pressed_button == "vol_minus")
        self._draw_circular_button(screen, self.btn_vol_plus, "+", self.pressed_button == "vol_plus")

        # 5. LISTENING TIME SECTION (Spaced down further)
        listen_y = vol_row_cy + 55
        listen_lbl = title_font.render("Listening Time", True, (227, 198, 236))
        screen.blit(listen_lbl, listen_lbl.get_rect(centerx=cx, top=listen_y))

        listen_row_cy = listen_y + listen_lbl.get_height() + 24
        val_surf = title_font.render(f"{self.listen_seconds} seconds", True, (242, 210, 20))
        val_rect = val_surf.get_rect(centerx=cx, centery=listen_row_cy)
        screen.blit(val_surf, val_rect)

        self.btn_listen_minus = pygame.Rect(cx - 210 - btn_sz, listen_row_cy - btn_sz // 2, btn_sz, btn_sz)
        self.btn_listen_plus = pygame.Rect(cx + 210, listen_row_cy - btn_sz // 2, btn_sz, btn_sz)
        self._draw_circular_button(screen, self.btn_listen_minus, "-", self.pressed_button == "listen_minus")
        self._draw_circular_button(screen, self.btn_listen_plus, "+", self.pressed_button == "listen_plus")

        # 6. BOTTOM ACTION BUTTON ("Back to Menu")
        btn_w, btn_h = 325, 64
        btn_y = card_rect.bottom - btn_h - 36
        self.btn_back = pygame.Rect(cx - btn_w // 2, btn_y, btn_w, btn_h)

        back_btn = Button(self.btn_back, label="Back to Menu", variant="yellow", font=self.app.font_button, stroke_weight=8)
        back_btn.is_pressed = (self.pressed_button == "back")
        back_btn.draw(screen)
