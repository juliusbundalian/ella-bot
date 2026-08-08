from unittest.mock import MagicMock, patch
from ella_bot.services.sound_effects import (
    play_button_click,
    play_level_sound,
    play_sound_effect,
)


@patch("pygame.mixer.Sound")
@patch("pygame.mixer.get_init", return_value=True)
def test_play_sound_effect(mock_get_init, mock_sound):
    play_sound_effect("level_pass.wav")
    mock_sound.assert_called_once()
    mock_sound.return_value.play.assert_called_once()


@patch("ella_bot.services.sound_effects.play_sound_effect")
def test_play_level_sound_pass(mock_play):
    play_level_sound(True)
    mock_play.assert_called_once_with("level_pass.wav")


@patch("ella_bot.services.sound_effects.play_sound_effect")
def test_play_level_sound_fail(mock_play):
    play_level_sound(False)
    mock_play.assert_called_once_with("level_fail.wav")


@patch("ella_bot.services.sound_effects.play_sound_effect")
def test_play_button_click(mock_play):
    play_button_click()
    mock_play.assert_called_once_with("button_click.wav")
