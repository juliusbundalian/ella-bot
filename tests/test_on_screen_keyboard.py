from __future__ import annotations

import pygame

from ella_bot.ui.pygame_gui.components.on_screen_keyboard import (
    KeyboardAction,
    OnScreenKeyboard,
)


def _keyboard():
    pygame.font.init()
    return OnScreenKeyboard(pygame.font.SysFont(None, 28))


def _draw(keyboard, rect=pygame.Rect(40, 30, 1000, 260)):
    screen = pygame.Surface((1280, 720))
    keyboard.draw(screen, rect)
    return screen


def test_keyboard_draws_all_keys_inside_supplied_rect():
    keyboard = _keyboard()
    bounds = pygame.Rect(40, 30, 1000, 260)

    _draw(keyboard, bounds)

    assert set("qwertyuiopasdfghjklzxcvbnm") <= set(keyboard.key_rects)
    assert {"shift", "space", "apostrophe", "hyphen", "backspace"} <= set(
        keyboard.key_rects
    )
    assert all(bounds.contains(rect) for rect in keyboard.key_rects.values())


def test_press_and_release_on_letter_emits_text_action():
    keyboard = _keyboard()
    _draw(keyboard)
    point = keyboard.key_rects["q"].center

    assert keyboard.handle_mouse_down(point) is True
    assert keyboard.handle_mouse_up(point) == KeyboardAction("text", "q")


def test_release_outside_pressed_key_cancels_action():
    keyboard = _keyboard()
    _draw(keyboard)

    keyboard.handle_mouse_down(keyboard.key_rects["q"].center)

    assert keyboard.handle_mouse_up(keyboard.key_rects["w"].center) is None


def _tap(keyboard, key):
    point = keyboard.key_rects[key].center
    assert keyboard.handle_mouse_down(point) is True
    return keyboard.handle_mouse_up(point)


def test_shift_capitalizes_only_the_next_letter():
    keyboard = _keyboard()
    _draw(keyboard)

    assert _tap(keyboard, "shift") == KeyboardAction("shift")
    assert keyboard.uppercase is True
    assert _tap(keyboard, "q") == KeyboardAction("text", "Q")
    assert keyboard.uppercase is False
    assert _tap(keyboard, "w") == KeyboardAction("text", "w")

    keyboard.reset()

    assert keyboard.uppercase is False


def test_special_keys_emit_semantic_actions():
    keyboard = _keyboard()
    _draw(keyboard)

    assert _tap(keyboard, "space") == KeyboardAction("text", " ")
    assert _tap(keyboard, "apostrophe") == KeyboardAction("text", "'")
    assert _tap(keyboard, "hyphen") == KeyboardAction("text", "-")
    assert _tap(keyboard, "backspace") == KeyboardAction("backspace")


def test_cancel_press_prevents_a_later_release_from_activating():
    keyboard = _keyboard()
    _draw(keyboard)
    point = keyboard.key_rects["q"].center
    keyboard.handle_mouse_down(point)

    keyboard.cancel_press()

    assert keyboard.handle_mouse_up(point) is None
