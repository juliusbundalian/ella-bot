from __future__ import annotations

import io
from typing import Optional

import pygame

_WHITE = (255, 255, 255)
_BTN_FILL = (255, 182, 193)
_BTN_OUTLINE = (94, 42, 59)
_BTN_PRESSED = (251, 165, 193)
_DANGER = (255, 99, 122)
_TITLE_COLOR = (230, 127, 159)
_SEG_ACTIVE_FILL = (255, 185, 210)
_SEG_INACTIVE_BORDER = (56, 56, 56)

_MODAL_W = 520
_MODAL_H = 560
_HEADER_H = 72


class PauseModal:
    """Options overlay with volume/listen steppers and a nested confirm dialog."""

    def __init__(self, app) -> None:
        self.app = app
        self.show_pause = False
        self.show_confirm = False
        self.confirm_action: Optional[str] = None  # "restart" | "main_menu"
        self._pressed_button: Optional[str] = None
        self.volume_level: int = 6
        self.listen_seconds: int = 5

        self._icon_add = None
        self._icon_remove = None
        self._icon_close = None

        self.restart_rect: Optional[pygame.Rect] = None
        self.main_menu_rect: Optional[pygame.Rect] = None
        self.close_rect: Optional[pygame.Rect] = None
        self.confirm_yes_rect: Optional[pygame.Rect] = None
        self.confirm_no_rect: Optional[pygame.Rect] = None

        self._vol_minus_rect: Optional[pygame.Rect] = None
        self._vol_plus_rect: Optional[pygame.Rect] = None
        self._listen_minus_rect: Optional[pygame.Rect] = None
        self._listen_plus_rect: Optional[pygame.Rect] = None

    @property
    def visible(self) -> bool:
        return self.show_pause or self.show_confirm

    def open(self) -> None:
        self.show_pause = True
        self.show_confirm = False
        self.confirm_action = None
        self._pressed_button = None
        try:
            from ella_bot.config.app_config import load_settings
            settings = load_settings()
        except Exception:
            settings = {}
        volume_fraction = settings.get("volume", 1.0)
        self.volume_level = max(1, min(6, round(volume_fraction * 6)))
        if self.app.asr is not None:
            self.listen_seconds = self.app.asr.listen_seconds
        else:
            self.listen_seconds = int(settings.get("listen_seconds", 5))

    def close(self) -> None:
        self.show_pause = False
        self.show_confirm = False
        self.confirm_action = None
        self._pressed_button = None

    def _load_assets(self) -> None:
        from ella_bot.utils.file_utils import resolve_asset_path
        for attr, filename, size in [
            ("_icon_add", "assets/ic_add.svg", 32),
            ("_icon_remove", "assets/ic_remove.svg", 32),
            ("_icon_close", "assets/ic_close.svg", 28),
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

    def _tap_volume(self, delta: int) -> None:
        from ella_bot.config.app_config import save_setting
        self.volume_level = max(1, min(6, self.volume_level + delta))
        if self.app.tts is not None:
            self.app.tts.set_volume(self.volume_level / 6)
        save_setting("TTS", "volume", str(self.volume_level))

    def _tap_listen(self, delta: int) -> None:
        from ella_bot.config.app_config import save_setting
        self.listen_seconds = max(5, min(10, self.listen_seconds + delta))
        if self.app.asr is not None:
            self.app.asr.listen_seconds = self.listen_seconds
        save_setting("Speech", "listen_seconds", str(self.listen_seconds))

    def _draw_button(self, screen, rect, label, key, radius=18, icon=None) -> None:
        is_pressed = self._pressed_button == key
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
            surf = self.app.font_body.render(label, True, _WHITE)
            screen.blit(surf, surf.get_rect(center=rect.center))

    def hit_test(self, pos) -> Optional[str]:
        if self.show_confirm:
            if self.close_rect and self.close_rect.collidepoint(pos):
                return "close"
            if self.confirm_yes_rect and self.confirm_yes_rect.collidepoint(pos):
                return "confirm_yes"
            if self.confirm_no_rect and self.confirm_no_rect.collidepoint(pos):
                return "confirm_no"
            return "consumed"

        if self.show_pause:
            if self.close_rect and self.close_rect.collidepoint(pos):
                return "resume"
            if self.restart_rect and self.restart_rect.collidepoint(pos):
                return "ask_restart"
            if self.main_menu_rect and self.main_menu_rect.collidepoint(pos):
                return "ask_main_menu"
            if self._vol_minus_rect and self._vol_minus_rect.collidepoint(pos):
                self._tap_volume(-1)
                return "consumed"
            if self._vol_plus_rect and self._vol_plus_rect.collidepoint(pos):
                self._tap_volume(1)
                return "consumed"
            if self._listen_minus_rect and self._listen_minus_rect.collidepoint(pos):
                self._tap_listen(-1)
                return "consumed"
            if self._listen_plus_rect and self._listen_plus_rect.collidepoint(pos):
                self._tap_listen(1)
                return "consumed"
            return "consumed"

        return None

    def render(self, screen, prompt_rect) -> None:
        if not self.visible:
            return

        self._load_assets()

        # Dark overlay
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))

        # Modal rect — 520×560, centered on prompt_rect
        modal_x = prompt_rect.centerx - _MODAL_W // 2
        modal_y = prompt_rect.centery - _MODAL_H // 2
        modal_rect = pygame.Rect(modal_x, modal_y, _MODAL_W, _MODAL_H)

        header_rect = pygame.Rect(modal_rect.left, modal_rect.top, modal_rect.width, _HEADER_H)
        body_rect = pygame.Rect(
            modal_rect.left, modal_rect.top + _HEADER_H,
            modal_rect.width, modal_rect.height - _HEADER_H
        )

        # Draw modal body (white, fully rounded)
        pygame.draw.rect(screen, _WHITE, modal_rect, border_radius=24)
        # Draw header (pink, only top corners rounded)
        pygame.draw.rect(screen, _BTN_FILL, header_rect,
                         border_top_left_radius=24, border_top_right_radius=24,
                         border_bottom_left_radius=0, border_bottom_right_radius=0)
        # Outer border on top
        pygame.draw.rect(screen, _BTN_OUTLINE, modal_rect, width=4, border_radius=24)

        # --- Header content ---
        title_surf = self.app.font_title.render("Options", True, _WHITE)
        title_cy = modal_rect.top + _HEADER_H // 2
        screen.blit(title_surf, title_surf.get_rect(left=modal_rect.left + 24, centery=title_cy))

        close_w, close_h = 44, 44
        close_rect = pygame.Rect(modal_rect.right - 16 - close_w, modal_rect.top + 14, close_w, close_h)
        self.close_rect = close_rect
        # Shadow-rect style with danger fill
        pygame.draw.rect(screen, _BTN_OUTLINE,
                         pygame.Rect(close_rect.left + 4, close_rect.top + 4, close_w, close_h),
                         border_radius=12)
        pygame.draw.rect(screen, _DANGER, close_rect, border_radius=12)
        pygame.draw.rect(screen, _BTN_OUTLINE, close_rect, width=2, border_radius=12)
        if self._icon_close not in (None, False):
            screen.blit(self._icon_close, self._icon_close.get_rect(center=close_rect.center))

        # --- Body ---
        if not self.show_confirm:
            self._draw_body(screen, modal_rect, body_rect)
        else:
            self._draw_confirm(screen, modal_rect, body_rect)

    def _draw_body(self, screen, modal_rect, body_rect) -> None:
        seg_w, seg_h, seg_gap = 48, 24, 8
        total_seg_w = 6 * seg_w + 5 * seg_gap
        btn_sz = 56
        btn_radius = 14
        btn_gap = 16  # gap between button edge and segment group

        body_top = body_rect.top
        body_cx = modal_rect.centerx

        # --- Volume section ---
        vol_label_y = body_top + 24
        vol_lbl = self.app.font_body.render("Volume", True, (50, 50, 50))
        screen.blit(vol_lbl, vol_lbl.get_rect(centerx=body_cx, top=vol_label_y))

        vol_row_cy = vol_label_y + vol_lbl.get_height() + 16 + btn_sz // 2
        seg_x0 = body_cx - total_seg_w // 2
        seg_y = vol_row_cy - seg_h // 2

        for i in range(6):
            rx = seg_x0 + i * (seg_w + seg_gap)
            if (i + 1) <= self.volume_level:
                pygame.draw.rect(screen, _BTN_OUTLINE,
                                 pygame.Rect(rx + 4, seg_y + 2, seg_w, seg_h), border_radius=6)
                pygame.draw.rect(screen, _SEG_ACTIVE_FILL, (rx, seg_y, seg_w, seg_h), border_radius=6)
                pygame.draw.rect(screen, _BTN_OUTLINE, (rx, seg_y, seg_w, seg_h), width=1, border_radius=6)
            else:
                pygame.draw.rect(screen, _SEG_INACTIVE_BORDER,
                                 pygame.Rect(rx + 4, seg_y + 2, seg_w, seg_h), border_radius=6)
                pygame.draw.rect(screen, _WHITE, (rx, seg_y, seg_w, seg_h), border_radius=6)
                pygame.draw.rect(screen, _SEG_INACTIVE_BORDER, (rx, seg_y, seg_w, seg_h), width=1, border_radius=6)

        self._vol_minus_rect = pygame.Rect(seg_x0 - btn_gap - btn_sz, vol_row_cy - btn_sz // 2, btn_sz, btn_sz)
        self._vol_plus_rect = pygame.Rect(seg_x0 + total_seg_w + btn_gap, vol_row_cy - btn_sz // 2, btn_sz, btn_sz)
        self._draw_button(screen, self._vol_minus_rect, "-", "vol_minus", radius=btn_radius,
                          icon=self._icon_remove)
        self._draw_button(screen, self._vol_plus_rect, "+", "vol_plus", radius=btn_radius,
                          icon=self._icon_add)

        # --- Listening Time section ---
        listen_label_y = vol_row_cy + btn_sz // 2 + 20
        listen_lbl = self.app.font_body.render("Listening Time", True, (50, 50, 50))
        screen.blit(listen_lbl, listen_lbl.get_rect(centerx=body_cx, top=listen_label_y))

        val_surf = self.app.font_body.render(f"{self.listen_seconds} seconds", True, _TITLE_COLOR)
        listen_row_cy = listen_label_y + listen_lbl.get_height() + 16 + btn_sz // 2
        val_rect = val_surf.get_rect(centerx=body_cx, centery=listen_row_cy)
        screen.blit(val_surf, val_rect)

        listen_btn_offset = max(total_seg_w // 2 + btn_gap, val_rect.width // 2 + btn_gap + 8)
        self._listen_minus_rect = pygame.Rect(body_cx - listen_btn_offset - btn_sz, listen_row_cy - btn_sz // 2, btn_sz, btn_sz)
        self._listen_plus_rect = pygame.Rect(body_cx + listen_btn_offset, listen_row_cy - btn_sz // 2, btn_sz, btn_sz)
        self._draw_button(screen, self._listen_minus_rect, "-", "listen_minus", radius=btn_radius,
                          icon=self._icon_remove)
        self._draw_button(screen, self._listen_plus_rect, "+", "listen_plus", radius=btn_radius,
                          icon=self._icon_add)

        # --- Divider ---
        div_y = listen_row_cy + btn_sz // 2 + 18
        div_margin = int(modal_rect.width * 0.10)
        pygame.draw.line(screen, _SEG_INACTIVE_BORDER,
                         (modal_rect.left + div_margin, div_y),
                         (modal_rect.right - div_margin, div_y), width=1)

        # --- Action buttons ---
        btn_w = int(modal_rect.width * 0.82)
        btn_h = 56
        stack_gap = 12
        btn_x = modal_rect.centerx - btn_w // 2
        btn_y = div_y + 16

        self.restart_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
        self._draw_button(screen, self.restart_rect, "Restart Level", "restart", radius=18)

        self.main_menu_rect = pygame.Rect(btn_x, btn_y + btn_h + stack_gap, btn_w, btn_h)
        self._draw_button(screen, self.main_menu_rect, "Back to Menu", "main_menu", radius=18)

        # Clear confirm rects
        self.confirm_yes_rect = None
        self.confirm_no_rect = None

    def _draw_confirm(self, screen, modal_rect, body_rect) -> None:
        body_cx = modal_rect.centerx
        body_cy = body_rect.top + body_rect.height // 2

        if self.confirm_action == "restart":
            msg_text = "Restart this level?"
        else:
            msg_text = "Return to main menu?"
        msg_surf = self.app.font_body.render(msg_text, True, (50, 50, 50))
        screen.blit(msg_surf, msg_surf.get_rect(centerx=body_cx, centery=body_cy - 30))

        btn_w = int(modal_rect.width * 0.38)
        btn_h = 52
        gap = 16
        yes_x = body_cx - btn_w - gap // 2
        no_x = body_cx + gap // 2
        btn_y = body_cy + 14

        self.confirm_yes_rect = pygame.Rect(yes_x, btn_y, btn_w, btn_h)
        self.confirm_no_rect = pygame.Rect(no_x, btn_y, btn_w, btn_h)
        self._draw_button(screen, self.confirm_yes_rect, "Yes", "confirm_yes", radius=18)
        self._draw_button(screen, self.confirm_no_rect, "No", "confirm_no", radius=18)

        # Clear action rects
        self.restart_rect = None
        self.main_menu_rect = None
        self._vol_minus_rect = None
        self._vol_plus_rect = None
        self._listen_minus_rect = None
        self._listen_plus_rect = None
