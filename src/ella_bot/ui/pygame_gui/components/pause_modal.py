from __future__ import annotations

import io
from typing import Optional
import pygame

from ella_bot.ui.pygame_gui.components.button import Button
from ella_bot.utils.file_utils import resolve_asset_path

_VOLUME_MAX = 6


class PauseModal:
    """Options / Pause overlay during reading level matching Figma design specs."""

    def __init__(self, app) -> None:
        self.app = app
        self.show_pause = False
        self.show_confirm = False
        self.confirm_action: Optional[str] = None  # "restart" | "main_menu"
        self._pressed_button: Optional[str] = None
        self.volume_level: int = 6
        self.listen_seconds: int = 5
        self._volume_down_icon = None
        self._volume_up_icon = None
        self._decrease_icon = None
        self._increase_icon = None

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

    def _tap_volume(self, delta: int) -> None:
        from ella_bot.config.app_config import save_setting
        self.volume_level = max(1, min(6, self.volume_level + delta))
        if self.app.tts is not None:
            self.app.tts.set_volume(self.volume_level / 6)
        save_setting("TTS", "volume", str(self.volume_level))

    def _tap_listen(self, delta: int) -> None:
        from ella_bot.config.app_config import save_setting
        self.listen_seconds = max(5, min(12, self.listen_seconds + delta))
        if self.app.asr is not None:
            self.app.asr.listen_seconds = self.listen_seconds
        save_setting("Speech", "listen_seconds", str(self.listen_seconds))

    def _load_assets(self) -> None:
        for attr, asset, source_size, target_size in (
            ("_volume_down_icon", "assets/ic_volume_down.svg", (23, 24), (31, 32)),
            ("_volume_up_icon", "assets/ic_volume_up.svg", (23, 24), (31, 32)),
            ("_decrease_icon", "assets/ic_decrease.svg", (24, 10), (24, 10)),
            ("_increase_icon", "assets/ic_increase.svg", (25, 25), (25, 25)),
        ):
            if getattr(self, attr) is None:
                try:
                    svg = resolve_asset_path(asset).read_text(encoding="utf-8")
                    source_w, source_h = source_size
                    target_w, target_h = target_size
                    svg = svg.replace(
                        f'width="{source_w}" height="{source_h}"',
                        f'width="{target_w}" height="{target_h}"',
                    )
                    icon = pygame.image.load(io.BytesIO(svg.encode("utf-8"))).convert_alpha()
                    setattr(self, attr, icon)
                except Exception:
                    setattr(self, attr, False)

    def _draw_control_button(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        symbol: str,
        is_pressed: bool,
        icon=None,
        *,
        circular: bool = False,
    ) -> None:
        cx, cy = rect.center

        fill_col = (70, 30, 90) if is_pressed else (87, 39, 108)  # #57276C
        stroke_col = (127, 63, 151)  # #7F3F97

        if circular:
            r = rect.width // 2
            if not is_pressed:
                pygame.draw.circle(screen, (35, 10, 45), (cx + 3, cy + 3), r)
            pygame.draw.circle(screen, fill_col, (cx, cy), r)
            pygame.draw.circle(screen, stroke_col, (cx, cy), r, width=4)
        else:
            if not is_pressed:
                pygame.draw.rect(screen, (35, 10, 45), rect.move(3, 3), border_radius=18)
            pygame.draw.rect(screen, fill_col, rect, border_radius=18)
            pygame.draw.rect(screen, stroke_col, rect, width=4, border_radius=18)

        if icon:
            surf = icon
        else:
            font = getattr(self.app, "font_button", self.app.font_title)
            symbol_text = "X" if symbol.lower() == "x" else symbol
            surf = font.render(symbol_text, True, (255, 250, 243))
        screen.blit(surf, surf.get_rect(center=(cx, cy)))

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

    def render(self, screen: pygame.Surface, prompt_rect: pygame.Rect) -> None:
        if not self.visible:
            return

        self._load_assets()

        # Semi-transparent dark backdrop
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        # Main Dialog Card (Figma spec 720x540)
        card_w, card_h = 720, 540
        card_x = prompt_rect.centerx - card_w // 2
        card_y = prompt_rect.centery - card_h // 2 + 10
        card_rect = pygame.Rect(card_x, card_y, card_w, card_h)

        # Drop shadow
        pygame.draw.rect(screen, (25, 5, 35), card_rect.move(5, 5), border_radius=140)
        # Main body (#57276C) & Border (#7F3F97)
        pygame.draw.rect(screen, (87, 39, 108), card_rect, border_radius=140)
        pygame.draw.rect(screen, (127, 63, 151), card_rect, width=8, border_radius=140)

        cx = card_rect.centerx

        # Top Banner "Options"
        banner_w, banner_h = 280, 58
        banner_rect = pygame.Rect(cx - banner_w // 2, card_rect.top - 18, banner_w, banner_h)
        banner_btn = Button(banner_rect, label="Options", variant="yellow", font=self.app.font_button, stroke_weight=6)
        banner_btn.draw(screen)

        # Top-Right Close "X" Button
        close_sz = 56
        self.close_rect = pygame.Rect(card_rect.right - close_sz - 24, card_rect.top + 16, close_sz, close_sz)
        self._draw_control_button(
            screen,
            self.close_rect,
            "X",
            self._pressed_button == "close",
            circular=True,
        )

        if self.show_confirm:
            self._draw_confirm(screen, card_rect)
            return

        title_font = getattr(self.app, "font_button", self.app.font_title)

        # 1. VOLUME SECTION
        vol_y = card_rect.top + 75
        vol_lbl = title_font.render("Volume", True, (227, 198, 236))
        screen.blit(vol_lbl, vol_lbl.get_rect(centerx=cx, top=vol_y))

        vol_row_cy = vol_y + vol_lbl.get_height() + 22
        btn_sz = 54
        seg_w, seg_h, seg_gap = 44, 26, 12
        total_seg_w = _VOLUME_MAX * seg_w + (_VOLUME_MAX - 1) * seg_gap
        seg_x0 = cx - total_seg_w // 2

        for i in range(_VOLUME_MAX):
            rx = seg_x0 + i * (seg_w + seg_gap)
            ry = vol_row_cy - seg_h // 2
            pill_r = pygame.Rect(rx, ry, seg_w, seg_h)
            if (i + 1) <= self.volume_level:
                pygame.draw.rect(screen, (242, 210, 20), pill_r, border_radius=13)  # Gold fill
                pygame.draw.rect(screen, (175, 141, 55), pill_r, width=3, border_radius=13)
            else:
                pygame.draw.rect(screen, (70, 30, 90), pill_r, border_radius=13)
                pygame.draw.rect(screen, (127, 63, 151), pill_r, width=3, border_radius=13)

        self._vol_minus_rect = pygame.Rect(seg_x0 - 30 - btn_sz, vol_row_cy - btn_sz // 2, btn_sz, btn_sz)
        self._vol_plus_rect = pygame.Rect(seg_x0 + total_seg_w + 30, vol_row_cy - btn_sz // 2, btn_sz, btn_sz)
        self._draw_control_button(
            screen,
            self._vol_minus_rect,
            "-",
            self._pressed_button == "vol_minus",
            self._volume_down_icon,
        )
        self._draw_control_button(
            screen,
            self._vol_plus_rect,
            "+",
            self._pressed_button == "vol_plus",
            self._volume_up_icon,
        )

        # 2. LISTENING TIME SECTION
        listen_y = vol_row_cy + 38
        listen_lbl = title_font.render("Listening Time", True, (227, 198, 236))
        screen.blit(listen_lbl, listen_lbl.get_rect(centerx=cx, top=listen_y))

        listen_row_cy = listen_y + listen_lbl.get_height() + 22
        val_surf = title_font.render(f"{self.listen_seconds} seconds", True, (242, 210, 20))
        val_rect = val_surf.get_rect(centerx=cx, centery=listen_row_cy)
        screen.blit(val_surf, val_rect)

        self._listen_minus_rect = pygame.Rect(cx - 180 - btn_sz, listen_row_cy - btn_sz // 2, btn_sz, btn_sz)
        self._listen_plus_rect = pygame.Rect(cx + 180, listen_row_cy - btn_sz // 2, btn_sz, btn_sz)
        self._draw_control_button(
            screen,
            self._listen_minus_rect,
            "-",
            self._pressed_button == "listen_minus",
            self._decrease_icon,
        )
        self._draw_control_button(
            screen,
            self._listen_plus_rect,
            "+",
            self._pressed_button == "listen_plus",
            self._increase_icon,
        )

        # 3. ACTION BUTTONS ("Restart Level" & "Back to Menu")
        btn_w, btn_h = 325, 58
        stack_gap = 14
        btn_start_y = card_rect.bottom - (btn_h * 2 + stack_gap + 35)

        # Restart Level (Violet variant)
        self.restart_rect = pygame.Rect(cx - btn_w // 2, btn_start_y, btn_w, btn_h)
        restart_btn = Button(self.restart_rect, label="Restart Level", variant="violet", font=self.app.font_button, stroke_weight=6)
        restart_btn.is_pressed = (self._pressed_button == "restart")
        restart_btn.draw(screen)

        # Back to Menu (Yellow variant)
        self.main_menu_rect = pygame.Rect(cx - btn_w // 2, btn_start_y + btn_h + stack_gap, btn_w, btn_h)
        menu_btn = Button(self.main_menu_rect, label="Back to Menu", variant="yellow", font=self.app.font_button, stroke_weight=6)
        menu_btn.is_pressed = (self._pressed_button == "main_menu")
        menu_btn.draw(screen)

        # Clear confirm rects
        self.confirm_yes_rect = None
        self.confirm_no_rect = None

    def _draw_confirm(self, screen: pygame.Surface, card_rect: pygame.Rect) -> None:
        cx = card_rect.centerx
        title_font = getattr(self.app, "font_button", self.app.font_title)

        if self.confirm_action == "restart":
            msg_text = "Restart this level?"
        else:
            msg_text = "Return to main menu?"

        msg_surf = title_font.render(msg_text, True, (255, 250, 243))
        screen.blit(msg_surf, msg_surf.get_rect(centerx=cx, centery=card_rect.centery - 40))

        btn_w, btn_h = 180, 56
        gap = 24
        yes_x = cx - btn_w - gap // 2
        no_x = cx + gap // 2
        btn_y = card_rect.centery + 30

        self.confirm_yes_rect = pygame.Rect(yes_x, btn_y, btn_w, btn_h)
        self.confirm_no_rect = pygame.Rect(no_x, btn_y, btn_w, btn_h)

        btn_yes = Button(self.confirm_yes_rect, label="Yes", variant="yellow", font=self.app.font_button, stroke_weight=6)
        btn_yes.is_pressed = (self._pressed_button == "confirm_yes")
        btn_yes.draw(screen)

        btn_no = Button(self.confirm_no_rect, label="No", variant="yellow", font=self.app.font_button, stroke_weight=6)
        btn_no.is_pressed = (self._pressed_button == "confirm_no")
        btn_no.draw(screen)

        # Clear action rects
        self.restart_rect = None
        self.main_menu_rect = None
        self._vol_minus_rect = None
        self._vol_plus_rect = None
        self._listen_minus_rect = None
        self._listen_plus_rect = None
