from __future__ import annotations

import pygame

from ella_bot.core.events import TurnStatusChanged
from ella_bot.ui.pygame_gui.bot_sprite import draw_thought_bubble


_COPY = {
    "prompting": "Listen to ELLA",
    "preparing": "",
    "listening": "Listening…",
    "processing": "",
    "correct": "Correct!",
    "retry": "Try again",
    "no_input": "Try again",
    "exhausted": "Moving on…",
    "practice": "Your turn",
    "error": "Please wait…",
}


def status_text(status: TurnStatusChanged) -> str:
    return _COPY.get(status.phase, _COPY["preparing"])


def draw_turn_status(screen, rect, status: TurnStatusChanged, title_font) -> None:
    label = status_text(status)
    if label:
        draw_thought_bubble(screen, rect, pygame.time.get_ticks(), font=title_font, text=label)


def draw_turn_outcome(screen, indicator_rect, status: TurnStatusChanged, font) -> None:
    text = ""
    if status.phase == "exhausted":
        text = "Attempts completed"
    elif status.phase != "practice" and status.attempt_number is not None and status.attempt_limit:
        text = f"Attempt {status.attempt_number} of {status.attempt_limit}"
    if text:
        label = font.render(text, True, (87, 39, 108))
        screen.blit(label, label.get_rect(centerx=indicator_rect.centerx, top=indicator_rect.bottom + 8))
