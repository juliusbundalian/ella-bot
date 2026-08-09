from unittest.mock import MagicMock

import pygame
import pytest

from ella_bot.ui.pygame_gui.components.pause_modal import PauseModal


@pytest.mark.parametrize("confirm_action", ["restart", "main_menu"])
def test_confirmation_places_violet_cancel_action_left(
    monkeypatch,
    confirm_action,
):
    import ella_bot.ui.pygame_gui.components.pause_modal as pause_module

    pygame.font.init()
    app = MagicMock()
    app.font_title = pygame.font.SysFont(None, 64)
    app.font_button = pygame.font.SysFont(None, 42)
    rendered_buttons = []

    class RecordingButton:
        def __init__(self, rect, *, label, variant="yellow", **kwargs):
            self.rect = pygame.Rect(rect)
            self.label = label
            self.variant = variant
            self.is_pressed = False

        def draw(self, screen):
            rendered_buttons.append((self.label, self.variant, self.rect))

    monkeypatch.setattr(pause_module, "Button", RecordingButton)
    modal = PauseModal(app)
    modal.confirm_action = confirm_action
    screen = pygame.Surface((1280, 720))

    modal._draw_confirm(screen, pygame.Rect(280, 98, 720, 524))

    buttons = {label: (variant, rect) for label, variant, rect in rendered_buttons}
    assert buttons["No"][0] == "violet"
    assert buttons["No"][1].left < buttons["Yes"][1].left
