import queue
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ella_bot.core.events import TurnStatusChanged, SubLevelCompleted
from ella_bot.ui.pygame_gui.scenes.reading_prompt import ReadingPromptScene


@pytest.mark.parametrize(("phase", "title"), [
    ("prompting", "Listen to ELLA"), ("preparing", ""),
    ("listening", "Listening…"), ("processing", ""),
    ("correct", "Correct!"), ("retry", "Listen carefully"),
    ("no_input", "Listen carefully"), ("exhausted", "Moving on…"),
    ("practice", "Your turn"), ("error", "Please wait…"),
])
def test_status_uses_short_labels_and_hides_transient_phases(phase, title):
    from ella_bot.ui.pygame_gui.components.turn_status import status_text

    status = TurnStatusChanged(phase, "2a", 1, "cat", 2, 3)
    assert status_text(status) == title


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
        _prompt_font=lambda pygame_module: pygame.font.Font(None, 96),
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
def test_reading_text_remains_centered_above_bot(width, height, level):
    scene, pygame, inner = _scene(width, height, level)
    scene._turn_status = TurnStatusChanged(
        "processing", level, 1,
        "She respectfully stated a reasonable solution by sharing the consumer's rights and the store's policy.",
        2, 3,
    )
    font, prompt_rect = scene._prompt_layout(inner, pygame)

    assert font is not None
    assert prompt_rect.centerx == inner.centerx
    assert prompt_rect.bottom <= scene._bot_safe_bottom(inner)
    assert scene._wrapped_height(scene._display_prompt(), font, prompt_rect.width) <= prompt_rect.height


@pytest.mark.parametrize(("level", "expected_rect"), [
    ("1a", (72, 152, 880, 376)),
    ("2a", (72, 242, 880, 116)),
    ("3", (282, 242, 460, 116)),
    ("4", (272, 242, 480, 116)),
])
def test_short_prompt_preserves_original_layout(level, expected_rect):
    scene, pygame, inner = _scene(level=level)
    scene._turn_status = TurnStatusChanged("listening", level, 1, "community", 1, 3)
    font, text_rect = scene._prompt_layout(inner, pygame)
    assert font is not None
    assert tuple(text_rect) == expected_rect


def test_render_status_works_with_real_fonts():
    import pygame
    from ella_bot.ui.pygame_gui.components.turn_status import draw_turn_status

    pygame.font.init()
    surface = pygame.Surface((1024, 600))
    surface.fill((255, 255, 255))
    rect = pygame.Rect(32, 32, 960, 536)
    draw_turn_status(
        surface, rect, TurnStatusChanged("listening", "2a", 1, "cat", 1, 3),
        pygame.font.Font(None, 26),
    )
    assert surface.get_at((918, 216))[:3] != (255, 255, 255)
    assert surface.get_at((918, 268))[:3] == (127, 63, 151)
    assert surface.get_at((918, 190))[:3] == (255, 255, 255)


@pytest.mark.parametrize("phase", ["preparing", "processing"])
def test_transient_phases_do_not_draw_a_bubble(phase):
    from ella_bot.ui.pygame_gui.components.turn_status import draw_turn_status

    scene, pygame, inner = _scene()
    surface = pygame.Surface((1024, 600), pygame.SRCALPHA)
    status = TurnStatusChanged(phase, "2a", 1, "cat", 1, 3)
    draw_turn_status(surface, inner, status, pygame.font.Font(None, 26))
    assert surface.get_bounding_rect().width == 0


@pytest.mark.parametrize(("width", "height", "right_limit"), [
    (1000, 600, 725), (1024, 600, 744), (1024, 768, 744), (1280, 720, 933),
])
def test_level_three_phrases_fit_clear_of_ella_in_at_most_two_lines(width, height, right_limit):
    import json
    from pathlib import Path

    scene, pygame, inner = _scene(width, height, "3")
    scene.app._get_prompt_font = lambda size: pygame.font.Font("assets/fonts/Rencana.ttf", size)
    phrases = json.loads(Path("config/level_pools.json").read_text())["3"]
    for phrase in phrases:
        scene._turn_status = TurnStatusChanged("listening", "3", 1, phrase, 1, 3)
        font, text_rect = scene._prompt_layout(inner, pygame)
        assert font is not None, phrase
        assert text_rect.centerx == inner.centerx
        assert text_rect.right <= right_limit, phrase
        assert all(font.size(word)[0] <= text_rect.width for word in phrase.split()), phrase
        text_height = scene._wrapped_height(phrase, font, text_rect.width)
        assert text_height <= text_rect.height, phrase
        assert text_height <= 2 * font.get_height() + 14, phrase


def test_paused_scene_defers_results_navigation():
    scene, _, _ = _scene()
    scene.is_paused = True
    scene.app.switch_scene = MagicMock()
    pending = SubLevelCompleted("saved result", "sublevel")
    scene.app.event_queue.put(pending)
    scene._drain_event_queue()
    assert scene._pending_navigation == pending
    scene.app.switch_scene.assert_not_called()


@pytest.mark.parametrize("phase", [
    "prompting", "preparing", "listening", "processing", "correct",
    "retry", "no_input", "exhausted", "practice", "error",
])
@pytest.mark.parametrize(("width", "height"), [(1024, 600), (1024, 768), (1280, 720)])
def test_bubble_copy_fits_with_app_font(phase, width, height):
    from ella_bot.ui.pygame_gui.components.turn_status import status_text

    scene, pygame, inner = _scene(width, height)
    status = TurnStatusChanged(phase, "2a", 1, "cat", 2, 3)
    title = status_text(status)
    content_width = max(160, pygame.font.Font("assets/fonts/Rencana.ttf", 26).size(title)[0] + 40) - 36
    for text, size, available_height in ((title, 26, 52),):
        font = pygame.font.Font("assets/fonts/Rencana.ttf", size)
        assert all(font.size(word)[0] <= content_width for word in text.split())
        assert scene._wrapped_height(text, font, content_width, line_spacing=2) <= available_height


@pytest.mark.parametrize(("phase", "attempt", "limit", "text"), [
    ("listening", 1, 3, "Attempt 1 of 3"),
    ("retry", 2, 3, "Attempt 2 of 3"),
    ("processing", 3, 3, "Attempt 3 of 3"),
    ("exhausted", 3, 3, "Attempts completed"),
    ("preparing", None, None, ""),
    ("practice", 1, 3, ""),
])
def test_attempt_count_or_completion_is_drawn_below_level_indicator(phase, attempt, limit, text):
    from ella_bot.ui.pygame_gui.components.turn_status import draw_turn_outcome

    scene, pygame, _ = _scene()
    surface = pygame.Surface((1024, 600), pygame.SRCALPHA)
    indicator = pygame.Rect(370, 32, 284, 58)
    status = TurnStatusChanged(phase, "2a", 1, "cat", attempt, limit)
    font = pygame.font.Font(None, 26)
    draw_turn_outcome(surface, indicator, status, font)
    expected = pygame.Surface((1024, 600), pygame.SRCALPHA)
    if text:
        label = font.render(text, True, (87, 39, 108))
        expected.blit(label, label.get_rect(centerx=512, top=98))
    assert pygame.image.tobytes(surface, "RGBA") == pygame.image.tobytes(expected, "RGBA")
    painted = surface.get_bounding_rect()
    if text:
        assert painted.width > 0
        assert painted.top >= indicator.bottom + 8
        assert abs(painted.centerx - indicator.centerx) <= 2
    else:
        assert painted.width == 0
