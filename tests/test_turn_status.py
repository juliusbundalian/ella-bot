import queue
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ella_bot.core.events import TurnStatusChanged, SubLevelCompleted
from ella_bot.ui.pygame_gui.scenes.reading_prompt import ReadingPromptScene


@pytest.mark.parametrize(("phase", "title"), [
    ("prompting", "Listen to ELLA"), ("preparing", "Getting ready…"),
    ("listening", "Listening — Speak now"), ("processing", "Processing…"),
    ("correct", "Correct!"), ("retry", "Try again"),
    ("no_input", "I didn't hear you"), ("exhausted", "Attempts completed"),
    ("practice", "Your turn to practise"), ("error", "Please wait — ELLA needs help"),
])
def test_status_has_distinct_learner_instruction(phase, title):
    from ella_bot.ui.pygame_gui.components.turn_status import status_text

    status = TurnStatusChanged(phase, "2a", 1, "cat", 2, 3)
    main, instruction, counter = status_text(status)
    assert main == title
    assert instruction
    assert counter == ("" if phase == "practice" else "Attempt 2 of 3")
    if phase == "listening":
        assert instruction == "Say it once, then wait."


def _scene(width=1024, height=600, level="2a"):
    import pygame

    pygame.font.init()
    scene = object.__new__(ReadingPromptScene)
    scene._turn_status = TurnStatusChanged("correct", level, 1, "The previous item", 1, 3)
    scene.is_paused = False
    scene._pending_navigation = None
    scene.app = SimpleNamespace(
        event_queue=queue.Queue(), state="idle", message="", expected_sentence="The next item",
        session=SimpleNamespace(current_level=level), animator=MagicMock(),
        _get_prompt_font=lambda size: pygame.font.Font(None, size),
    )
    return scene, pygame, pygame.Rect(32, 32, width - 64, height - 64)


def test_scene_consumes_turn_status_and_preserves_item_snapshot():
    scene, _, _ = _scene()
    status = TurnStatusChanged("exhausted", "2b", 3, "previous word", 3, 3)
    scene.app.event_queue.put(status)
    scene._drain_event_queue()

    assert scene._turn_status == status
    assert scene._display_prompt() == "previous word"


@pytest.mark.parametrize(("width", "height"), [(1024, 600), (1024, 768), (1280, 720)])
@pytest.mark.parametrize("level", ["1a", "2a", "4"])
def test_status_and_prompt_do_not_overlap_bot_or_controls(width, height, level):
    scene, pygame, inner = _scene(width, height, level)
    scene._turn_status = TurnStatusChanged(
        "processing", level, 1,
        "She respectfully stated a reasonable solution by sharing the consumer's rights and the store's policy.",
        2, 3,
    )
    status_rect = scene._status_rect(inner, pygame)
    font, prompt_rect = scene._prompt_layout(inner, pygame)
    gear = pygame.Rect(inner.left + 40, height // 2 - 40, 80, 80)

    assert font is not None
    assert prompt_rect.top >= status_rect.bottom + 12
    assert prompt_rect.bottom <= scene._bot_safe_bottom(inner)
    assert not prompt_rect.colliderect(gear)
    assert scene._wrapped_height(scene._display_prompt(), font, prompt_rect.width) <= prompt_rect.height
    assert status_rect.bottom < height - 114


def test_render_status_works_with_real_fonts():
    import pygame
    from ella_bot.ui.pygame_gui.components.turn_status import draw_turn_status

    pygame.font.init()
    surface = pygame.Surface((1024, 600))
    surface.fill((255, 255, 255))
    rect = pygame.Rect(136, 106, 752, 94)
    draw_turn_status(
        surface, rect, TurnStatusChanged("listening", "2a", 1, "cat", 1, 3),
        pygame.font.Font(None, 32), pygame.font.Font(None, 24),
    )
    assert surface.get_at(rect.center)[:3] != (255, 255, 255)


def test_paused_scene_defers_results_navigation():
    scene, _, _ = _scene()
    scene.is_paused = True
    scene.app.switch_scene = MagicMock()
    pending = SubLevelCompleted("saved result", "sublevel")
    scene.app.event_queue.put(pending)
    scene._drain_event_queue()
    assert scene._pending_navigation == pending
    scene.app.switch_scene.assert_not_called()
