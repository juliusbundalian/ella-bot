# Profiles Carousel Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Match the Profiles page container to the standalone Options page and replace its five-card grid with a touch-friendly, two-profile carousel and consistent card actions.

**Architecture:** Keep pagination and input state inside `ProfilesScene`. Add small pure geometry/pagination helpers, render only the current two-profile slice, and continue using the shared `Button` component for fixed actions and profile-management controls.

**Tech Stack:** Python 3, pygame-ce, pytest

## Global Constraints

- The Profiles container is exactly `720px` wide, horizontally centered, and uses a `140px` radius while retaining its existing height and vertical position.
- Show exactly two existing profiles per carousel page; do not put Create Profile in the carousel.
- Open on the active profile's page, disable arrows at the ends, do not wrap, and keep page indicators visual-only.
- Rename spans the top action row; Reset and Delete use equal halves below it.
- Management buttons use a `40px` height and one shared font size; labels are exactly `Rename`, `Reset`, and `Delete`.
- Keep the five-profile limit, persistence, modals, confirmation wording, touchscreen keyboard, and reading-session behavior unchanged.
- Do not modify unrelated profile/settings data already present in the worktree.

---

### Task 1: Container Geometry and Pagination Model

**Files:**
- Modify: `src/ella_bot/ui/pygame_gui/scenes/profiles.py:17-74,316-371`
- Modify: `tests/test_profiles_scene.py:1-45`

**Interfaces:**
- Consumes: `app.profiles() -> tuple[Profile, ...]` and `app.active_profile() -> Profile | None`.
- Produces: `_PROFILE_PAGE_SIZE`, `_PROFILE_CONTAINER_WIDTH`, `_PROFILE_CONTAINER_RADIUS`, `ProfilesScene.carousel_page`, `_get_container_rect(width, height)`, `_page_count(profile_count)`, `_clamp_carousel_page(profiles)`, `_visible_profiles(profiles)`, and `_show_active_profile_page(profiles, active_profile_id)`.

- [ ] **Step 1: Add failing geometry and pagination tests**

Append these tests to `tests/test_profiles_scene.py`:

```python
def test_profile_container_matches_options_container_geometry():
    from ella_bot.ui.pygame_gui.scenes.profiles import (
        _PROFILE_CONTAINER_RADIUS,
    )

    scene = _scene()
    rect = scene._get_container_rect(1280, 720)

    assert rect == pygame.Rect(280, 32, 720, 656)
    assert rect.centerx == 640
    assert _PROFILE_CONTAINER_RADIUS == 140


def test_profile_pages_contain_two_profiles():
    scene = _scene()
    profiles = tuple(_profile(index) for index in range(5))

    assert scene._page_count(len(profiles)) == 3
    scene.carousel_page = 1
    assert scene._visible_profiles(profiles) == profiles[2:4]


def test_on_enter_opens_page_containing_active_profile():
    scene = _scene()
    scene._lottie_bg = False
    profiles = tuple(_profile(index) for index in range(5))
    scene.app.profiles.return_value = profiles
    scene.app.active_profile.return_value = profiles[3]

    scene.on_enter()

    assert scene.carousel_page == 1
```

- [ ] **Step 2: Run the new tests and verify the intended failures**

Run:

```bash
pytest \
  tests/test_profiles_scene.py::test_profile_container_matches_options_container_geometry \
  tests/test_profiles_scene.py::test_profile_pages_contain_two_profiles \
  tests/test_profiles_scene.py::test_on_enter_opens_page_containing_active_profile \
  -v
```

Expected: FAIL because the constants, helper methods, and `carousel_page` do not exist.

- [ ] **Step 3: Add constants, state, and pure helpers**

Add below `_summary_text` in `profiles.py`:

```python
_PROFILE_PAGE_SIZE = 2
_PROFILE_CONTAINER_WIDTH = 720
_PROFILE_CONTAINER_RADIUS = 140
```

Add to `ProfilesScene.__init__`:

```python
        self.carousel_page = 0
```

Add above `render()`:

