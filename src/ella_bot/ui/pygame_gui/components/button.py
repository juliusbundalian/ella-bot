from __future__ import annotations

import logging
from typing import Callable, Optional, Tuple

import pygame

logger = logging.getLogger(__name__)

# Exact color palettes from Figma specs
BUTTON_THEMES = {
    "yellow": {
        "fill": (242, 210, 20),      # #F2D214
        "stroke": (175, 141, 55),    # #AF8D37
        "text": (87, 39, 108),       # #57276C
        "pressed": (220, 188, 15),
    },
    "violet": {
        "fill": (87, 39, 108),       # #57276C
        "stroke": (127, 63, 151),    # #7F3F97
        "text": (255, 250, 243),     # #FFFAF3
        "pressed": (70, 30, 90),
    },
}


class Button:
    """Reusable Pygame GUI pill-shaped Button matching Figma specs (Yellow & Violet variants)."""

    def __init__(
        self,
        rect: pygame.Rect | Tuple[int, int, int, int],
        label: str = "",
        icon: Optional[pygame.Surface] = None,
        variant: str = "yellow",
        font: Optional[pygame.font.Font] = None,
        corner_radius: int = 50,
        stroke_weight: int = 6,
        on_click: Optional[Callable[[], None]] = None,
    ):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.icon = icon
        self.variant = variant.lower()
        self.font = font
        self.corner_radius = corner_radius
        self.stroke_weight = stroke_weight
        self.on_click = on_click
        self.is_pressed = False
        self.is_hovered = False

    def update_rect(self, rect: pygame.Rect | Tuple[int, int, int, int]) -> None:
        self.rect = pygame.Rect(rect)

    def handle_event(self, event) -> bool:
        """Handles mouse motion and click events. Returns True if button was clicked."""
        if event.type == pygame.MOUSEMOTION:
            self.is_hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.is_pressed = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.is_pressed and self.rect.collidepoint(event.pos):
                self.is_pressed = False
                if self.on_click:
                    self.on_click()
                return True
            self.is_pressed = False
        return False

    def draw(self, screen: pygame.Surface) -> None:
        theme = BUTTON_THEMES.get(self.variant, BUTTON_THEMES["yellow"])
        radius = min(self.corner_radius, self.rect.height // 2)

        fill_color = theme["pressed"] if self.is_pressed else theme["fill"]
        stroke_color = theme["stroke"]
        text_color = theme["text"]

        # Drop shadow offset when not pressed
        if not self.is_pressed:
            shadow_rect = pygame.Rect(
                self.rect.left + 4,
                self.rect.top + 4,
                self.rect.width,
                self.rect.height,
            )
            pygame.draw.rect(screen, stroke_color, shadow_rect, border_radius=radius)

        # Draw main button body
        pygame.draw.rect(screen, fill_color, self.rect, border_radius=radius)

        # Draw thick outer stroke (Figma spec)
        pygame.draw.rect(
            screen,
            stroke_color,
            self.rect,
            width=self.stroke_weight,
            border_radius=radius,
        )

        # Draw icon centered if provided
        if self.icon:
            icon_rect = self.icon.get_rect(center=self.rect.center)
            screen.blit(self.icon, icon_rect)
        # Draw text label centered on true optical bounding rect
        elif self.label and self.font:
            text_surf = self.font.render(self.label, True, text_color)
            bound = text_surf.get_bounding_rect()
            if bound.width > 0 and bound.height > 0:
                text_x = self.rect.centerx - bound.width // 2 - bound.x
                text_y = self.rect.centery - bound.height // 2 - bound.y
                screen.blit(text_surf, (text_x, text_y))
            else:
                text_rect = text_surf.get_rect(center=self.rect.center)
                screen.blit(text_surf, text_rect)
