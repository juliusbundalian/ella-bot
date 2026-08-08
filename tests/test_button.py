import pygame
import pytest

from ella_bot.ui.pygame_gui.components.button import Button


@pytest.mark.parametrize(
    ("variant", "expected_stroke"),
    [
        ("violet", (127, 63, 151, 255)),
        ("yellow", (175, 141, 55, 255)),
    ],
)
def test_button_uses_original_variant_stroke(variant, expected_stroke):
    surface = pygame.Surface((120, 70), pygame.SRCALPHA)
    button = Button(pygame.Rect(10, 10, 100, 40), variant=variant, stroke_weight=6)

    button.draw(surface)

    assert surface.get_at((60, 10)) == expected_stroke
    assert surface.get_at((112, 30)) == expected_stroke
