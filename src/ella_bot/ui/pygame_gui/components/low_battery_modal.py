from __future__ import annotations

import math
import threading
from typing import Optional
import pygame

from ella_bot.services.battery_service import BatteryStatus
from ella_bot.utils.logging import get_logger

logger = get_logger(__name__)


class LowBatteryModal:
    """Uninterruptable modal overlay displayed when ELLA's battery drops to 20% or below."""

    def __init__(self, app) -> None:
        self.app = app
        self.show_modal: bool = False
        self.battery_status: Optional[BatteryStatus] = None
        self._announced: bool = False

    @property
    def visible(self) -> bool:
        return self.show_modal

    def open(self, status: BatteryStatus) -> None:
        self.battery_status = status
        if not self.show_modal:
            self.show_modal = True
            logger.warning("Low battery detected (%.1f%%). Triggering uninterruptable modal.", status.percent)
            if not self._announced:
                self._announced = True
                # Run TTS voice announcement asynchronously in a daemon thread
                # so the Pygame GUI renders the visual modal overlay ON SCREEN INSTANTLY first.
                threading.Thread(target=self._speak_warning, daemon=True).start()

    def update_status(self, status: BatteryStatus) -> None:
        self.battery_status = status
        # Auto-dismiss if battery is now charging or percentage > threshold
        if status.is_charging or not status.is_low_battery:
            if self.show_modal:
                logger.info("Power reconnected or battery level safe (%.1f%%, charging=%s). Dismissing low battery modal.", status.percent, status.is_charging)
            self.close()

    def close(self) -> None:
        self.show_modal = False
        self._announced = False

    def _speak_warning(self) -> None:
        if getattr(self.app, "audio_feedback", False) and getattr(self.app, "tts", None) is not None:
            try:
                msg = "Battery low. To continue using ELLA, please charge or plug in ELLA."
                self.app.tts.speak(msg)
            except Exception as exc:
                logger.warning("Failed to play TTS battery warning: %s", exc)

    def hit_test(self, pos) -> Optional[str]:
        """Uninterruptable modal consumes ALL touch/pointer events, blocking interaction with scenes underneath."""
        if self.visible:
            return "consumed"
        return None

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Consume key and mouse events when modal is active."""
        if self.visible:
            return True  # Event consumed
        return False

    def _get_autofit_surf(self, text: str, max_width: int, start_size: int, color: tuple, bold: bool = False) -> pygame.Surface:
        """Helper to create a rendered text surface that automatically scales down if wider than max_width."""
        size = start_size
        get_font = getattr(self.app, "_get_sys_font", None)
        while size >= 14:
            if get_font:
                font = get_font(size, bold=bold)
            else:
                font = pygame.font.SysFont("sans-serif", size, bold=bold)
            surf = font.render(text, True, color)
            if surf.get_width() <= max_width:
                return surf
            size -= 2
        font = pygame.font.SysFont("sans-serif", 14, bold=bold)
        return font.render(text, True, color)

    def _draw_battery_icon(self, screen: pygame.Surface, center_x: int, center_y: int, percent: float) -> None:
        """Draw a large, sleek, animated low battery icon with a pulsing warning glow."""
        w, h = 150, 76
        rect = pygame.Rect(center_x - w // 2, center_y - h // 2, w, h)
        
        # Pulsing warning glow effect
        ticks = pygame.time.get_ticks()
        pulse = (math.sin(ticks * 0.006) + 1) * 0.5  # 0.0 to 1.0
        glow_color = (
            int(220 + 35 * pulse),
            int(50 * (1 - pulse)),
            int(50 * (1 - pulse))
        )

        # Drop shadow
        pygame.draw.rect(screen, (20, 5, 25), rect.move(5, 5), border_radius=16)

        # Battery outer shell
        pygame.draw.rect(screen, (45, 20, 55), rect, border_radius=16)
        pygame.draw.rect(screen, glow_color, rect, width=5, border_radius=16)

        # Battery terminal tip (right side)
        tip_rect = pygame.Rect(rect.right + 4, center_y - 16, 12, 32)
        pygame.draw.rect(screen, glow_color, tip_rect, border_radius=4)

        # Battery level bar (<= 20% capacity in warning red)
        max_bar_w = w - 24
        bar_w = max(10, int(max_bar_w * (max(5.0, percent) / 100.0)))
        bar_rect = pygame.Rect(rect.left + 12, rect.top + 12, bar_w, h - 24)
        
        pygame.draw.rect(screen, (220, 45, 45), bar_rect, border_radius=8)
        pygame.draw.rect(screen, (255, 130, 130), bar_rect, width=3, border_radius=8)

    def render(self, screen: pygame.Surface) -> None:
        if not self.visible:
            return

        sw, sh = screen.get_size()

        # Semi-transparent dark overlay
        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((15, 8, 22, 230))
        screen.blit(overlay, (0, 0))

        # Responsively scale main dialog card based on screen width/height
        card_w = max(560, min(int(sw * 0.82), 780))
        card_h = max(400, min(int(sh * 0.75), 460))
        card_x = (sw - card_w) // 2
        card_y = (sh - card_h) // 2
        card_rect = pygame.Rect(card_x, card_y, card_w, card_h)

        # Drop shadow & Card body styling (#4A1B54 with glowing warning border)
        pygame.draw.rect(screen, (10, 2, 15), card_rect.move(6, 6), border_radius=28)
        pygame.draw.rect(screen, (72, 28, 92), card_rect, border_radius=28)
        
        # Pulsing Red/Amber warning border
        ticks = pygame.time.get_ticks()
        pulse = (math.sin(ticks * 0.005) + 1) * 0.5
        border_color = (
            int(235 + 20 * pulse),
            int(60 + 60 * pulse),
            50
        )
        pygame.draw.rect(screen, border_color, card_rect, width=6, border_radius=28)

        cx = card_rect.centerx

        # 1. Top Warning Header Banner
        banner_w = min(int(card_w * 0.75), 440)
        banner_h = 56
        banner_rect = pygame.Rect(cx - banner_w // 2, card_rect.top - 24, banner_w, banner_h)
        
        # Banner shadow & background
        pygame.draw.rect(screen, (20, 5, 25), banner_rect.move(3, 3), border_radius=18)
        pygame.draw.rect(screen, (220, 45, 45), banner_rect, border_radius=18)
        pygame.draw.rect(screen, (255, 180, 180), banner_rect, width=4, border_radius=18)

        banner_surf = self._get_autofit_surf("BATTERY LOW", banner_w - 24, start_size=38, color=(255, 255, 255), bold=True)
        screen.blit(banner_surf, banner_surf.get_rect(center=banner_rect.center))

        # 2. Large Battery Icon & Telemetry Display Row (Mathematically Centered Group)
        percent_val = self.battery_status.percent if self.battery_status else 20.0
        row_y = card_rect.top + 135

        p_surf = self._get_autofit_surf(f"{int(percent_val)}%", max_width=200, start_size=60, color=(255, 110, 110), bold=True)

        # Combined bounding box of battery icon (150px shell + 16px terminal tip = 166px) + gap + text width
        icon_total_w = 166
        gap = 20
        total_group_w = icon_total_w + gap + p_surf.get_width()

        group_left = cx - (total_group_w // 2)
        icon_cx = group_left + 75  # Center x of the 150px main battery shell

        self._draw_battery_icon(screen, icon_cx, row_y, percent_val)
        screen.blit(p_surf, p_surf.get_rect(left=group_left + icon_total_w + gap, centery=row_y))

        # 3. Main Instruction Message
        max_text_w = card_w - 60
        line1 = "To continue using ELLA,"
        line2 = "please charge or plug in ELLA."
        
        l1_surf = self._get_autofit_surf(line1, max_text_w, start_size=32, color=(255, 245, 235))
        l2_surf = self._get_autofit_surf(line2, max_text_w, start_size=36, color=(255, 220, 80), bold=True)

        screen.blit(l1_surf, l1_surf.get_rect(centerx=cx, top=card_rect.top + 225))
        screen.blit(l2_surf, l2_surf.get_rect(centerx=cx, top=card_rect.top + 275))