```python
    @staticmethod
    def _get_container_rect(width: int, height: int) -> pygame.Rect:
        return pygame.Rect(
            (width - _PROFILE_CONTAINER_WIDTH) // 2,
            32,
            _PROFILE_CONTAINER_WIDTH,
            height - 64,
        )

    @staticmethod
    def _page_count(profile_count: int) -> int:
        if profile_count <= 0:
            return 0
        return (profile_count + _PROFILE_PAGE_SIZE - 1) // _PROFILE_PAGE_SIZE

    def _clamp_carousel_page(self, profiles: tuple) -> None:
        last_page = max(0, self._page_count(len(profiles)) - 1)
        self.carousel_page = max(0, min(self.carousel_page, last_page))

    def _visible_profiles(self, profiles: tuple) -> tuple:
        self._clamp_carousel_page(profiles)
        start = self.carousel_page * _PROFILE_PAGE_SIZE
        return profiles[start : start + _PROFILE_PAGE_SIZE]

    def _show_active_profile_page(
        self,
        profiles: tuple,
        active_profile_id: str | None,
    ) -> None:
        self.carousel_page = 0
        if active_profile_id is None:
            return
        for index, profile in enumerate(profiles):
            if profile.id == active_profile_id:
                self.carousel_page = index // _PROFILE_PAGE_SIZE
                return
```

- [ ] **Step 4: Initialize the active page on scene entry**

At the end of `on_enter()`, add:

```python
        profiles = tuple(self.app.profiles())[:MAX_PROFILES]
        active = self.app.active_profile()
        self._show_active_profile_page(
            profiles,
            active.id if active is not None else None,
        )
```

Replace the current Profiles container construction in `render()` with:

```python
        card_rect = self._get_container_rect(width, height)
        pygame.draw.rect(
            screen,
            (25, 5, 35),
            card_rect.move(4, 4),
            border_radius=_PROFILE_CONTAINER_RADIUS,
        )
        pygame.draw.rect(
            screen,
            (87, 39, 108),
            card_rect,
            border_radius=_PROFILE_CONTAINER_RADIUS,
        )
        pygame.draw.rect(
            screen,
            (127, 63, 151),
            card_rect,
            width=8,
            border_radius=_PROFILE_CONTAINER_RADIUS,
        )
```

- [ ] **Step 5: Run focused and existing profile tests**

Run:

```bash
pytest tests/test_profiles_scene.py -q
```

Expected: all existing tests and the three new tests pass.

- [ ] **Step 6: Commit the pagination model**

```bash
git diff --check -- src/ella_bot/ui/pygame_gui/scenes/profiles.py tests/test_profiles_scene.py
git add src/ella_bot/ui/pygame_gui/scenes/profiles.py tests/test_profiles_scene.py
git commit -m "refactor: add profiles carousel pagination model"
```

---

### Task 2: Carousel Navigation, Indicators, and Fixed Actions

**Files:**
- Modify: `src/ella_bot/ui/pygame_gui/scenes/profiles.py:29-315,349-473`
- Modify: `tests/test_profiles_scene.py:46-152`

**Interfaces:**
- Consumes: Task 1 pagination helpers and `carousel_page`.
- Produces: `carousel_previous_button`, `carousel_next_button`, `page_indicator_rects`, `page_indicator_states`, `empty_state_rect`, `capacity_status_rect`, `_change_carousel_page(delta, profiles)`, and `_draw_carousel_arrow(screen, rect, direction, enabled, pressed)`.

- [ ] **Step 1: Add failing carousel rendering tests**

Add these tests to `tests/test_profiles_scene.py`:

