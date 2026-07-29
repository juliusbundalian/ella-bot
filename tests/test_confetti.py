from unittest.mock import MagicMock
from ella_bot.ui.pygame_gui.components.confetti import ConfettiAnimation, ConfettiParticle


def test_confetti_particle_initialization():
    p = ConfettiParticle(1280, 720)
    assert 0 <= p.x <= 1280
    assert p.y < 0
    assert len(p.color) == 3


def test_confetti_animation_trigger_and_render():
    anim = ConfettiAnimation(count=30)
    assert not anim.active

    anim.trigger(duration=2.0)
    assert anim.active

    mock_pygame = MagicMock()
    mock_screen = MagicMock()
    mock_screen.get_size.return_value = (1280, 720)

    anim.update_and_render(mock_pygame, mock_screen)
    assert len(anim.particles) > 0
    mock_pygame.draw.polygon.assert_called()
