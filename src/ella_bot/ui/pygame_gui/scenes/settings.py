from __future__ import annotations

import io
import pygame
from ella_bot.ui.pygame_gui.scene import BaseScene
from ella_bot.config.app_config import save_setting
from ella_bot.utils.file_utils import resolve_asset_path

_VOLUME_MIN = 1
_VOLUME_MAX = 6
_LISTEN_MIN = 5
_LISTEN_MAX = 10

_CARD_BG = (0, 0, 0)
_WHITE = (255, 255, 255)
_OUTER_BORDER = (94, 42, 59)
_INNER_BORDER = (255, 185, 207)
_BTN_FILL = (255, 182, 193)
_BTN_OUTLINE = (94, 42, 59)
_BTN_PRESSED = (251, 165, 193)
_DANGER = (255, 99, 122)
_DANGER_PRESSED = (200, 50, 70)
_DANGER_BORDER = (244, 45, 74)
_TITLE_COLOR = (230, 127, 159)


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

        self._icon_add = None
        self._icon_remove = None

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

    def _load_assets(self) -> None:
        for attr, filename, size in [
            ("_icon_add", "assets/ic_add.svg", 36),
            ("_icon_remove", "assets/ic_remove.svg", 36),
        ]:
            if getattr(self, attr) is None:
                try:
                    svg_text = resolve_asset_path(filename).read_text()
                    svg_sized = (svg_text
                                 .replace('height="24px"', f'height="{size}px"')
                                 .replace('width="24px"', f'width="{size}px"'))
                    setattr(self, attr, pygame.image.load(io.BytesIO(svg_sized.encode())).convert_alpha())
                except Exception:
                    setattr(self, attr, False)

    def _draw_button(self, screen, rect, label, key, radius=16, font=None, icon=None) -> None:
        if font is None:
            font = self.app.font_title
        is_pressed = self.pressed_button == key
        bg = _BTN_PRESSED if is_pressed else _BTN_FILL
        if not is_pressed:
            pygame.draw.rect(screen, _BTN_OUTLINE,
                             pygame.Rect(rect.left + 4, rect.top + 4, rect.width, rect.height),
                             border_radius=radius)
        pygame.draw.rect(screen, bg, rect, border_radius=radius)
        pygame.draw.rect(screen, _BTN_OUTLINE, rect, width=2, border_radius=radius)
        if icon:
            screen.blit(icon, icon.get_rect(center=rect.center))
        else:
            surf = font.render(label, True, _WHITE)
            screen.blit(surf, surf.get_rect(center=rect.center))

    def render(self) -> None:
        screen = self.app.screen
        width, height = screen.get_size()
        self._load_assets()

        prompt_rect = pygame.Rect(0, 0, width, height)

        # --- card frame (matching MainMenuScene) ---
        pygame.draw.rect(screen, _CARD_BG, prompt_rect, border_radius=0)
        middle_rect = prompt_rect.inflate(-24, -24)
        pygame.draw.rect(screen, _WHITE, middle_rect, border_radius=56)
        inner_rect = prompt_rect.inflate(-64, -64)
        pygame.draw.rect(screen, _WHITE, inner_rect, border_radius=36)

        # --- Title ---
        title_surf = self.app.font_title.render("Settings", True, _TITLE_COLOR)
        screen.blit(title_surf, title_surf.get_rect(centerx=inner_rect.centerx, top=inner_rect.top + 28))

        # --- Back button (bottom-left) ---
        back_w, back_h = 120, 52
        self.btn_back = pygame.Rect(
            inner_rect.left + 24,
            inner_rect.bottom - 20 - back_h,
            back_w, back_h,
        )
        self._draw_button(screen, self.btn_back, "Back", "back", radius=16, font=self.app.font_body)

        # --- Volume section ---
        # Label centered horizontally, ~45% down from inner_rect.top
        vol_label_y = inner_rect.centery - 110
        vol_lbl = self.app.font_body.render("Volume", True, (50, 50, 50))
        screen.blit(vol_lbl, vol_lbl.get_rect(centerx=inner_rect.centerx, top=vol_label_y))

        seg_w, seg_h, seg_gap = 52, 36, 8
        total_seg_w = _VOLUME_MAX * seg_w + (_VOLUME_MAX - 1) * seg_gap
        seg_x0 = inner_rect.centerx - total_seg_w // 2
        seg_y = vol_label_y + vol_lbl.get_height() + 30

        # Draw volume segments
        for i in range(_VOLUME_MAX):
            rx = seg_x0 + i * (seg_w + seg_gap)
            if (i + 1) <= self.volume_level:
                pygame.draw.rect(screen, _BTN_FILL, (rx, seg_y, seg_w, seg_h), border_radius=8)
            else:
                pygame.draw.rect(screen, _WHITE, (rx, seg_y, seg_w, seg_h), border_radius=8)
                pygame.draw.rect(screen, _BTN_OUTLINE, (rx, seg_y, seg_w, seg_h), width=2, border_radius=8)

        # Volume -/+ buttons (62x62, 12px gap from segments)
        btn_sz = 62
        self.btn_vol_minus = pygame.Rect(seg_x0 - btn_sz - 12, seg_y, btn_sz, btn_sz)
        self.btn_vol_plus = pygame.Rect(seg_x0 + total_seg_w + 12, seg_y, btn_sz, btn_sz)
        self._draw_button(screen, self.btn_vol_minus, "-", "vol_minus", radius=14, icon=self._icon_remove or None)
        self._draw_button(screen, self.btn_vol_plus, "+", "vol_plus", radius=14, icon=self._icon_add or None)

        # --- Listening Time section ---
        listen_top = seg_y + seg_h + 30
        listen_lbl = self.app.font_body.render("Listening Time", True, (50, 50, 50))
        screen.blit(listen_lbl, listen_lbl.get_rect(centerx=inner_rect.centerx, top=listen_top))

        val_surf = self.app.font_body.render(f"{self.listen_seconds} seconds", True, _TITLE_COLOR)
        val_rect = val_surf.get_rect(centerx=inner_rect.centerx, top=listen_top + listen_lbl.get_height() + 20)
        screen.blit(val_surf, val_rect)

        self.btn_listen_minus = pygame.Rect(val_rect.left - btn_sz - 12, val_rect.top, btn_sz, btn_sz)
        self.btn_listen_plus = pygame.Rect(val_rect.right + 12, val_rect.top, btn_sz, btn_sz)
        self._draw_button(screen, self.btn_listen_minus, "-", "listen_minus", radius=14, icon=self._icon_remove or None)
        self._draw_button(screen, self.btn_listen_plus, "+", "listen_plus", radius=14, icon=self._icon_add or None)

        # --- Reset Progress button ---
        reset_w, reset_h = 380, 70
        reset_x = inner_rect.centerx - reset_w // 2
        reset_y = inner_rect.bottom - 60 - reset_h
        self.btn_reset = pygame.Rect(reset_x, reset_y, reset_w, reset_h)
        is_reset_pressed = self.pressed_button == "reset"
        reset_bg = _DANGER_PRESSED if is_reset_pressed else _DANGER
        if not is_reset_pressed:
            pygame.draw.rect(screen, _DANGER_BORDER,
                             pygame.Rect(self.btn_reset.left + 6, self.btn_reset.top + 6,
                                         self.btn_reset.width, self.btn_reset.height),
                             border_radius=15)
        pygame.draw.rect(screen, reset_bg, self.btn_reset, border_radius=15)
        pygame.draw.rect(screen, _DANGER_BORDER, self.btn_reset, width=2, border_radius=15)
        rs = self.app.font_body.render("Reset Progress", True, _WHITE)
        screen.blit(rs, rs.get_rect(center=self.btn_reset.center))

        # --- Outer/inner pink borders (on top) ---
        pygame.draw.rect(screen, _OUTER_BORDER, prompt_rect, width=12, border_radius=68)
        pygame.draw.rect(screen, _INNER_BORDER, inner_rect, width=12, border_radius=36)

        # --- Confirmation overlay ---
        if self.show_reset_confirm:
            overlay = pygame.Surface((width, height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            screen.blit(overlay, (0, 0))

            dlg_w = int(width * 0.55)
            dlg_h = int(height * 0.32)
            dlg_x = (width - dlg_w) // 2
            dlg_y = (height - dlg_h) // 2
            dlg = pygame.Rect(dlg_x, dlg_y, dlg_w, dlg_h)
            pygame.draw.rect(screen, _WHITE, dlg, border_radius=20)
            pygame.draw.rect(screen, _BTN_OUTLINE, dlg, width=4, border_radius=20)

            msg = self.app.font_body.render("Reset all progress to Level 1?", True, (50, 50, 50))
            screen.blit(msg, msg.get_rect(center=(width // 2, dlg_y + int(dlg_h * 0.35))))

            bw, bh = 150, 62
            by = dlg_y + dlg_h - bh - 22
            self.btn_confirm_yes = pygame.Rect(width // 2 - bw - 14, by, bw, bh)
            self.btn_confirm_no = pygame.Rect(width // 2 + 14, by, bw, bh)
            self._draw_button(screen, self.btn_confirm_yes, "Yes", "confirm_yes", font=self.app.font_body)
            self._draw_button(screen, self.btn_confirm_no, "No", "confirm_no", font=self.app.font_body)
