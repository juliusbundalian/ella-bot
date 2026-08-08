from unittest.mock import MagicMock


def _make_scene(kind="sublevel", passed=True, level="1c", tier=1):
    from ella_bot.ui.pygame_gui.scenes.results import ResultsScene
    app = MagicMock()
    result = MagicMock()
    result.passed = passed
    result.level = level
    result.tier = tier
    app.latest_result = result
    app.latest_result_kind = kind
    app.save_active_session.return_value = True
    app.start_new_session.return_value = True
    scene = object.__new__(ResultsScene)
    scene.app = app
    scene.pressed_button = None
    scene._show_menu_confirm = False
    scene._confirm_continue_button = None
    scene._confirm_restart_button = None
    scene.next_button = None
    scene.menu_button = None
    return scene


def test_next_advances_when_passed():
    scene = _make_scene(passed=True)
    scene._do_next()
    scene.app.session.advance_to_higher_stage.assert_called_once()
    scene.app.switch_scene.assert_called_with("reading_prompt")


def test_next_does_nothing_when_not_passed():
    scene = _make_scene(passed=False)
    scene._do_next()
    scene.app.session.advance_to_higher_stage.assert_not_called()
    scene.app.switch_scene.assert_not_called()


def test_retry_sublevel_resets_sublevel():
    scene = _make_scene(kind="sublevel", level="1c")
    scene._do_retry()
    scene.app.session.retry_sublevel.assert_called_once_with("1c")
    scene.app.evaluation.reset_sublevel.assert_called_once_with("1c")
    scene.app.switch_scene.assert_called_with("reading_prompt")


def test_retry_tier_resets_tier():
    scene = _make_scene(kind="tier", tier=2)
    scene._do_retry()
    scene.app.session.retry_tier.assert_called_once_with(2)
    scene.app.evaluation.reset_tier.assert_called_once_with(2)


def test_main_menu_switches_to_menu():
    scene = _make_scene(passed=True)
    scene._do_main_menu()
    scene.app.switch_scene.assert_called_once_with("main_menu")


def test_failed_transition_save_restores_pending_results_state():
    scene = _make_scene(passed=True)
    scene.app.save_active_session.return_value = False

    scene._do_next()

    scene.app.continue_saved_session.assert_called_once()
    scene.app.switch_scene.assert_not_called()