```python
def test_carousel_renders_only_two_profiles_and_three_indicators():
    scene = _scene()
    profiles = tuple(_profile(index) for index in range(5))
    scene.app.profiles.return_value = profiles

    scene.render()

    assert tuple(scene.profile_cards) == (profiles[0].id, profiles[1].id)
    assert scene.carousel_previous_button is None
    assert scene.carousel_next_button is not None
    assert len(scene.page_indicator_rects) == 3
    assert scene.page_indicator_states == [True, False, False]
    assert scene.carousel_page == 0


def test_carousel_arrow_moves_page_and_disables_at_last_page():
    scene = _scene()
    profiles = tuple(_profile(index) for index in range(5))
    scene.app.profiles.return_value = profiles
    scene.render()

    next_point = scene.carousel_next_button.center
    scene.handle_event(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=next_point)
    )
    scene.handle_event(
        pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=next_point)
    )
    scene.carousel_page = 2
    scene.render()

    assert tuple(scene.profile_cards) == (profiles[4].id,)
    assert scene.carousel_previous_button is not None
    assert scene.carousel_next_button is None


def test_create_and_back_are_fixed_equal_actions_outside_carousel():
    scene = _scene()
    scene.app.profiles.return_value = tuple(_profile(index) for index in range(3))

    scene.render()

    assert scene.create_button is not None
    assert scene.back_button is not None
    assert scene.create_button.size == scene.back_button.size
    assert not any(
        rect.colliderect(scene.create_button)
        for rect in scene._profile_card_rects.values()
    )


def test_empty_profiles_show_empty_state_without_indicators():
    scene = _scene()

    scene.render()

    assert scene.empty_state_rect is not None
    assert scene.page_indicator_rects == []
    assert scene.carousel_previous_button is None
    assert scene.carousel_next_button is None
    assert scene.create_button is not None
```

Update `test_rendering_five_profiles_hides_create_button` so its final assertion is:

```python
    assert scene.create_button is None
    assert scene.capacity_status_rect is not None
    assert len(scene.profile_cards) == 2
```

- [ ] **Step 2: Run the carousel tests and verify they fail**

Run:

```bash
pytest tests/test_profiles_scene.py -k "carousel or fixed_equal or empty_profiles or rendering_five" -v
```

Expected: FAIL because carousel hitboxes, indicators, fixed action geometry, and empty/capacity state do not exist.

- [ ] **Step 3: Add carousel state fields**

Add to `ProfilesScene.__init__`:

```python
        self.carousel_previous_button: pygame.Rect | None = None
        self.carousel_next_button: pygame.Rect | None = None
        self.page_indicator_rects: list[pygame.Rect] = []
        self.page_indicator_states: list[bool] = []
        self.empty_state_rect: pygame.Rect | None = None
        self.capacity_status_rect: pygame.Rect | None = None
```

- [ ] **Step 4: Add page-change and arrow drawing helpers**

Add above `render()`:

```python
    def _change_carousel_page(self, delta: int, profiles: tuple) -> None:
        page_count = self._page_count(len(profiles))
        last_page = max(0, page_count - 1)
        self.carousel_page = max(0, min(self.carousel_page + delta, last_page))
        self.profile_cards = {}
        self.manage_buttons = {}

    def _draw_carousel_arrow(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        direction: int,
        enabled: bool,
        pressed: bool,
    ) -> None:
        fill = (70, 30, 90) if enabled else (65, 42, 73)
        if pressed and enabled:
            fill = (60, 24, 78)
        stroke = (127, 63, 151) if enabled else (91, 70, 98)
        icon = (255, 250, 243) if enabled else (145, 127, 151)
        if enabled and not pressed:
            pygame.draw.rect(
                screen,
                (35, 10, 45),
                rect.move(3, 3),
                border_radius=18,
            )
        pygame.draw.rect(screen, fill, rect, border_radius=18)
        pygame.draw.rect(screen, stroke, rect, width=4, border_radius=18)
        cx, cy = rect.center
        offset = 6 * direction
        pygame.draw.lines(
            screen,
            icon,
            False,
            [(cx - offset, cy - 12), (cx + offset, cy), (cx - offset, cy + 12)],
            width=5,
        )
```

- [ ] **Step 5: Route enabled arrow input**

In `_handle_mouse_down`, before management buttons, add:

```python
        if (
            self.carousel_previous_button
            and self.carousel_previous_button.collidepoint(mouse_pos)
        ):
            self.pressed_button = "carousel_previous"
            play_button_click()
            return
        if (
            self.carousel_next_button
            and self.carousel_next_button.collidepoint(mouse_pos)
        ):
            self.pressed_button = "carousel_next"
            play_button_click()
            return
```

