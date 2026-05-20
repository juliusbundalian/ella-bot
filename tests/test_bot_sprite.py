from ella_bot.ui.pygame_gui.bot_sprite import bot_state_for_app


def test_processing_maps_to_thinking():
    assert bot_state_for_app("processing") == "thinking"


def test_retry_maps_to_error():
    assert bot_state_for_app("retry") == "error"


def test_success_maps_to_idle():
    assert bot_state_for_app("success") == "idle"


def test_passthrough_states():
    for s in ("idle", "listening", "speaking", "warmup"):
        assert bot_state_for_app(s) == s


def test_unknown_defaults_to_idle():
    assert bot_state_for_app("banana") == "idle"
