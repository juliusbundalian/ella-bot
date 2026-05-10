from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from src.ella_bot.utils.file_utils import resolve_asset_path


@dataclass
class GUIConfig:
    width: int = 1280
    height: int = 720
    fullscreen: bool = False
    fps: int = 60
    animation_fps: int = 10
    speaking_fps: int = 5
    loading_fps: int = 8
    processing_fps: int = 2
    title: str = "E.L.L.A. Reading Assistant"
    assets_dir: Path = resolve_asset_path("assets")

    background_top: tuple[int, int, int] = (236, 246, 255)
    background_bottom: tuple[int, int, int] = (212, 233, 246)
    card: tuple[int, int, int] = (250, 252, 255)
    text_primary: tuple[int, int, int] = (21, 37, 53)
    text_secondary: tuple[int, int, int] = (78, 101, 124)
    accent: tuple[int, int, int] = (21, 147, 122)
    warn: tuple[int, int, int] = (207, 138, 39)
    danger: tuple[int, int, int] = (188, 67, 78)
