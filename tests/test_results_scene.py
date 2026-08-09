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


def test_play_again_after_session_completion_starts_from_level_1a():
    scene = _make_scene(kind="session")
    scene.app.start_new_session.return_value = True

    scene._do_next()

    scene.app.start_new_session.assert_called_once_with("1a")
    scene.app.session.advance_to_higher_stage.assert_not_called()
    scene.app.save_active_session.assert_not_called()
    scene.app.switch_scene.assert_called_once_with("reading_prompt")
    scene.app.active_scene._start_attempt.assert_called_once()


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


def test_results_metrics_and_time_clear_bottom_buttons():
    import pygame

    from ella_bot.services.evaluation import TierResult
    from ella_bot.ui.pygame_gui.scenes.results import ResultsScene

    pygame.font.init()
    app = MagicMock()
    app.screen = pygame.Surface((1280, 720))
    app.font_title = pygame.font.SysFont(None, 64)
    app.font_body = pygame.font.SysFont(None, 30)
    app.font_small = pygame.font.SysFont(None, 22)
    app.font_button = pygame.font.SysFont(None, 48, bold=True)
    app._get_sys_font.side_effect = lambda size, bold=False: pygame.font.SysFont(
        None,
        size,
        bold=bold,
    )
    app.latest_result = TierResult(3, 0.86, "A", 28, 24, True)
    app.latest_result_kind = "tier"
    scene = ResultsScene(app)
    scene._lottie_bg = False
    scene._main_menu_svg = False
    scene._ribbon_img = False

    scene.render()

    assert scene.metrics_circle_y == scene.rating_letter_rect.centery + 16
    assert scene.score_circle_rect.size == (128, 128)
    assert scene.fluency_circle_rect.size == (128, 128)
    assert scene.ratings_badge_rect.top < scene.rating_letter_rect.bottom
    assert scene.time_badge_rect.bottom < scene.menu_button.top
    assert scene.time_badge_rect.bottom < scene.next_button.top


def test_session_completion_renders_in_results_ui_with_play_again(monkeypatch):
    import pygame

    import ella_bot.ui.pygame_gui.scenes.results as results_module
    from ella_bot.services.evaluation import CumulativeResult

    pygame.font.init()
    app = MagicMock()
    app.screen = pygame.Surface((1280, 720))
    app.font_title = pygame.font.SysFont(None, 64)
    app.font_body = pygame.font.SysFont(None, 30)
    app.font_small = pygame.font.SysFont(None, 22)
    app.font_button = pygame.font.SysFont(None, 48, bold=True)
    app._get_sys_font.side_effect = lambda size, bold=False: pygame.font.SysFont(
        None,
        size,
        bold=bold,
    )
    app.latest_result = CumulativeResult(0.86, "A", 28, 24, [], 180.0)
    app.latest_result_kind = "session"
    rendered_buttons = []

    class RecordingButton:
        def __init__(self, rect, *, label, variant="yellow", **kwargs):
            self.label = label
            self.variant = variant
            self.is_pressed = False

        def draw(self, screen):
            rendered_buttons.append((self.label, self.variant))

    monkeypatch.setattr(results_module, "Button", RecordingButton)
    scene = results_module.ResultsScene(app)
    scene._lottie_bg = False
    scene._main_menu_svg = False
    scene._ribbon_img = False

    scene.render()

    assert ("Play Again", "yellow") in rendered_buttons
