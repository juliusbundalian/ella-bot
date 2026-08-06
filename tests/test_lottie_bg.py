from unittest.mock import MagicMock, patch

from ella_bot.ui.pygame_gui.lottie_bg import (
    LottieBackground,
    load_animated_background,
)


def test_unloaded_lottie_background_is_falsey():
    background = LottieBackground("missing-animation.lottie")

    assert background.is_loaded is False
    assert bool(background) is False


@patch("ella_bot.ui.pygame_gui.lottie_bg.LottieBackground")
@patch("ella_bot.ui.pygame_gui.lottie_bg.resolve_asset_path")
def test_loader_skips_an_unloadable_candidate(mock_resolve, mock_background):
    mock_resolve.side_effect = lambda candidate: MagicMock(
        exists=MagicMock(return_value=True),
        __str__=MagicMock(return_value=str(candidate)),
    )
    unloaded = MagicMock(is_loaded=False)
    loaded = MagicMock(is_loaded=True)
    mock_background.side_effect = (unloaded, loaded)

    result = load_animated_background(["broken.lottie", "working.lottie"])

    assert result is loaded
    assert mock_background.call_count == 2


@patch("ella_bot.ui.pygame_gui.video_bg.VideoBackground")
@patch("ella_bot.ui.pygame_gui.lottie_bg.LottieBackground")
@patch("ella_bot.ui.pygame_gui.lottie_bg.resolve_asset_path")
def test_loader_uses_video_when_lottie_cannot_load(
    mock_resolve,
    mock_background,
    mock_video_background,
):
    mock_resolve.side_effect = lambda candidate: MagicMock(
        exists=MagicMock(return_value=True),
        __str__=MagicMock(return_value=str(candidate)),
    )
    mock_background.return_value = MagicMock(is_loaded=False)
    video = MagicMock(is_loaded=True)
    mock_video_background.return_value = video

    result = load_animated_background(
        ["broken.lottie"],
        video_fallback="background.mp4",
    )

    assert result is video
