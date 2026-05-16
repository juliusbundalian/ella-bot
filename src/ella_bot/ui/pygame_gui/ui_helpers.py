from __future__ import annotations

from typing import List
from ella_bot.ui.pygame_gui.config import GUIConfig

def draw_gradient(screen, config: GUIConfig, pygame_module) -> None:
    top = config.background_top
    bottom = config.background_bottom
    width, height = screen.get_size()

    for y in range(height):
        t = y / max(1, height - 1)
        color = (
            int(top[0] * (1 - t) + bottom[0] * t),
            int(top[1] * (1 - t) + bottom[1] * t),
            int(top[2] * (1 - t) + bottom[2] * t),
        )
        pygame_module.draw.line(screen, color, (0, y), (width, y))

def draw_wrapped_text(screen, text: str, font, color: tuple[int, int, int], rect, line_spacing: int = 8) -> None:
    words = text.split()
    lines: List[str] = []
    current = ""

    for word in words:
        test = (current + " " + word).strip()
        if font.size(test)[0] <= rect.width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    y = rect.top
    for line in lines:
        surf = font.render(line, True, color)
        screen.blit(surf, (rect.left, y))
        y += surf.get_height() + line_spacing
        if y > rect.bottom:
            break

def draw_menu_button(screen, pygame_module, rect, text: str, is_pressed: bool, bg_color: tuple[int, int, int], text_color: tuple[int, int, int], outline_color: tuple[int, int, int], font=None) -> None:
    """Draw a menu button with text."""
    pressed_color = (251, 165, 193)  # #FBA5C1
    current_bg_color = pressed_color if is_pressed else bg_color
    
    pygame_module.draw.rect(screen, current_bg_color, rect, border_radius=15)
    pygame_module.draw.rect(screen, outline_color, rect, width=6, border_radius=15)
    
    button_font = font if font else pygame_module.font.SysFont(["Avenir Next", "Segoe UI", "Arial", "sans-serif"], 48, bold=True)
    text_surf = button_font.render(text, True, text_color)
    text_rect = text_surf.get_rect(center=rect.center)
    screen.blit(text_surf, text_rect)
