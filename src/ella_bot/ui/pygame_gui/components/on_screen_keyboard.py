from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pygame


@dataclass(frozen=True)
class KeyboardAction:
    kind: Literal["text", "backspace", "shift"]
    text: str = ""


@dataclass(frozen=True)
class _Key:
    key_id: str
    label: str
    action: KeyboardAction
    weight: float = 1.0


class OnScreenKeyboard:
    _LETTER_ROWS = ("qwertyuiop", "asdfghjkl", "zxcvbnm")

    def __init__(self, font) -> None:
        self.font = font
        self.uppercase = False
        self._pressed_key: str | None = None
        self._keys: dict[str, _Key] = {}
        self._key_rects: dict[str, pygame.Rect] = {}

    @property
    def key_rects(self) -> dict[str, pygame.Rect]:
        return dict(self._key_rects)

    def reset(self) -> None:
        self.uppercase = False
        self.cancel_press()

    def cancel_press(self) -> None:
        self._pressed_key = None

    def _rows(self) -> tuple[tuple[_Key, ...], ...]:
        letter_rows = []
        for letters in self._LETTER_ROWS:
            row = tuple(
                _Key(
                    letter,
                    letter.upper() if self.uppercase else letter,
                    KeyboardAction(
                        "text", letter.upper() if self.uppercase else letter
                    ),
                )
                for letter in letters
            )
            letter_rows.append(row)
        controls = (
            _Key("shift", "Shift", KeyboardAction("shift"), 1.35),
            _Key("apostrophe", "'", KeyboardAction("text", "'"), 0.75),
            _Key("space", "Space", KeyboardAction("text", " "), 4.0),
            _Key("hyphen", "-", KeyboardAction("text", "-"), 0.75),
            _Key("backspace", "Back", KeyboardAction("backspace"), 1.6),
        )
        return (*letter_rows, controls)

    def _layout(self, bounds: pygame.Rect) -> None:
        rows = self._rows()
        row_gap = max(4, min(8, bounds.height // 30))
        key_gap = max(4, min(8, bounds.width // 120))
        key_height = (bounds.height - row_gap * (len(rows) - 1)) // len(rows)
        self._keys = {}
        self._key_rects = {}
        for row_index, row in enumerate(rows):
            total_weight = sum(key.weight for key in row)
            usable_width = bounds.width - key_gap * (len(row) - 1)
            unit = usable_width / total_weight
            widths = [int(unit * key.weight) for key in row]
            widths[-1] += usable_width - sum(widths)
            row_width = sum(widths) + key_gap * (len(row) - 1)
            x = bounds.centerx - row_width // 2
            y = bounds.top + row_index * (key_height + row_gap)
            for key, width in zip(row, widths):
                self._keys[key.key_id] = key
                self._key_rects[key.key_id] = pygame.Rect(
                    x, y, width, key_height
                )
                x += width + key_gap

    def draw(self, screen: pygame.Surface, bounds: pygame.Rect) -> None:
        self._layout(pygame.Rect(bounds))
        for key_id, rect in self._key_rects.items():
            pressed = key_id == self._pressed_key
            active_shift = key_id == "shift" and self.uppercase
            fill = (200, 160, 20) if pressed else (242, 210, 20)
            if active_shift and not pressed:
                fill = (255, 232, 90)
            pygame.draw.rect(
                screen, (25, 5, 35), rect.move(3, 3), border_radius=10
            )
            pygame.draw.rect(screen, fill, rect, border_radius=10)
            pygame.draw.rect(
                screen, (175, 141, 55), rect, width=2, border_radius=10
            )
            label = self.font.render(self._keys[key_id].label, True, (35, 10, 45))
            screen.blit(label, label.get_rect(center=rect.center))

    def _key_at(self, pos) -> str | None:
        return next(
            (
                key_id
                for key_id, rect in self._key_rects.items()
                if rect.collidepoint(pos)
            ),
            None,
        )

    def handle_mouse_down(self, pos) -> bool:
        self._pressed_key = self._key_at(pos)
        return self._pressed_key is not None

    def handle_mouse_up(self, pos) -> KeyboardAction | None:
        pressed = self._pressed_key
        self._pressed_key = None
        if pressed is None or self._key_at(pos) != pressed:
            return None
        action = self._keys[pressed].action
        if action.kind == "shift":
            self.uppercase = not self.uppercase
            return action
        if len(pressed) == 1 and pressed.isalpha():
            letter = pressed.upper() if self.uppercase else pressed
            return KeyboardAction("text", letter)
        return action
