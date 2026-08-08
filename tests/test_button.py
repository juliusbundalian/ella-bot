import pygame
import pytest

from ella_bot.ui.pygame_gui.components.button import Button


@pytest.mark.parametrize(
    ("variant", "expected_stroke"),
    [
        ("violet", (59, 12, 76, 255)),
        ("yellow", (127, 89, 28, 255)),
    ],
)
def test_button_uses_variant_stroke_color(variant, expected_stroke):
    surface = pygame.Surface((120, 70), pygame.SRCALPHA)
    button = Button(pygame.Rect(10, 10, 100, 40), variant=variant, stroke_weight=6)

    button.draw(surface)

    assert surface.get_at((60, 10)) == expected_stroke
