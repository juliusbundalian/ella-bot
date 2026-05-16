from pathlib import Path

def get_project_root() -> Path:
    """Returns the absolute path to the project root directory."""
    return Path(__file__).parent.parent.parent.parent

def resolve_asset_path(relative_path: str) -> Path:
    """Resolves a path relative to the project root."""
    return get_project_root() / relative_path

def resolve_config_path(relative_path: str) -> Path:
    """Resolves a path relative to the config directory."""
    return get_project_root() / "config" / relative_path

def resolve_model_path(relative_path: str) -> Path:
    """Resolves a path relative to the models directory."""
    return get_project_root() / "models" / Path(relative_path).name

def resolve_piper_path(relative_path: str) -> Path:
    """Resolves a path relative to the piper directory."""
    return get_project_root() / "piper" / Path(relative_path).name
