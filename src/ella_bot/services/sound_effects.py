from __future__ import annotations

"""Sound effect player for ELLA application."""

from ella_bot.utils.file_utils import resolve_asset_path
from ella_bot.utils.logging import get_logger

logger = get_logger(__name__)


def play_sound_effect(filename: str) -> None:
    """Play a sound effect file from assets/audio/sfx/ asynchronously via Pygame mixer."""
    try:
        import pygame
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init()
            except Exception:
                return
        sfx_path = resolve_asset_path(f"assets/audio/sfx/{filename}")
        if not sfx_path.exists():
            logger.warning("Sound effect file not found: %s", sfx_path)
            return
        sound = pygame.mixer.Sound(str(sfx_path))
        sound.play()
    except Exception as exc:
        logger.warning("Could not play sound effect %s: %s", filename, exc)


def play_level_sound(passed: bool) -> None:
    """Play pass or fail sound effect when finishing a level.

    Pass: Confetti popping and kids cheering (FNAF level success cheer).
    Fail: Encouraging gentle chime so the user is not discouraged.
    """
    sfx_file = "level_pass.wav" if passed else "level_fail.wav"
    play_sound_effect(sfx_file)


def play_button_click() -> None:
    """Play crisp button click sound effect."""
    play_sound_effect("button_click.wav")