In `_handle_mouse_up`, before Create/Back handling, add:

```python
        profiles = tuple(self.app.profiles())[:MAX_PROFILES]
        if (
            pressed == "carousel_previous"
            and self.carousel_previous_button
            and self.carousel_previous_button.collidepoint(mouse_pos)
        ):
            self._change_carousel_page(-1, profiles)
            return
        if (
            pressed == "carousel_next"
            and self.carousel_next_button
            and self.carousel_next_button.collidepoint(mouse_pos)
        ):
            self._change_carousel_page(1, profiles)
            return
```

- [ ] **Step 6: Replace the grid with a two-card carousel**

In `render()`, replace the `entries`, grid sizing, grid loop, and old Back button block with this layout:

```python
        self.profile_cards = {}
        self.manage_buttons = {}
        self.create_button = None
        self._profile_card_rects = {}
        self._management_profiles = {}
        self.page_indicator_rects = []
        self.page_indicator_states = []
        self.empty_state_rect = None
        self.capacity_status_rect = None

        page_count = self._page_count(len(profiles))
        visible_profiles = self._visible_profiles(profiles)

        horizontal_padding = 24
        arrow_w, arrow_h = 48, 72
        arrow_gap = 12
        profile_gap = 16
        profile_h = 280
        carousel_top = banner_rect.bottom + 32
        cards_total_w = (
            card_rect.width
            - 2 * horizontal_padding
            - 2 * arrow_w
            - 2 * arrow_gap
            - profile_gap
        )
        profile_w = cards_total_w // 2
        previous_rect = pygame.Rect(
            card_rect.left + horizontal_padding,
            carousel_top + (profile_h - arrow_h) // 2,
            arrow_w,
            arrow_h,
        )
        first_card_left = previous_rect.right + arrow_gap
        next_rect = pygame.Rect(
            first_card_left + 2 * profile_w + profile_gap + arrow_gap,
            previous_rect.top,
            arrow_w,
            arrow_h,
        )

        previous_enabled = page_count > 1 and self.carousel_page > 0
        next_enabled = page_count > 1 and self.carousel_page < page_count - 1
        self.carousel_previous_button = previous_rect if previous_enabled else None
        self.carousel_next_button = next_rect if next_enabled else None
        self._draw_carousel_arrow(
            screen,
            previous_rect,
            -1,
            previous_enabled,
            self.pressed_button == "carousel_previous",
        )
        self._draw_carousel_arrow(
            screen,
            next_rect,
            1,
            next_enabled,
            self.pressed_button == "carousel_next",
        )

        if visible_profiles:
            for slot, profile in enumerate(visible_profiles):
                c_rect = pygame.Rect(
                    first_card_left + slot * (profile_w + profile_gap),
                    carousel_top,
                    profile_w,
                    profile_h,
                )
                self._profile_card_rects[profile.id] = c_rect
                self._management_profiles[profile.id] = profile
                self.profile_cards[profile.id] = pygame.Rect(
                    c_rect.left,
                    c_rect.top,
                    c_rect.width,
                    c_rect.height - 48,
                )
                self._draw_profile_card(
                    screen,
                    c_rect,
                    profile,
                    profile.id == active_profile_id,
                )
        else:
            self.empty_state_rect = pygame.Rect(
                first_card_left,
                carousel_top,
                2 * profile_w + profile_gap,
                profile_h,
            )
            empty = self._render_adaptive_text(
                "No profiles yet",
                24,
                (227, 198, 236),
                default_font=self._get_adaptive_font(24, bold=True),
            )
            if empty:
                screen.blit(empty, empty.get_rect(center=self.empty_state_rect.center))

        if page_count:
            dot_radius = 6
            dot_gap = 18
            indicators_y = carousel_top + profile_h + 22
            total_dot_w = page_count * dot_radius * 2 + (page_count - 1) * dot_gap
            dot_x = cx - total_dot_w // 2
            for index in range(page_count):
                dot_rect = pygame.Rect(
                    dot_x + index * (dot_radius * 2 + dot_gap),
                    indicators_y - dot_radius,
                    dot_radius * 2,
                    dot_radius * 2,
                )
                self.page_indicator_rects.append(dot_rect)
                is_current = index == self.carousel_page
                self.page_indicator_states.append(is_current)
                color = (242, 210, 20) if is_current else (227, 198, 236)
                pygame.draw.circle(screen, color, dot_rect.center, dot_radius)

        action_w, action_h, action_gap = 250, 56, 16
        action_y = card_rect.bottom - action_h - 28
        left_action = pygame.Rect(
            cx - action_gap // 2 - action_w,
            action_y,
            action_w,
            action_h,
        )
        self.back_button = pygame.Rect(
            cx + action_gap // 2,
            action_y,
            action_w,
            action_h,
        )
        action_font = self._get_adaptive_font(20, bold=True)
        if len(profiles) < MAX_PROFILES:
            self.create_button = left_action
            create = Button(
                self.create_button,
                label="+ Create Profile",
                variant="violet",
                font=action_font,
                corner_radius=18,
                stroke_weight=5,
            )
            create.is_pressed = self.pressed_button == "create"
            create.draw(screen)
        else:
            self.capacity_status_rect = left_action
            status = self._render_adaptive_text(
                "5 of 5 profiles",
                20,
                (227, 198, 236),
                default_font=action_font,
            )
            if status:
                screen.blit(status, status.get_rect(center=left_action.center))

        back = Button(
            self.back_button,
            label="Back to Menu",
            variant="yellow",
            font=action_font,
            corner_radius=18,
            stroke_weight=5,
        )
        back.is_pressed = self.pressed_button == "back"
        back.draw(screen)
```

