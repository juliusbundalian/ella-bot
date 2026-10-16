from __future__ import annotations

import math

import pygame

from ella_bot.core.events import TurnStatusChanged


_COPY = {
    "prompting": ("Listen to ELLA", 'Wait until you see “Speak now.”'),
    "preparing": ("Getting ready…", "Please wait."),
    "listening": ("Listening — Speak now", "Say it once, then wait."),
    "processing": ("Processing…", "Please wait while ELLA checks your answer."),
    "correct": ("Correct!", "Moving to the next item."),
    "retry": ("Try again", 'Wait for “Speak now” before trying again.'),
    "no_input": ("I didn't hear you", 'Wait for “Speak now,” then say it once.'),
    "exhausted": ("Attempts completed", "Let's try the next item."),
    "practice": ("Your turn to practise", "Say the sound. Use Replay to hear it again, then Next."),
    "error": ("Please wait — ELLA needs help", "Ask the researcher for help."),
}


def status_text(status: TurnStatusChanged) -> tuple[str, str, str]:
    title, instruction = _COPY.get(status.phase, _COPY["preparing"])
    counter = ""
    if status.phase != "practice" and status.attempt_number is not None and status.attempt_limit:
        counter = f"Attempt {status.attempt_number} of {status.attempt_limit}"
    return title, instruction, counter


def _fit_font(font, text: str, width: int):
    size = font.get_height()
    while font.size(text)[0] > width and size > 16:
        size -= 1
        font = pygame.font.Font(None, size)
    return font


def _draw_icon(screen, center, phase: str, color) -> None:
    center_x, center_y = center
    if phase == "listening":
        pygame.draw.rect(screen, color, (center_x - 6, center_y - 16, 12, 23), border_radius=6)
        pygame.draw.arc(screen, color, (center_x - 12, center_y - 13, 24, 27), math.pi, 2 * math.pi, 3)
        pygame.draw.line(screen, color, (center_x, center_y + 12), (center_x, center_y + 18), 3)
        pygame.draw.line(screen, color, (center_x - 7, center_y + 18), (center_x + 7, center_y + 18), 3)
    elif phase == "correct":
        pygame.draw.lines(screen, color, False, [(center_x - 14, center_y), (center_x - 4, center_y + 10), (center_x + 16, center_y - 12)], 5)
    elif phase in {"retry", "no_input"}:
        pygame.draw.arc(screen, color, (center_x - 15, center_y - 15, 30, 30), 0, 1.7 * math.pi, 4)
        pygame.draw.polygon(screen, color, [(center_x + 16, center_y - 3), (center_x + 6, center_y - 3), (center_x + 16, center_y + 8)])
    elif phase == "exhausted":
        pygame.draw.line(screen, color, (center_x - 16, center_y), (center_x + 12, center_y), 4)
        pygame.draw.lines(screen, color, False, [(center_x + 2, center_y - 11), (center_x + 15, center_y), (center_x + 2, center_y + 11)], 4)
    elif phase == "error":
        pygame.draw.line(screen, color, (center_x, center_y - 15), (center_x, center_y + 5), 5)
        pygame.draw.circle(screen, color, (center_x, center_y + 14), 3)
    elif phase in {"preparing", "processing"}:
        active = (pygame.time.get_ticks() // 350) % 3
        for index in range(3):
            pygame.draw.circle(screen, color, (center_x - 14 + index * 14, center_y), 5 if index == active else 3)
    else:
        pygame.draw.rect(screen, color, (center_x - 16, center_y - 7, 9, 14), border_radius=2)
        pygame.draw.polygon(screen, color, [(center_x - 7, center_y - 7), (center_x + 5, center_y - 15), (center_x + 5, center_y + 15), (center_x - 7, center_y + 7)])
        pygame.draw.arc(screen, color, (center_x - 1, center_y - 12, 22, 24), -math.pi / 3, math.pi / 3, 3)


def draw_turn_status(screen, rect, status: TurnStatusChanged, title_font, body_font) -> None:
    color = {
        "listening": (20, 115, 105), "processing": (44, 90, 150),
        "correct": (37, 120, 62), "retry": (151, 99, 15),
        "no_input": (151, 99, 15), "error": (157, 49, 59),
    }.get(status.phase, (112, 57, 137))
    pygame.draw.rect(screen, (255, 250, 253), rect, border_radius=20)
    pygame.draw.rect(screen, color, rect, width=3, border_radius=20)
    _draw_icon(screen, (rect.left + 36, rect.centery), status.phase, color)
    title, instruction, counter = status_text(status)
    counter_font = _fit_font(body_font, counter, 150)
    counter_surface = counter_font.render(counter, True, color)
    counter_width = counter_surface.get_width() + 20 if counter else 0
    content_width = rect.width - 98
    title_font = _fit_font(title_font, title, content_width - counter_width)
    body_font = _fit_font(body_font, instruction, content_width)
    screen.blit(title_font.render(title, True, color), (rect.left + 74, rect.top + 13))
    screen.blit(body_font.render(instruction, True, (56, 38, 65)), (rect.left + 74, rect.top + 54))
    if counter:
        screen.blit(counter_surface, counter_surface.get_rect(right=rect.right - 20, top=rect.top + 17))
