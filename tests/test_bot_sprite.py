from ella_bot.ui.pygame_gui.bot_sprite import bot_state_for_app


def test_processing_maps_to_thinking():
    assert bot_state_for_app("processing") == "thinking"


def test_retry_maps_to_idle():
    assert bot_state_for_app("retry") == "idle"


def test_success_maps_to_idle():
    assert bot_state_for_app("success") == "idle"


def test_passthrough_states():
    for s in ("idle", "listening", "speaking", "warmup"):
        assert bot_state_for_app(s) == s


def test_unknown_defaults_to_idle():
    assert bot_state_for_app("banana") == "idle"


def test_scaled_frames_are_cached_on_repeated_calls():
    from unittest.mock import MagicMock, patch
    from ella_bot.ui.pygame_gui.bot_sprite import BotSprite

    bot = object.__new__(BotSprite)
    fake_frame = MagicMock()
    fake_frame.get_width.return_value = 100
    fake_frame.get_height.return_value = 100
    fake_scaled = MagicMock()

    bot.frames = {"idle": [fake_frame]}
    bot.state = "idle"
    bot._scaled_cache = {}
    bot._cache_target_size = None

    with patch("ella_bot.ui.pygame_gui.bot_sprite.pygame.transform.smoothscale", return_value=fake_scaled) as mock_scale:
        bot._get_scaled_frames(200, 200)
        bot._get_scaled_frames(200, 200)

    assert mock_scale.call_count == 1


def test_scaled_cache_clears_when_target_size_changes():
    from unittest.mock import MagicMock, patch
    from ella_bot.ui.pygame_gui.bot_sprite import BotSprite

    bot = object.__new__(BotSprite)
    fake_frame = MagicMock()
    fake_frame.get_width.return_value = 100
    fake_frame.get_height.return_value = 100
    fake_scaled = MagicMock()

    bot.frames = {"idle": [fake_frame]}
    bot.state = "idle"
    bot._scaled_cache = {}
    bot._cache_target_size = None

    with patch("ella_bot.ui.pygame_gui.bot_sprite.pygame.transform.smoothscale", return_value=fake_scaled) as mock_scale:
        bot._get_scaled_frames(200, 200)
        bot._get_scaled_frames(300, 300)

    assert mock_scale.call_count == 2