Move the non-modal error placement to:

```python
                    error.get_rect(centerx=cx, bottom=action_y - 8),
```

Delete `_draw_create_card`, which no longer has a caller.

- [ ] **Step 7: Run the carousel and full Profiles scene tests**

Run:

```bash
pytest tests/test_profiles_scene.py -q
```

Expected: all tests pass, including existing modal and touchscreen-keyboard coverage.

- [ ] **Step 8: Commit carousel navigation and fixed actions**

```bash
git diff --check -- src/ella_bot/ui/pygame_gui/scenes/profiles.py tests/test_profiles_scene.py
git add src/ella_bot/ui/pygame_gui/scenes/profiles.py tests/test_profiles_scene.py
git commit -m "feat: add two-profile carousel navigation"
```

---

### Task 3: Consistent Profile Card Actions and Hitboxes

**Files:**
- Modify: `src/ella_bot/ui/pygame_gui/scenes/profiles.py:475-590`
- Modify: `tests/test_profiles_scene.py:208-318,478-497`

**Interfaces:**
- Consumes: Task 2's fixed `pygame.Rect` profile cards and visible-profile rendering loop.
- Produces: `_management_button_rects(rect) -> dict[str, pygame.Rect]`, `_profile_selection_rect(rect) -> pygame.Rect`, and the approved Rename/Reset/Delete layout.

- [ ] **Step 1: Add failing card geometry and label tests**

Append these tests to `tests/test_profiles_scene.py`:

```python
def test_visible_profile_cards_and_actions_use_consistent_geometry():
    scene = _scene()
    profiles = (_profile(1, "Maria"), _profile(2, "Leo"))
    scene.app.profiles.return_value = profiles

    scene.render()

    first_card = scene._profile_card_rects[profiles[0].id]
    second_card = scene._profile_card_rects[profiles[1].id]
    assert first_card.size == second_card.size

    rename = scene.manage_buttons[("rename", profiles[0].id)]
    reset = scene.manage_buttons[("reset", profiles[0].id)]
    delete = scene.manage_buttons[("delete", profiles[0].id)]
    assert rename.height == reset.height == delete.height == 40
    assert reset.size == delete.size
    assert rename.top < reset.top
    assert rename.width == reset.width + 8 + delete.width


def test_profile_selection_hitbox_stops_above_management_actions():
    scene = _scene()
    profile = _profile(1)
    scene.app.profiles.return_value = (profile,)

    scene.render()

    selection = scene.profile_cards[profile.id]
    rename = scene.manage_buttons[("rename", profile.id)]
    assert selection.bottom <= rename.top - 8


def test_management_labels_use_short_consistent_copy():
    scene = _scene()
    profile = _profile(1)
    scene.app.profiles.return_value = (profile,)
    real_font = pygame.font.SysFont(None, 16)
    tracking_font = MagicMock()
    tracking_font.render.side_effect = real_font.render
    scene._get_adaptive_font = MagicMock(return_value=tracking_font)

    scene.render()

    rendered_labels = [call.args[0] for call in tracking_font.render.call_args_list]
    assert "Rename" in rendered_labels
    assert "Reset" in rendered_labels
    assert "Delete" in rendered_labels
    assert "Reset Progress" not in rendered_labels
```

