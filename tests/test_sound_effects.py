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


def test_boost_sound_volume():
    import numpy as np
    import pygame
    from ella_bot.services.sound_effects import boost_sound_volume

    pygame.mixer.init()
    # Create a quiet int16 sine wave audio array (max amplitude ~10000 out of 32767)
    sample_rate = 22050
    t = np.linspace(0, 0.1, int(sample_rate * 0.1), False)
    sine = (np.sin(2 * np.pi * 440 * t) * 10000).astype(np.int16)
    stereo = np.column_stack((sine, sine))
    sound = pygame.sndarray.make_sound(stereo)

    boosted = boost_sound_volume(sound, gain_factor=2.5, target_peak_fraction=0.95)
    boosted_arr = pygame.sndarray.array(boosted)

    # Peak should be boosted significantly above original peak up to int16 max capacity
    orig_peak = np.max(np.abs(stereo))
    boosted_peak = np.max(np.abs(boosted_arr))
    assert boosted_peak > orig_peak
    assert boosted_peak <= 32767


def test_boost_sound_volume_fallback():
    from ella_bot.services.sound_effects import boost_sound_volume
    mock_sound = MagicMock()
    # Should safely return mock_sound without throwing an exception
    result = boost_sound_volume(mock_sound)
    assert result == mock_sound

