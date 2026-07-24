from unittest.mock import MagicMock


def _make_render_app(tmp_path):
    import pygame

    app = MagicMock()
    app.screen = pygame.Surface((1024, 768))
    app.font_body = pygame.font.SysFont(None, 30)
    app.font_title = pygame.font.SysFont(None, 64)
    app._get_sys_font.side_effect = lambda size, bold=False: pygame.font.SysFont(
        None, size, bold=bold
    )
    app.latest_result = MagicMock(
        overall_rating="A",
        overall_fluency=0.86,
        first_try_correct=24,
        items_total=28,
    )
    return app


def _make_scene(tmp_path):
    from ella_bot.ui.pygame_gui.scenes.final_eval import FinalEvaluationScene
    from ella_bot.services.evaluation import EvaluationService
    app = MagicMock()
    app.evaluation = EvaluationService(log_path=tmp_path / "s.jsonl", pass_bar=0.70)
    app.latest_result = MagicMock()
    scene = object.__new__(FinalEvaluationScene)
    scene.app = app
    scene.pressed_button = None
    return scene


def test_play_again_resets_and_restarts(tmp_path):
    scene = _make_scene(tmp_path)
    old_evaluation = scene.app.evaluation
    scene._do_play_again()
    scene.app.session.reset_to_start.assert_called_once()
    assert scene.app.evaluation is not old_evaluation  # fresh EvaluationService created
    scene.app.switch_scene.assert_called_with("reading_prompt")


def test_main_menu_switches_scene(tmp_path):
    scene = _make_scene(tmp_path)
    scene._do_main_menu()
    scene.app.switch_scene.assert_called_once_with("main_menu")


def test_render_uses_cumulative_summary_without_tier_rows(tmp_path, monkeypatch):
    import pygame
    from ella_bot.ui.pygame_gui.scenes.final_eval import FinalEvaluationScene

    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    pygame.init()
    app = _make_render_app(tmp_path)
    app.latest_result.tiers = None
    scene = FinalEvaluationScene(app)

    scene.render()

    assert scene.play_button is not None
    assert scene.menu_button is not None