- [ ] **Step 2: Run the new card tests and verify they fail**

Run:

```bash
pytest tests/test_profiles_scene.py -k "consistent_geometry or stops_above or short_consistent" -v
```

Expected: FAIL because the current card uses a three-column 30px action row and a fixed 48px management strip.

- [ ] **Step 3: Add reusable card geometry helpers**

Add above `_draw_profile_card`:

```python
    @staticmethod
    def _management_button_rects(rect: pygame.Rect) -> dict[str, pygame.Rect]:
        padding = 16
        gap = 8
        button_h = 40
        bottom_y = rect.bottom - padding - button_h
        rename_y = bottom_y - gap - button_h
        full_w = rect.width - 2 * padding
        half_w = (full_w - gap) // 2
        return {
            "rename": pygame.Rect(rect.left + padding, rename_y, full_w, button_h),
            "reset": pygame.Rect(rect.left + padding, bottom_y, half_w, button_h),
            "delete": pygame.Rect(
                rect.left + padding + half_w + gap,
                bottom_y,
                half_w,
                button_h,
            ),
        }

    @classmethod
    def _profile_selection_rect(cls, rect: pygame.Rect) -> pygame.Rect:
        rename = cls._management_button_rects(rect)["rename"]
        return pygame.Rect(
            rect.left,
            rect.top,
            rect.width,
            max(0, rename.top - rect.top - 8),
        )
```

In Task 2's render loop, replace the temporary selection rectangle with:

```python
                self.profile_cards[profile.id] = self._profile_selection_rect(c_rect)
```

- [ ] **Step 4: Replace profile card typography and action rendering**

In `_draw_profile_card`, keep the card shadow, fill, active border, summary loading, and Active badge. Use these exact typography calls:

```python
        name_surf = self._render_adaptive_text(
            profile.name,
            24,
            (255, 250, 243),
            max_w=rect.width - (110 if is_active else 32),
            bold=True,
            default_font=self._get_adaptive_font(24, bold=True),
        )
        if name_surf:
            screen.blit(
                name_surf,
                name_surf.get_rect(left=rect.left + 16, top=rect.top + 18),
            )

        progress_surf = self._render_adaptive_text(
            _summary_text(summary),
            18,
            (227, 198, 236),
            max_w=rect.width - 32,
            default_font=self._get_adaptive_font(18),
        )
        if progress_surf:
            screen.blit(
                progress_surf,
                progress_surf.get_rect(left=rect.left + 16, top=rect.top + 58),
            )
```

Replace the divider and three-column management loop with:

```python
        action_rects = self._management_button_rects(rect)
        divider_y = action_rects["rename"].top - 12
        pygame.draw.line(
            screen,
            (127, 63, 151),
            (rect.left + 16, divider_y),
            (rect.right - 16, divider_y),
            width=2,
        )
        action_font = self._get_adaptive_font(16, bold=True)
        for action, label, variant in (
            ("rename", "Rename", "yellow"),
            ("reset", "Reset", "yellow"),
            ("delete", "Delete", "violet"),
        ):
            btn_rect = action_rects[action]
            self.manage_buttons[(action, profile.id)] = btn_rect
            button = Button(
                btn_rect,
                label=label,
                variant=variant,
                font=action_font,
                corner_radius=14,
                stroke_weight=3,
            )
            button.is_pressed = self.pressed_button == f"{action}:{profile.id}"
            button.draw(screen)
```

