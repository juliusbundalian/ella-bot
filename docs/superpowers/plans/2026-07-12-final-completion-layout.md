# Final Completion Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render the final `All Levels Complete` result in the same visual hierarchy as ordinary level-completion results, with cumulative statistics only.

**Architecture:** Update `FinalEvaluationScene` to mirror the card, ribbon, rating, statistics, and button geometry already used by `ResultsScene`. Keep its existing action handlers and use the cumulative final result as the data source; no evaluation-service or navigation changes are required.

**Tech Stack:** Python 3.9+, pygame-ce, pytest.

## Global Constraints

- Preserve `Play Again` and `Main Menu` behavior exactly.
- Do not render per-tier result rows.
- Do not change scoring, result event routing, or session reset semantics.
- Use the existing completion-screen colors, asset banner, and button treatment.

---

### Task 1: Cover the final cumulative layout

**Files:**
- Modify: `tests/test_final_eval_scene.py`
- Modify: `src/ella_bot/ui/pygame_gui/scenes/final_eval.py:1-117`

**Interfaces:**
- Consumes: `app.latest_result.overall_rating`, `overall_fluency`, `first_try_correct`, and `items_total`.
- Produces: `FinalEvaluationScene.render()` that displays cumulative score and fluency without accessing `result.tiers`.

- [x] **Step 1: Write the failing render test**

```python
def test_render_uses_cumulative_summary_without_tier_rows(tmp_path, monkeypatch):
    import pygame
    from ella_bot.ui.pygame_gui.scenes.final_eval import FinalEvaluationScene

    pygame.init()
    app = _make_render_app(tmp_path)
    app.latest_result.tiers = None
    scene = FinalEvaluationScene(app)

    scene.render()

    assert scene.play_button is not None
    assert scene.menu_button is not None
```

Add `_make_render_app()` in the same test module with a `pygame.Surface`, real fonts, and a final result containing the cumulative fields. The test proves rendering does not depend on the removed tier rows.

- [x] **Step 2: Run the test to verify it fails**

Run: `./.venv/bin/python -m pytest -q tests/test_final_eval_scene.py::test_render_uses_cumulative_summary_without_tier_rows`

Expected: FAIL because the existing render loop iterates over `result.tiers`.

- [x] **Step 3: Implement the matching layout**

Replace the ad-hoc final layout in `FinalEvaluationScene.render()` with the same visual structure as `ResultsScene.render()`:

```python
rows = [
    ("Score:", f"{result.first_try_correct}/{result.items_total}"),
    ("Fluency:", f"{round(result.overall_fluency * 100)}%"),
]
```

Load `assets/img_ribbon_banner.png` lazily, render `ALL LEVELS` and `COMPLETE!` on the banner, use `overall_rating` in the outlined-letter treatment, render the two rows in the right column, and retain the current two button actions.

- [x] **Step 4: Run final-scene tests to verify the implementation**

Run: `./.venv/bin/python -m pytest -q tests/test_final_eval_scene.py`

Expected: PASS.

- [x] **Step 5: Run adjacent completion-scene tests**

Run: `./.venv/bin/python -m pytest -q tests/test_final_eval_scene.py tests/test_results_scene.py`

Expected: PASS.

- [ ] **Step 6: Commit the focused change**

```bash
git add src/ella_bot/ui/pygame_gui/scenes/final_eval.py tests/test_final_eval_scene.py
git commit -m "ui: align final completion layout with level results"
```
