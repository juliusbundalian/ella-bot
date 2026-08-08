# Responsive Reading Prompt Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Keep long reading prompts visible by shifting them upward and reducing their font size when necessary.

**Architecture:** Add a focused layout helper to ReadingPromptScene that measures wrapped line height at progressively smaller font sizes, then calculates a centered prompt rectangle above Ella's safe lower boundary. The existing draw_wrapped_text call consumes that calculated result; the bot remains unchanged.

**Tech Stack:** Python 3.9+, pygame-ce, pytest.

## Global Constraints

- Keep prompt text horizontally centered.
- Do not place text in a separate upper-left column.
- Do not change the Ella sprite's size or placement.
- Short prompts must preserve their current font and placement behavior.
- Long prompts must remain clear of Ella and within the reading prompt frame.

---

### Task 1: Add responsive prompt sizing and placement

**Files:**
- Modify: src/ella_bot/ui/pygame_gui/scenes/reading_prompt.py:173-260
- Modify: tests/test_reading_prompt_auto_continue.py

**Interfaces:**
- Consumes: self.app.expected_sentence, inner_rect, and the existing prompt fonts.
- Produces: ReadingPromptScene._prompt_layout(inner_rect, pygame_module) returning (font, pygame.Rect) for draw_wrapped_text.

- [ ] **Step 1: Write the failing layout test**

~~~python
def test_long_prompt_uses_smaller_font_and_higher_text_area():
    scene, pygame = _make_scene_for_layout(
        "she stepped in and respectfully stated a reasonable solution by "
        "sharing the consumer's rights and the store's policy."
    )
    inner_rect = pygame.Rect(32, 32, 1216, 656)

    font, text_rect = scene._prompt_layout(inner_rect, pygame)

    assert font.get_height() < scene.app.font_prompt_small.get_height()
    assert text_rect.top < inner_rect.top + 120
    assert text_rect.bottom <= inner_rect.bottom - int(inner_rect.height * 0.28)
~~~

The fixture must supply a real pygame font family and an expected_sentence property. This test demonstrates the current scene has no responsive layout helper before production changes.

- [ ] **Step 2: Run the focused test and verify it fails**

Run: ./.venv/bin/python -m pytest -q tests/test_reading_prompt_auto_continue.py::test_long_prompt_uses_smaller_font_and_higher_text_area

Expected: FAIL because _prompt_layout does not exist.

- [ ] **Step 3: Implement the layout helper and use it in rendering**

~~~python
def _prompt_layout(self, inner_rect, pygame_module):
    text = self.app.expected_sentence
    word_count = len(text.split())
    if word_count <= 6:
        return self.app._prompt_font(pygame_module), pygame_module.Rect(
            inner_rect.left + 40,
            inner_rect.top + 120,
            inner_rect.width - 80,
            inner_rect.height - 160,
        )

    safe_bottom = inner_rect.bottom - int(inner_rect.height * 0.28)
    text_rect = pygame_module.Rect(
        inner_rect.left + 40,
        inner_rect.top + 88,
        inner_rect.width - 80,
        safe_bottom - (inner_rect.top + 88),
    )
    font_size = 82
    while font_size >= 52:
        font = self.app._get_sys_font(font_size)
        if self._wrapped_height(text, font, text_rect.width, line_spacing=14) <= text_rect.height:
            return font, text_rect
        font_size -= 4
    return self.app._get_sys_font(52), text_rect
~~~

Replace the existing fixed prompt_font and prompt_text_rect construction in render() with the helper result. Adjust the threshold or vertical offset only as required for the test and actual wrapped-height measurement; keep the text centered through draw_wrapped_text(..., align="center", valign="center").

- [ ] **Step 4: Run the focused test and verify it passes**

Run: ./.venv/bin/python -m pytest -q tests/test_reading_prompt_auto_continue.py::test_long_prompt_uses_smaller_font_and_higher_text_area

Expected: PASS.

- [ ] **Step 5: Run relevant scene tests**

Run: ./.venv/bin/python -m pytest -q tests/test_reading_prompt_auto_continue.py tests/test_gui_e2e.py

Expected: PASS.

- [ ] **Step 6: Commit the focused change**

~~~bash
git add src/ella_bot/ui/pygame_gui/scenes/reading_prompt.py tests/test_reading_prompt_auto_continue.py
git commit -m "ui: fit long reading prompts above bot"
~~~
