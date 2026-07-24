from unittest.mock import MagicMock

from ella_bot.services.session_checkpoint import SavedSessionSummary
from ella_bot.ui.pygame_gui.scenes.main_menu import MainMenuScene


def _scene():
    app = MagicMock()
    return MainMenuScene(app)


def test_start_without_checkpoint_opens_level_selection():
    scene = _scene()
    scene.app.saved_session_summary.return_value = None

    scene._do_start()

    scene.app.switch_scene.assert_called_once_with("level_selection")
    assert scene.show_resume_prompt is False


def test_start_with_checkpoint_opens_resume_prompt():
    scene = _scene()
    summary = SavedSessionSummary("2c", 4, "2026-07-24T10:00:00+08:00", "reading")
    scene.app.saved_session_summary.return_value = summary

    scene._do_start()

    assert scene.show_resume_prompt is True
    assert scene.resume_summary == summary
    scene.app.switch_scene.assert_not_called()


def test_continue_reading_checkpoint_starts_saved_attempt():
    scene = _scene()
    scene.app.continue_saved_session.return_value = "reading"

    scene._do_continue()

    scene.app.switch_scene.assert_called_once_with("reading_prompt")
    scene.app.active_scene._start_attempt.assert_called_once()


def test_continue_results_checkpoint_opens_results_without_attempt():
    scene = _scene()
    scene.app.continue_saved_session.return_value = "results"

    scene._do_continue()

    scene.app.switch_scene.assert_called_once_with("results")
    scene.app.active_scene._start_attempt.assert_not_called()


def test_new_session_choice_does_not_clear_checkpoint():
    scene = _scene()

    scene._do_new_session()

    scene.app.clear_active_session.assert_not_called()
    scene.app.switch_scene.assert_called_once_with("level_selection")


def test_entering_main_menu_does_not_reset_progress():
    scene = _scene()
    scene.on_enter()
    scene.app.session.reset_current_level.assert_not_called()
