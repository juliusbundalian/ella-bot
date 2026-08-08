from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from ella_bot.services.bgm_service import (
    play_menu_bgm,
    pause_bgm,
    unpause_bgm,
    stop_bgm,
    set_bgm_volume,
    is_bgm_playing,
)


def test_bgm_service_play_pause_stop():
    with patch("pygame.mixer.get_init", return_value=True), \
         patch("pygame.mixer.music.load") as mock_load, \
         patch("pygame.mixer.music.play") as mock_play, \
         patch("pygame.mixer.music.pause") as mock_pause, \
         patch("pygame.mixer.music.unpause") as mock_unpause, \
         patch("pygame.mixer.music.set_volume") as mock_set_vol, \
         patch("pygame.mixer.music.fadeout") as mock_fadeout, \
         patch("pygame.mixer.music.get_busy", return_value=False):
        
        # Test play menu BGM
        play_menu_bgm(volume_scale=1.0)
        assert mock_load.called
        assert mock_play.called
        assert mock_set_vol.called

        # Test pause BGM
        with patch("pygame.mixer.music.get_busy", return_value=True):
            pause_bgm()
            assert mock_pause.called

        # Test unpause BGM
        unpause_bgm()
        assert mock_unpause.called

        # Test set volume
        set_bgm_volume(0.8)
        assert mock_set_vol.called

        # Test stop BGM
        stop_bgm(fade_ms=300)
        assert mock_fadeout.called_with(300)


def test_is_bgm_playing_status():
    with patch("pygame.mixer.get_init", return_value=True), \
         patch("pygame.mixer.music.get_busy", return_value=True):
        # Stop / reset state
        stop_bgm(fade_ms=0)
        assert not is_bgm_playing()
