from __future__ import annotations

class BaseScene:
    """Base class for all GUI scenes."""
    def __init__(self, app):
        """app is a reference to the main SceneManager (EllaGUIApp)"""
        self.app = app

    def on_enter(self) -> None:
        """Called when the scene becomes active."""
        pass

    def on_exit(self) -> None:
        """Called when the scene is no longer active."""
        pass

    def handle_event(self, event) -> None:
        """Handle a pygame event."""
        pass

    def update(self, now_ms: int) -> None:
        """Update scene logic."""
        pass

    def render(self) -> None:
        """Render the scene to self.app.screen."""
        pass