Delete `_draw_management_button`, which no longer has a caller.

- [ ] **Step 5: Clamp the page after profile deletion**

At the end of `_confirm_management`, after successful reset/delete handling and before any scene switch, add:

```python
        profiles = tuple(self.app.profiles())[:MAX_PROFILES]
        self._clamp_carousel_page(profiles)
```

Add this regression test:

```python
def test_delete_clamps_carousel_to_new_last_page():
    scene = _scene()
    profiles = tuple(_profile(index) for index in range(5))
    scene.app.profiles.return_value = profiles[:4]
    scene.carousel_page = 2
    scene._open_confirmation("delete", profiles[4])

    scene._confirm_management()

    assert scene.carousel_page == 1


def test_rename_and_reset_keep_current_carousel_page():
    scene = _scene()
    profiles = tuple(_profile(index) for index in range(4))
    scene.app.profiles.return_value = profiles
    scene.carousel_page = 1

    scene._open_rename(profiles[2])
    scene.name_input = "Renamed"
    scene._save_name()
    assert scene.carousel_page == 1

    scene._open_confirmation("reset", profiles[2])
    scene._confirm_management()
    assert scene.carousel_page == 1
```

- [ ] **Step 6: Run all Profiles tests**

Run:

```bash
pytest tests/test_profiles_scene.py -q
```

Expected: all Profiles tests pass with no per-label action scaling and no overlapping hitboxes.

- [ ] **Step 7: Commit the profile card redesign**

```bash
git diff --check -- src/ella_bot/ui/pygame_gui/scenes/profiles.py tests/test_profiles_scene.py
git add src/ella_bot/ui/pygame_gui/scenes/profiles.py tests/test_profiles_scene.py
git commit -m "style: redesign carousel profile cards"
```

---

### Task 4: Regression and Layout Verification

**Files:**
- Verify: `src/ella_bot/ui/pygame_gui/scenes/profiles.py`
- Verify: `src/ella_bot/ui/pygame_gui/components/button.py`
- Verify: `tests/test_profiles_scene.py`
- Verify: `tests/test_button.py`
- Verify: `tests/test_settings_scene.py`

**Interfaces:**
- Consumes: completed Tasks 1-3.
- Produces: verification evidence for the centered container, carousel interaction, card actions, shared button themes, and unchanged Options page.

- [ ] **Step 1: Run the complete focused GUI regression set**

```bash
pytest \
  tests/test_profiles_scene.py \
  tests/test_button.py \
  tests/test_settings_scene.py \
  -q
```

Expected: all tests pass.

- [ ] **Step 2: Run syntax and whitespace checks**

```bash
python -m py_compile \
  src/ella_bot/ui/pygame_gui/scenes/profiles.py \
  src/ella_bot/ui/pygame_gui/components/button.py
git diff --check
```

Expected: both commands exit zero.

- [ ] **Step 3: Run a headless five-profile rendering smoke test**

Run:

```bash
SDL_VIDEODRIVER=dummy pytest \
  tests/test_profiles_scene.py::test_carousel_renders_only_two_profiles_and_three_indicators \
  tests/test_profiles_scene.py::test_visible_profile_cards_and_actions_use_consistent_geometry \
  tests/test_profiles_scene.py::test_delete_clamps_carousel_to_new_last_page \
  -v
```

Expected: all three tests pass.

- [ ] **Step 4: Attempt the repository test suite and record environmental blockers exactly**

```bash
pytest tests -q
```

Expected: no feature-related failures. The current environment may still stop during collection because `cv2` and `numpy` are not installed; if so, record the exact collection errors without changing unrelated dependencies.

- [ ] **Step 5: Inspect the final scoped diff and status**

```bash
git diff HEAD~3 -- \
  src/ella_bot/ui/pygame_gui/scenes/profiles.py \
  tests/test_profiles_scene.py
git status --short
```

Confirm that only the intended profile UI/tests and committed design/plan artifacts belong to this feature. Preserve existing changes in `config/settings.ini`, `data/profiles.json`, and profile session data.
