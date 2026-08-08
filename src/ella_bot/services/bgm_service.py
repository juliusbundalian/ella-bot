from __future__ import annotations

from pathlib import Path
from typing import Optional

from ella_bot.config.app_config import load_settings
from ella_bot.utils.file_utils import resolve_asset_path
from ella_bot.utils.logging import get_logger

logger = get_logger(__name__)

_DEFAULT_BGM_FILE = "assets/BG/bg_Enthusiasm.mp3"
_BASE_BGM_VOLUME = 0.35  # Comfortably balanced background volume scale

_current_track: Optional[Path] = None
_is_paused: bool = False


def _get_configured_volume_scale() -> float:
    """Retrieve master volume scale from settings (0.0 to 1.0)."""
    try:
        settings = load_settings()
        return float(settings.get("volume", 1.0))
    except Exception as exc:
        logger.debug("Could not load volume settings for BGM: %s", exc)
        return 1.0


def play_menu_bgm(
    filename_or_path: str | Path = _DEFAULT_BGM_FILE,
    volume_scale: Optional[float] = None,
    fade_ms: int = 500,
) -> None:
    """Play background music asynchronously in a continuous loop.

    If the requested track is already playing and paused, it unpauses smoothly.
    If the requested track is already playing actively, volume is updated without restarting.
    """
    global _current_track, _is_paused

    try:
        import pygame

        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init()
            except Exception as exc:
                logger.warning("Could not initialize pygame mixer for BGM: %s", exc)
                return

        track_path = resolve_asset_path(filename_or_path)
        if not track_path.exists():
            logger.warning("BGM file not found: %s", track_path)
            return

        vol_scale = (
            volume_scale if volume_scale is not None else _get_configured_volume_scale()
        )
        effective_vol = max(0.0, min(1.0, _BASE_BGM_VOLUME * vol_scale))

        if _current_track == track_path and pygame.mixer.music.get_busy():
            pygame.mixer.music.set_volume(effective_vol)
            if _is_paused:
                pygame.mixer.music.unpause()
                _is_paused = False
            return

        # Load and play new track with fade-in
        pygame.mixer.music.load(str(track_path))
        pygame.mixer.music.set_volume(effective_vol)
        pygame.mixer.music.play(loops=-1, fade_ms=fade_ms)
        _current_track = track_path
        _is_paused = False
        logger.info("BGM playing: %s (vol=%.2f)", track_path.name, effective_vol)
    except Exception as exc:
        logger.warning("Failed to play BGM %s: %s", filename_or_path, exc)


def pause_bgm() -> None:
    """Pause background music (e.g. during active reading levels)."""
    global _is_paused
    try:
        import pygame

        if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
            pygame.mixer.music.pause()
            _is_paused = True
    except Exception as exc:
        logger.debug("Error pausing BGM: %s", exc)


def unpause_bgm() -> None:
    """Unpause background music."""
    global _is_paused
    try:
        import pygame

        if pygame.mixer.get_init() and _is_paused:
            pygame.mixer.music.unpause()
            _is_paused = False
    except Exception as exc:
        logger.debug("Error unpausing BGM: %s", exc)


def stop_bgm(fade_ms: int = 500) -> None:
    """Stop background music with optional fadeout."""
    global _current_track, _is_paused
    try:
        import pygame

        if pygame.mixer.get_init():
            if fade_ms > 0:
                pygame.mixer.music.fadeout(fade_ms)
            else:
                pygame.mixer.music.stop()
        _current_track = None
        _is_paused = False
    except Exception as exc:
        logger.debug("Error stopping BGM: %s", exc)


def set_bgm_volume(volume_scale: float) -> None:
    """Dynamically set BGM volume based on master volume scale (0.0 to 1.0)."""
    try:
        import pygame

        if pygame.mixer.get_init():
            effective_vol = max(0.0, min(1.0, _BASE_BGM_VOLUME * volume_scale))
            pygame.mixer.music.set_volume(effective_vol)
    except Exception as exc:
        logger.debug("Error setting BGM volume: %s", exc)


def is_bgm_playing() -> bool:
    """Return True if BGM is actively playing and not paused."""
    try:
        import pygame

        return (
            pygame.mixer.get_init()
            and pygame.mixer.music.get_busy()
            and not _is_paused
            and _current_track is not None
        )
    except Exception:
        return False
