from unittest.mock import MagicMock, patch


def _make_scene(volume_level=3, listen_seconds=7):
    """Build a SettingsScene without touching pygame."""
    from ella_bot.ui.pygame_gui.scenes.settings import SettingsScene
    app = MagicMock()
    app.asr = MagicMock()
    app.asr.listen_seconds = listen_seconds
    app.tts = MagicMock()
    scene = object.__new__(SettingsScene)
    scene.app = app
    scene.volume_level = volume_level
    scene.listen_seconds = listen_seconds
    scene.pressed_button = None
    scene.show_reset_confirm = False
    return scene


def test_volume_tap_plus_increments():
    scene = _make_scene(volume_level=3)
    with patch("ella_bot.config.app_config.save_setting"):
        scene._tap_volume(1)
    assert scene.volume_level == 4


def test_volume_tap_minus_decrements():
    scene = _make_scene(volume_level=3)
    with patch("ella_bot.config.app_config.save_setting"):
        scene._tap_volume(-1)
    assert scene.volume_level == 2


def test_volume_clamps_at_min():
    scene = _make_scene(volume_level=1)
    with patch("ella_bot.config.app_config.save_setting"):
        scene._tap_volume(-1)
    assert scene.volume_level == 1


def test_volume_clamps_at_max():
    scene = _make_scene(volume_level=6)
    with patch("ella_bot.config.app_config.save_setting"):
        scene._tap_volume(1)
    assert scene.volume_level == 6


def test_volume_tap_calls_set_volume():
    scene = _make_scene(volume_level=3)
    with patch("ella_bot.config.app_config.save_setting"):
        scene._tap_volume(1)
    scene.app.tts.set_volume.assert_called_once_with(4 / 6)


def test_listen_tap_plus_increments():
    scene = _make_scene(listen_seconds=7)
    with patch("ella_bot.config.app_config.save_setting"):
        scene._tap_listen(1)
    assert scene.listen_seconds == 8


def test_listen_tap_minus_decrements():
    scene = _make_scene(listen_seconds=7)
    with patch("ella_bot.config.app_config.save_setting"):
        scene._tap_listen(-1)
    assert scene.listen_seconds == 6


def test_listen_clamps_at_min():
    scene = _make_scene(listen_seconds=5)
    with patch("ella_bot.config.app_config.save_setting"):
        scene._tap_listen(-1)
    assert scene.listen_seconds == 5


def test_listen_clamps_at_max():
    scene = _make_scene(listen_seconds=10)
    with patch("ella_bot.config.app_config.save_setting"):
        scene._tap_listen(1)
    assert scene.listen_seconds == 10


def test_listen_tap_updates_asr():
    scene = _make_scene(listen_seconds=7)
    with patch("ella_bot.config.app_config.save_setting"):
        scene._tap_listen(1)
    assert scene.app.asr.listen_seconds == 8
