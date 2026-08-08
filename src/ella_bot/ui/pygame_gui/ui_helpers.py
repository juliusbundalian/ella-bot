from __future__ import annotations

from typing import List, Optional, Tuple
from ella_bot.ui.pygame_gui.config import GUIConfig

# Cached gradient surface — rebuilt only when screen size or colors change.
_gradient_cache: Optional[object] = None
_gradient_key: Optional[Tuple] = None


def draw_gradient(screen, config: GUIConfig, pygame_module) -> None:
    global _gradient_cache, _gradient_key

    top = config.background_top
    bottom = config.background_bottom
    width, height = screen.get_size()
    key = (width, height, top, bottom)

    if _gradient_cache is None or _gradient_key != key:
        surf = pygame_module.Surface((width, height))
        for y in range(height):
            t = y / max(1, height - 1)
            color = (
                int(top[0] * (1 - t) + bottom[0] * t),
                int(top[1] * (1 - t) + bottom[1] * t),
                int(top[2] * (1 - t) + bottom[2] * t),
            )
            pygame_module.draw.line(surf, color, (0, y), (width, y))
        _gradient_cache = surf
        _gradient_key = key

    screen.blit(_gradient_cache, (0, 0))

def parse_parenthesized_segments(
    text: str,
    base_color: tuple[int, int, int] = (56, 56, 56),
    highlight_color: tuple[int, int, int] = (142, 40, 175),
) -> list[tuple[str, tuple[int, int, int]]]:
    """Parse text formatted as 'sound (word)' into colored rendering segments for display_word.

    Example: 'ai (main)' ->
      Display: 'main' with 'ai' highlighted
      Segments: [('m', base), ('ai', highlight), ('n', base)]
    """
    if "(" not in text or ")" not in text:
        return [(text, base_color)]

    try:
        sound_prefix = text.split("(")[0].strip()
        open_paren = text.find("(")
        close_paren = text.find(")", open_paren)
        if open_paren == -1 or close_paren == -1:
            return [(text, base_color)]

        paren_content = text[open_paren + 1 : close_paren].strip()

        if not sound_prefix or not paren_content:
            return [(text, base_color)]

        sound_lower = sound_prefix.lower()
        paren_lower = paren_content.lower()
        idx = paren_lower.find(sound_lower)

        segments: list[tuple[str, tuple[int, int, int]]] = []

        if idx != -1:
            word_prefix = paren_content[:idx]
            target_match = paren_content[idx : idx + len(sound_prefix)]
            word_suffix = paren_content[idx + len(sound_prefix) :]

            if word_prefix:
                segments.append((word_prefix, base_color))
            segments.append((target_match, highlight_color))
            if word_suffix:
                segments.append((word_suffix, base_color))
        else:
            segments.append((paren_content, base_color))

        return segments
    except Exception:
        return [(text, base_color)]


def draw_wrapped_text(
    screen,
    text: str,
    font,
    color: tuple[int, int, int],
    rect,
    line_spacing: int = 8,
    align: str = "left",
    valign: str = "top",
    highlight_color: tuple[int, int, int] = (142, 40, 175),
) -> None:
    # If text is in 'sound (word)' format, render with highlighted sound target
    if "(" in text and ")" in text:
        segments = parse_parenthesized_segments(text, base_color=color, highlight_color=highlight_color)
        seg_surfs = [(font.render(seg_text, True, seg_color), seg_color) for seg_text, seg_color in segments]
        total_width = sum(surf.get_width() for surf, _ in seg_surfs)
        max_height = max((surf.get_height() for surf, _ in seg_surfs), default=font.get_height())

        y = rect.top
        if valign == "center":
            y = rect.top + max(0, (rect.height - max_height) // 2)

        x = rect.left
        if align == "center":
            x = rect.left + max(0, (rect.width - total_width) // 2)

        for surf, _ in seg_surfs:
            screen.blit(surf, (x, y))
            x += surf.get_width()
        return

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

    line_surfs = [font.render(line, True, color) for line in lines]
    total_height = sum(surf.get_height() for surf in line_surfs)
    total_height += line_spacing * max(0, len(line_surfs) - 1)

    y = rect.top
    if valign == "center":
        y = rect.top + max(0, (rect.height - total_height) // 2)

    for surf in line_surfs:
        x = rect.left
        if align == "center":
            x = rect.left + (rect.width - surf.get_width()) // 2
        screen.blit(surf, (x, y))
        y += surf.get_height() + line_spacing
        if y > rect.bottom:
            break

