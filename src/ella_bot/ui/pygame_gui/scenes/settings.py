from __future__ import annotations

import pygame
from ella_bot.ui.pygame_gui.scene import BaseScene
from ella_bot.config.app_config import save_setting
from ella_bot.ui.pygame_gui.ui_helpers import draw_menu_button

_VOLUME_MIN = 1
_VOLUME_MAX = 6
_LISTEN_MIN = 5
_LISTEN_MAX = 10


class SettingsScene(BaseScene):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.volume_level: int = _VOLUME_MAX
        self.listen_seconds: int = _LISTEN_MIN
        self.pressed_button: str | None = None
        self.show_reset_confirm: bool = False

        self.btn_vol_minus: pygame.Rect | None = None
        self.btn_vol_plus: pygame.Rect | None = None
        self.btn_listen_minus: pygame.Rect | None = None
        self.btn_listen_plus: pygame.Rect | None = None
        self.btn_reset: pygame.Rect | None = None
        self.btn_back: pygame.Rect | None = None
        self.btn_confirm_yes: pygame.Rect | None = None
        self.btn_confirm_no: pygame.Rect | None = None

        self.bg_color = (245, 205, 214)
        self.btn_color = (248, 111, 150)
        self.btn_text_color = (255, 255, 255)
        self.btn_outline_color = (0, 0, 0)
        self.btn_pressed_color = (251, 165, 193)
        self.seg_filled_color = (248, 111, 150)
        self.seg_empty_color = (210, 170, 185)
        self.danger_color = (220, 70, 90)
        self.danger_pressed_color = (200, 50, 70)

    def on_enter(self) -> None:
        self.show_reset_confirm = False
        self.pressed_button = None
        try:
            from ella_bot.config.app_config import load_settings
            settings = load_settings()
        except Exception:
            settings = {}
        volume_fraction = settings.get("volume", 1.0)
        self.volume_level = max(_VOLUME_MIN, min(_VOLUME_MAX, round(volume_fraction * _VOLUME_MAX)))
        if self.app.asr is not None:
            self.listen_seconds = self.app.asr.listen_seconds
        else:
            self.listen_seconds = int(settings.get("listen_seconds", _LISTEN_MIN))

    def handle_event(self, event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._on_mouse_down(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._on_mouse_up(event.pos)

    def _on_mouse_down(self, pos) -> None:
        if self.show_reset_confirm:
            if self.btn_confirm_yes and self.btn_confirm_yes.collidepoint(pos):
                self.pressed_button = "confirm_yes"
            elif self.btn_confirm_no and self.btn_confirm_no.collidepoint(pos):
                self.pressed_button = "confirm_no"
            return
        for name, rect in [
            ("vol_minus", self.btn_vol_minus),
            ("vol_plus", self.btn_vol_plus),
            ("listen_minus", self.btn_listen_minus),
            ("listen_plus", self.btn_listen_plus),
            ("reset", self.btn_reset),
            ("back", self.btn_back),
        ]:
            if rect and rect.collidepoint(pos):
                self.pressed_button = name
                break

    def _on_mouse_up(self, pos) -> None:
        try:
            if self.show_reset_confirm:
                if self.pressed_button == "confirm_yes" and self.btn_confirm_yes and self.btn_confirm_yes.collidepoint(pos):
                    self.app.session.reset_to_start()
                    self.app.switch_scene("main_menu")
                elif self.pressed_button == "confirm_no" and self.btn_confirm_no and self.btn_confirm_no.collidepoint(pos):
                    self.show_reset_confirm = False
                return
            btn = self.pressed_button
            if btn == "vol_minus" and self.btn_vol_minus and self.btn_vol_minus.collidepoint(pos):
                self._tap_volume(-1)
            elif btn == "vol_plus" and self.btn_vol_plus and self.btn_vol_plus.collidepoint(pos):
                self._tap_volume(1)
            elif btn == "listen_minus" and self.btn_listen_minus and self.btn_listen_minus.collidepoint(pos):
                self._tap_listen(-1)
            elif btn == "listen_plus" and self.btn_listen_plus and self.btn_listen_plus.collidepoint(pos):
                self._tap_listen(1)
            elif btn == "reset" and self.btn_reset and self.btn_reset.collidepoint(pos):
                self.show_reset_confirm = True
            elif btn == "back" and self.btn_back and self.btn_back.collidepoint(pos):
                self.app.switch_scene("main_menu")
        finally:
            self.pressed_button = None

    def _tap_volume(self, delta: int) -> None:
        self.volume_level = max(_VOLUME_MIN, min(_VOLUME_MAX, self.volume_level + delta))
        self.app.tts.set_volume(self.volume_level / _VOLUME_MAX)
        save_setting("TTS", "volume", str(self.volume_level))

    def _tap_listen(self, delta: int) -> None:
        self.listen_seconds = max(_LISTEN_MIN, min(_LISTEN_MAX, self.listen_seconds + delta))
        if self.app.asr is not None:
            self.app.asr.listen_seconds = self.listen_seconds
        save_setting("Speech", "listen_seconds", str(self.listen_seconds))

    def render(self) -> None:
        screen = self.app.screen
        w, h = screen.get_size()
        screen.fill(self.bg_color)

        title = self.app.font_title.render("Settings", True, (0, 0, 0))
        screen.blit(title, title.get_rect(center=(w // 2, int(h * 0.10))))

        cx = w // 2
        btn_sz = 70
        btn_r = 12

        # Volume row
        vol_label_y = int(h * 0.28)
        lbl = self.app.font_body.render("Volume", True, (0, 0, 0))
        screen.blit(lbl, lbl.get_rect(midleft=(cx - 260, vol_label_y)))

        seg_w, seg_h, seg_gap = 52, 36, 8
        total_seg_w = _VOLUME_MAX * seg_w + (_VOLUME_MAX - 1) * seg_gap
        seg_x0 = cx - total_seg_w // 2
        seg_y = vol_label_y + 40
        for i in range(_VOLUME_MAX):
            rx = seg_x0 + i * (seg_w + seg_gap)
            color = self.seg_filled_color if (i + 1) <= self.volume_level else self.seg_empty_color
            pygame.draw.rect(screen, color, (rx, seg_y, seg_w, seg_h), border_radius=8)
            if (i + 1) > self.volume_level:
                pygame.draw.rect(screen, self.btn_outline_color, (rx, seg_y, seg_w, seg_h), width=2, border_radius=8)

        self.btn_vol_minus = pygame.Rect(seg_x0 - btn_sz - 12, seg_y, btn_sz, btn_sz)
        self.btn_vol_plus = pygame.Rect(seg_x0 + total_seg_w + 12, seg_y, btn_sz, btn_sz)
        for rect, symbol, key in [
            (self.btn_vol_minus, "-", "vol_minus"),
            (self.btn_vol_plus, "+", "vol_plus"),
        ]:
            pressed = self.pressed_button == key
            bg = self.btn_pressed_color if pressed else self.btn_color
            pygame.draw.rect(screen, bg, rect, border_radius=btn_r)
            pygame.draw.rect(screen, self.btn_outline_color, rect, width=4, border_radius=btn_r)
            s = self.app.font_button.render(symbol, True, self.btn_text_color)
            screen.blit(s, s.get_rect(center=rect.center))

        # Listen Time row
        listen_label_y = int(h * 0.50)
        lbl2 = self.app.font_body.render("Listen Time", True, (0, 0, 0))
        screen.blit(lbl2, lbl2.get_rect(midleft=(cx - 260, listen_label_y)))

        val = self.app.font_button.render(f"{self.listen_seconds} sec", True, (0, 0, 0))
        val_rect = val.get_rect(center=(cx, listen_label_y + 40 + btn_sz // 2))
        screen.blit(val, val_rect)

        self.btn_listen_minus = pygame.Rect(val_rect.left - btn_sz - 16, val_rect.top, btn_sz, btn_sz)
        self.btn_listen_plus = pygame.Rect(val_rect.right + 16, val_rect.top, btn_sz, btn_sz)
        for rect, symbol, key in [
            (self.btn_listen_minus, "-", "listen_minus"),
            (self.btn_listen_plus, "+", "listen_plus"),
        ]:
            pressed = self.pressed_button == key
            bg = self.btn_pressed_color if pressed else self.btn_color
            pygame.draw.rect(screen, bg, rect, border_radius=btn_r)
            pygame.draw.rect(screen, self.btn_outline_color, rect, width=4, border_radius=btn_r)
            s = self.app.font_button.render(symbol, True, self.btn_text_color)
            screen.blit(s, s.get_rect(center=rect.center))

        # Reset Progress button
        reset_w, reset_h = 320, 90
        self.btn_reset = pygame.Rect(cx - reset_w // 2, int(h * 0.70), reset_w, reset_h)
        reset_bg = self.danger_pressed_color if self.pressed_button == "reset" else self.danger_color
        pygame.draw.rect(screen, reset_bg, self.btn_reset, border_radius=15)
        pygame.draw.rect(screen, self.btn_outline_color, self.btn_reset, width=6, border_radius=15)
        rs = self.app.font_body.render("Reset Progress", True, (255, 255, 255))
        screen.blit(rs, rs.get_rect(center=self.btn_reset.center))

        # Back button
        back_w, back_h = 180, 70
        self.btn_back = pygame.Rect(24, h - back_h - 24, back_w, back_h)
        draw_menu_button(screen, pygame, self.btn_back, "Back",
                         self.pressed_button == "back",
                         self.btn_color, self.btn_text_color, self.btn_outline_color,
                         font=self.app.font_body)

        # Confirmation overlay
        if self.show_reset_confirm:
            overlay = pygame.Surface((w, h), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            screen.blit(overlay, (0, 0))

            dlg_w = int(w * 0.7)
            dlg_h = int(h * 0.32)
            dlg_x = (w - dlg_w) // 2
            dlg_y = (h - dlg_h) // 2
            dlg = pygame.Rect(dlg_x, dlg_y, dlg_w, dlg_h)
            pygame.draw.rect(screen, (255, 255, 255), dlg, border_radius=12)
            pygame.draw.rect(screen, (0, 0, 0), dlg, width=6, border_radius=12)

            msg = self.app.font_body.render("Reset all progress to Level 1?", True, (0, 0, 0))
            screen.blit(msg, msg.get_rect(center=(w // 2, dlg_y + int(dlg_h * 0.35))))

            bw, bh = 160, 70
            by = dlg_y + dlg_h - bh - 24
            self.btn_confirm_yes = pygame.Rect(w // 2 - bw - 12, by, bw, bh)
            self.btn_confirm_no = pygame.Rect(w // 2 + 12, by, bw, bh)
            for rect, text, key in [
                (self.btn_confirm_yes, "Yes", "confirm_yes"),
                (self.btn_confirm_no, "No", "confirm_no"),
            ]:
                pressed = self.pressed_button == key
                bg = self.btn_pressed_color if pressed else self.btn_color
                pygame.draw.rect(screen, bg, rect, border_radius=12)
                pygame.draw.rect(screen, self.btn_outline_color, rect, width=6, border_radius=12)
                ts = self.app.font_body.render(text, True, (255, 255, 255))
                screen.blit(ts, ts.get_rect(center=rect.center))
