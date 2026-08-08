from __future__ import annotations

import pygame
from typing import Optional

from ella_bot.services.profile_store import MAX_PROFILES, ProfileStoreError
from ella_bot.ui.pygame_gui.scene import BaseScene
from ella_bot.services.sound_effects import play_button_click
from ella_bot.ui.pygame_gui.components.button import Button
from ella_bot.ui.pygame_gui.components.on_screen_keyboard import (
    KeyboardAction,
    OnScreenKeyboard,
)
from ella_bot.ui.pygame_gui.lottie_bg import LottieBackground, load_animated_background


def _summary_text(summary) -> str:
    if summary is None:
        return "Ready to begin"
    level = summary.level.upper()
    if summary.phase == "results":
        return f"Level {level} - Results"
    return f"Level {level} - Item {summary.item_number}"


_PROFILE_PAGE_SIZE = 2
_PROFILE_CONTAINER_WIDTH = 720
_PROFILE_CONTAINER_RADIUS = 140


class ProfilesScene(BaseScene):
    """Browse learner profiles and create, select, or manage them."""

    def __init__(self, app):
        super().__init__(app)
        self.profile_cards: dict[str, pygame.Rect] = {}
        self.manage_buttons: dict[tuple[str, str], pygame.Rect] = {}
        self.create_button: pygame.Rect | None = None
        self.back_button: pygame.Rect | None = None
        self.modal: str | None = None
        self.target_profile_id: str | None = None
        self.target_profile_name = ""
        self.name_input = ""
        self.error_message = ""
        self.pressed_button: str | None = None
        self.carousel_page = 0

        self._profile_card_rects: dict[str, pygame.Rect] = {}
        self._management_profiles: dict[str, object] = {}
        self._modal_save_button: pygame.Rect | None = None
        self._modal_cancel_button: pygame.Rect | None = None
        self.keyboard = OnScreenKeyboard(self.app.font_small)
        self._lottie_bg: Optional[LottieBackground] = None

    def _load_assets(self) -> None:
        if self._lottie_bg is None:
            self._lottie_bg = load_animated_background(
                [
                    "assets/Final_Lightray.lottie",
                    "assets/Lightray.lottie",
                    "assets/shinebg.lottie",
                    "assets/shinebg.json",
                ],
                video_fallback="assets/Comp 1_2.mp4",
            )
            if self._lottie_bg is None:
                self._lottie_bg = False

    def on_enter(self) -> None:
        self._load_assets()
        self._close_modal()
        self.error_message = ""
        self.pressed_button = None
        profiles = tuple(self.app.profiles())[:MAX_PROFILES]
        active = self.app.active_profile()
        self._show_active_profile_page(
            profiles,
            active.id if active is not None else None,
        )

    def on_exit(self) -> None:
        pygame.key.stop_text_input()
        self.keyboard.cancel_press()
        self.pressed_button = None

    def _open_create(self) -> None:
        if len(self.app.profiles()) >= MAX_PROFILES:
            return
        self.modal = "create"
        self.target_profile_id = None
        self.name_input = ""
        self.error_message = ""
        self.pressed_button = None
        self.keyboard.reset()
        pygame.key.start_text_input()

    def _open_rename(self, profile) -> None:
        self.modal = "rename"
        self.target_profile_id = profile.id
        self.target_profile_name = profile.name
        self.name_input = profile.name
        self.error_message = ""
        self.pressed_button = None
        self.keyboard.reset()
        pygame.key.start_text_input()

    def _open_confirmation(self, action: str, profile) -> None:
        pygame.key.stop_text_input()
        self.modal = action
        self.target_profile_id = profile.id
        self.target_profile_name = profile.name
        self.name_input = ""
        self.error_message = ""
        self.pressed_button = None

    def _close_modal(self) -> None:
        pygame.key.stop_text_input()
        self.keyboard.cancel_press()
        self.modal = None
        self.target_profile_id = None
        self.target_profile_name = ""
        self.name_input = ""
        self.error_message = ""
        self.pressed_button = None

    def _save_name(self) -> None:
        try:
            if self.modal == "rename":
                self.app.rename_profile(self.target_profile_id, self.name_input)
                destination = None
            else:
                self.app.create_profile(self.name_input)
                destination = "level_selection"
        except (ProfileStoreError, OSError) as exc:
            self.error_message = str(exc) or "Profile could not be saved."
            return
        self._close_modal()
        if destination is not None:
            self.app.switch_scene(destination)

    def _apply_keyboard_action(self, action: KeyboardAction | None) -> None:
        if action is None or action.kind == "shift":
            return
        if action.kind == "backspace":
            self.name_input = self.name_input[:-1]
            self.error_message = ""
            return
        candidate = self.name_input + action.text
        if len(candidate) <= 20:
            self.name_input = candidate
            self.error_message = ""

    def _confirm_management(self) -> None:
        target_profile_id = self.target_profile_id
        action = self.modal
        active = self.app.active_profile()
        deleting_active = (
            action == "delete"
            and active is not None
            and active.id == target_profile_id
        )
        try:
            if action == "reset":
                cleaned = self.app.reset_profile_progress(target_profile_id)
            elif action == "delete":
                cleaned = self.app.delete_profile(target_profile_id)
            else:
                return
        except (ProfileStoreError, OSError) as exc:
            self.error_message = str(exc) or "Profile could not be updated."
            return
        if deleting_active and not cleaned:
            self.modal = "cleanup_warning"
            self.target_profile_id = None
            self.target_profile_name = ""
            self.error_message = "Some old profile files could not be removed."
            self.pressed_button = None
            self._modal_cancel_button = None
            return
        self._close_modal()
        if not cleaned:
            self.error_message = "Some old profile files could not be removed."
        if deleting_active:
            self.app.switch_scene("main_menu")

    def _acknowledge_cleanup_warning(self) -> None:
        self._close_modal()
        self.app.switch_scene("main_menu")

    def _select_profile(self, profile_id: str) -> None:
        try:
            self.app.select_profile(profile_id)
        except (ProfileStoreError, OSError) as exc:
            self.error_message = str(exc) or "Profile could not be selected."
            return
        pygame.key.stop_text_input()
        self.app.switch_scene("main_menu")

    def _go_back(self) -> None:
        pygame.key.stop_text_input()
        self.app.switch_scene("main_menu")

    def handle_event(self, event) -> None:
        if event.type == pygame.TEXTINPUT and self.modal in ("create", "rename"):
            candidate = self.name_input + event.text
            if len(candidate) <= 20:
                self.name_input = candidate
                self.error_message = ""
            return

        if event.type == pygame.KEYDOWN:
            if self.modal in ("create", "rename"):
                if event.key == pygame.K_BACKSPACE:
                    self.name_input = self.name_input[:-1]
                    self.error_message = ""
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self._save_name()
                elif event.key == pygame.K_ESCAPE:
                    self._close_modal()
            elif event.key == pygame.K_ESCAPE:
                self._go_back()
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_mouse_down(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._handle_mouse_up(event.pos)

    def _handle_mouse_down(self, mouse_pos) -> None:
        if self.modal is not None:
            if self._modal_save_button and self._modal_save_button.collidepoint(mouse_pos):
                self.keyboard.cancel_press()
                self.pressed_button = (
                    "modal_save"
                    if self.modal in ("create", "rename")
                    else (
                        "modal_ack"
                        if self.modal == "cleanup_warning"
                        else "modal_confirm"
                    )
                )
            elif self._modal_cancel_button and self._modal_cancel_button.collidepoint(mouse_pos):
                self.keyboard.cancel_press()
                self.pressed_button = "modal_cancel"
            elif self.modal in ("create", "rename"):
                self.keyboard.handle_mouse_down(mouse_pos)
            if self.pressed_button:
                play_button_click()
            return

        for (action, profile_id), rect in self.manage_buttons.items():
            if rect.collidepoint(mouse_pos):
                self.pressed_button = f"{action}:{profile_id}"
                play_button_click()
                return
        for profile_id, rect in self.profile_cards.items():
            if rect.collidepoint(mouse_pos):
                self.pressed_button = f"profile:{profile_id}"
                play_button_click()
                return
        if self.create_button and self.create_button.collidepoint(mouse_pos):
            self.pressed_button = "create"
        elif self.back_button and self.back_button.collidepoint(mouse_pos):
            self.pressed_button = "back"

        if self.pressed_button:
            play_button_click()

    def _handle_mouse_up(self, mouse_pos) -> None:
        pressed = self.pressed_button
        self.pressed_button = None
        if self.modal is not None:
            if (
                pressed == "modal_save"
                and self._modal_save_button
                and self._modal_save_button.collidepoint(mouse_pos)
            ):
                self.keyboard.cancel_press()
                self._save_name()
            elif (
                pressed == "modal_ack"
                and self._modal_save_button
                and self._modal_save_button.collidepoint(mouse_pos)
            ):
                self.keyboard.cancel_press()
                self._acknowledge_cleanup_warning()
            elif (
                pressed == "modal_confirm"
                and self._modal_save_button
                and self._modal_save_button.collidepoint(mouse_pos)
            ):
                self.keyboard.cancel_press()
                self._confirm_management()
            elif (
                pressed == "modal_cancel"
                and self._modal_cancel_button
                and self._modal_cancel_button.collidepoint(mouse_pos)
            ):
                self.keyboard.cancel_press()
                self._close_modal()
            elif self.modal in ("create", "rename"):
                self._apply_keyboard_action(self.keyboard.handle_mouse_up(mouse_pos))
            return

        if (
            pressed == "create"
            and self.create_button
            and self.create_button.collidepoint(mouse_pos)
        ):
            self._open_create()
        elif pressed == "back" and self.back_button and self.back_button.collidepoint(mouse_pos):
            self._go_back()
        elif pressed and pressed.split(":", 1)[0] in ("rename", "reset", "delete"):
            action, profile_id = pressed.split(":", 1)
            rect = self.manage_buttons.get((action, profile_id))
            profile = self._management_profiles.get(profile_id)
            if rect and rect.collidepoint(mouse_pos) and profile is not None:
                if action == "rename":
                    self._open_rename(profile)
                else:
                    self._open_confirmation(action, profile)
        elif pressed and pressed.startswith("profile:"):
            profile_id = pressed.split(":", 1)[1]
            rect = self.profile_cards.get(profile_id)
            if rect and rect.collidepoint(mouse_pos):
                self._select_profile(profile_id)

    def _get_adaptive_font(self, size: int, bold: bool = False):
        if hasattr(self.app, "_get_sys_font"):
            try:
                res = self.app._get_sys_font(size, bold=bold)
                if isinstance(res, pygame.font.Font):
                    return res
            except Exception:
                pass
        font = getattr(self.app, "font_body", None)
        if isinstance(font, pygame.font.Font):
            return font
        return pygame.font.SysFont(None, size, bold=bold)

    def _render_adaptive_text(
        self,
        text: str,
        size: int,
        color: tuple,
        max_w: int = 0,
        bold: bool = False,
        default_font: pygame.font.Font | None = None,
    ) -> pygame.Surface | None:
        font = default_font or self._get_adaptive_font(size, bold=bold)
        surf = font.render(text, True, color)
        if isinstance(surf, pygame.Surface):
            if max_w > 0 and surf.get_width() > max_w:
                scale_ratio = max_w / surf.get_width()
                new_w = max_w
                new_h = max(1, int(surf.get_height() * scale_ratio))
                surf = pygame.transform.smoothscale(surf, (new_w, new_h))
            return surf
        return None

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

    def render(self) -> None:
        self._load_assets()
        screen = self.app.screen
        width, height = screen.get_size()
        now_ms = pygame.time.get_ticks()

        # 1. Render Lottie Animated Lightray Background
        if self._lottie_bg:
            vf = self._lottie_bg.get_frame(now_ms, (width, height))
            if vf:
                screen.blit(vf, (0, 0))
            else:
                screen.fill((0, 0, 0))
        else:
            screen.fill((0, 0, 0))

        # 2. Main Full-Screen Purple Container (#57276C fill, #7F3F97 stroke)
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

        cx = card_rect.centerx

        # 3. Top Title Banner "Who's Learning?"
        banner_w, banner_h = min(360, card_rect.width - 40), 60
        banner_rect = pygame.Rect(cx - banner_w // 2, card_rect.top + 22, banner_w, banner_h)
        title_font = getattr(self.app, "font_title", self.app.font_button)
        if title_font and hasattr(title_font, "render"):
            title_font.render("Who's Learning?", True, (255, 250, 243))
        banner_btn_font = self._get_adaptive_font(28, bold=True)
        banner_btn = Button(banner_rect, label="Who's Learning?", variant="yellow", font=banner_btn_font, stroke_weight=8)
        banner_btn.draw(screen)

        # Profiles Grid setup
        profiles = tuple(self.app.profiles())[:MAX_PROFILES]
        active = self.app.active_profile()
        active_profile_id = active.id if active is not None else None

        entries: list[tuple[str, object | None]] = [
            ("profile", profile) for profile in profiles
        ]
        if len(profiles) < MAX_PROFILES:
            entries.append(("create", None))

        self.profile_cards = {}
        self.manage_buttons = {}
        self.create_button = None
        self._profile_card_rects = {}
        self._management_profiles = {}

        grid_left = card_rect.left + 50
        grid_top = banner_rect.bottom + 25
        grid_width = card_rect.width - 100
        grid_bottom = card_rect.bottom - 100
        column_gap = 20
        row_gap = 14

        # Display cards in grid (2 columns)
        card_width = (grid_width - column_gap) // 2
        num_items = len(entries)
        num_rows = max(1, (num_items + 1) // 2)
        card_height = min(136, (grid_bottom - grid_top - (num_rows - 1) * row_gap) // num_rows)

        for index, (kind, value) in enumerate(entries):
            row, column = divmod(index, 2)
            c_rect = pygame.Rect(
                grid_left + column * (card_width + column_gap),
                grid_top + row * (card_height + row_gap),
                card_width,
                card_height,
            )
            if kind == "create":
                self.create_button = c_rect
                self._draw_create_card(screen, c_rect)
                continue

            profile = value
            self._profile_card_rects[profile.id] = c_rect
            self._management_profiles[profile.id] = profile
            selection_rect = pygame.Rect(
                c_rect.left,
                c_rect.top,
                c_rect.width,
                c_rect.height - 48,
            )
            self.profile_cards[profile.id] = selection_rect
            self._draw_profile_card(
                screen,
                c_rect,
                profile,
                profile.id == active_profile_id,
            )

        # 4. Bottom Action Button ("Back to Menu")
        btn_w, btn_h = min(325, card_rect.width - 40), 64
        btn_y = card_rect.bottom - btn_h - 25
        self.back_button = pygame.Rect(cx - btn_w // 2, btn_y, btn_w, btn_h)

        back_btn_font = self._get_adaptive_font(26, bold=True)
        back_btn = Button(self.back_button, label="Back to Menu", variant="yellow", font=back_btn_font, stroke_weight=8)
        back_btn.is_pressed = (self.pressed_button == "back")
        back_btn.draw(screen)

        if self.error_message and self.modal is None:
            error = self._render_adaptive_text(
                self.error_message,
                22,
                (255, 100, 100),
                max_w=card_rect.width - 40,
                default_font=self.app.font_small,
            )
            if error:
                screen.blit(
                    error,
                    error.get_rect(centerx=cx, bottom=self.back_button.top - 8),
                )

        # 5. Render Modals
        if self.modal in ("create", "rename"):
            self._draw_name_modal(screen, width, height)
        elif self.modal in ("reset", "delete"):
            self._draw_confirmation_modal(screen, width, height)
        elif self.modal == "cleanup_warning":
            self._draw_cleanup_warning_modal(screen, width, height)

    def _draw_profile_card(self, screen, rect, profile, is_active: bool) -> None:
        key = f"profile:{profile.id}"
        is_pressed = self.pressed_button == key

        # Card Shadow & Background (#461E58 fill, #7F3F97 border)
        if not is_pressed:
            pygame.draw.rect(screen, (25, 5, 35), rect.move(3, 3), border_radius=20)

        card_fill = (80, 35, 100) if is_pressed else (70, 30, 90)
        border_col = (242, 210, 20) if is_active else (127, 63, 151)
        border_w = 4 if is_active else 3

        pygame.draw.rect(screen, card_fill, rect, border_radius=20)
        pygame.draw.rect(screen, border_col, rect, width=border_w, border_radius=20)

        # Profile Name (Bold cream)
        title_font = getattr(self.app, "font_body", self.app.font_title)
        max_name_w = rect.width - (140 if is_active else 40)
        name_surf = self._render_adaptive_text(
            profile.name,
            24,
            (255, 250, 243),
            max_w=max_name_w,
            bold=True,
            default_font=title_font,
        )
        if name_surf:
            screen.blit(name_surf, name_surf.get_rect(left=rect.left + 20, top=rect.top + 14))

        # Progress / Subtitle
        try:
            summary = self.app.profile_session_summary(profile.id)
        except (ProfileStoreError, OSError) as exc:
            summary = None
            self.error_message = str(exc) or "Profile progress could not be loaded."

        progress_surf = self._render_adaptive_text(
            _summary_text(summary),
            20,
            (227, 198, 236),
            max_w=rect.width - 40,
            default_font=self.app.font_small,
        )
        if progress_surf:
            screen.blit(progress_surf, progress_surf.get_rect(left=rect.left + 20, top=rect.top + 48))

        # Active Badge
        if is_active:
            badge_surf = self._render_adaptive_text(
                "Active",
                18,
                (35, 10, 45),
                default_font=self.app.font_small,
            )
            if badge_surf:
                badge_rect = badge_surf.get_rect()
                badge_rect.inflate_ip(16, 8)
                badge_rect.topright = (rect.right - 18, rect.top + 14)
                pygame.draw.rect(screen, (242, 210, 20), badge_rect, border_radius=10)
                screen.blit(badge_surf, badge_surf.get_rect(center=badge_rect.center))

        # Action Buttons at Bottom of Card (Rename, Reset Progress, Delete)
        divider_y = rect.bottom - 42
        pygame.draw.line(
            screen,
            (127, 63, 151),
            (rect.left + 16, divider_y),
            (rect.right - 16, divider_y),
            width=2,
        )

        button_gap = 8
        button_left = rect.left + 16
        button_width = (rect.width - 32 - 2 * button_gap) // 3
        for index, (action, label) in enumerate(
            (
                ("rename", "Rename"),
                ("reset", "Reset Progress"),
                ("delete", "Delete"),
            )
        ):
            btn_r = pygame.Rect(
                button_left + index * (button_width + button_gap),
                divider_y + 6,
                button_width,
                30,
            )
            self.manage_buttons[(action, profile.id)] = btn_r
            self._draw_management_button(screen, btn_r, label, f"{action}:{profile.id}")

    def _draw_management_button(
        self,
        screen,
        rect: pygame.Rect,
        label: str,
        key: str,
    ) -> None:
        is_pressed = self.pressed_button == key

        fill = (200, 160, 20) if is_pressed else (242, 210, 20)
        stroke = (175, 141, 55)

        pygame.draw.rect(screen, fill, rect, border_radius=8)
        pygame.draw.rect(screen, stroke, rect, width=2, border_radius=8)

        max_w = max(1, rect.width - 6)
        font = getattr(self.app, "font_small", self.app.font_body)
        surface = font.render(label, True, (35, 10, 45))
        if isinstance(surface, pygame.Surface):
            if surface.get_width() > max_w:
                scale_ratio = max_w / surface.get_width()
                new_w = max_w
                new_h = max(1, int(surface.get_height() * scale_ratio))
                surface = pygame.transform.smoothscale(surface, (new_w, new_h))
            screen.blit(surface, surface.get_rect(center=rect.center))

    def _draw_create_card(self, screen, rect: pygame.Rect) -> None:
        is_pressed = self.pressed_button == "create"
        if not is_pressed:
            pygame.draw.rect(screen, (25, 5, 35), rect.move(3, 3), border_radius=20)
        
        fill = (70, 30, 90) if is_pressed else (87, 39, 108)
        pygame.draw.rect(screen, fill, rect, border_radius=20)
        pygame.draw.rect(screen, (242, 210, 20), rect, width=3, border_radius=20)

        card_font_size = max(18, min(30, int(rect.height * 0.32)))
        title_font = getattr(self.app, "font_button", self.app.font_title)
        if title_font and hasattr(title_font, "render"):
            title_font.render("+ Create Profile", True, (242, 210, 20))
        label = self._render_adaptive_text(
            "+ Create Profile",
            card_font_size,
            (242, 210, 20),
            max_w=rect.width - 24,
            bold=True,
        )
        if label:
            screen.blit(label, label.get_rect(center=rect.center))

    def _draw_name_modal(self, screen, width: int, height: int) -> None:
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        dialog = pygame.Rect(
            0,
            0,
            min(1120, width - 80),
            min(640, height - 40),
        )
        dialog.center = (width // 2, height // 2)

        pygame.draw.rect(screen, (25, 5, 35), dialog.move(4, 4), border_radius=30)
        pygame.draw.rect(screen, (87, 39, 108), dialog, border_radius=30)
        pygame.draw.rect(screen, (127, 63, 151), dialog, width=6, border_radius=30)

        is_create = self.modal == "create"
        title_text = "Create Profile" if is_create else "Rename Profile"
        title_size = max(22, min(36, int(dialog.height * 0.10)))
        title_font = getattr(self.app, "font_button", self.app.font_title)
        if title_font and hasattr(title_font, "render"):
            title_font.render(title_text, True, (255, 250, 243))
        title = self._render_adaptive_text(title_text, title_size, (255, 250, 243), max_w=dialog.width - 40, bold=True)
        if title:
            screen.blit(title, title.get_rect(centerx=dialog.centerx, top=dialog.top + 24))

        prompt_size = max(14, min(22, int(dialog.height * 0.05)))
        prompt = self._render_adaptive_text(
            "Enter a name (up to 20 characters)",
            prompt_size,
            (227, 198, 236),
            max_w=dialog.width - 40,
            default_font=self.app.font_small,
        )
        if prompt:
            screen.blit(prompt, prompt.get_rect(centerx=dialog.centerx, top=dialog.top + 80))

        input_rect = pygame.Rect(
            dialog.left + 80,
            dialog.top + 100,
            dialog.width - 160,
            48,
        )
        pygame.draw.rect(screen, (60, 25, 75), input_rect, border_radius=12)
        pygame.draw.rect(screen, (127, 63, 151), input_rect, width=3, border_radius=12)

        input_font_size = max(18, min(28, int(input_rect.height * 0.58)))
        if title_font and hasattr(title_font, "render"):
            title_font.render(self.name_input, True, (242, 210, 20))
        input_surface = self._render_adaptive_text(
            self.name_input,
            input_font_size,
            (242, 210, 20),
            max_w=input_rect.width - 30,
            bold=True,
        )
        if input_surface:
            screen.blit(
                input_surface,
                input_surface.get_rect(left=input_rect.left + 15, centery=input_rect.centery),
            )

        button_width, button_height, gap = 180, 52, 20
        button_y = dialog.bottom - button_height - 20
        self._modal_save_button = pygame.Rect(
            dialog.centerx - gap // 2 - button_width,
            button_y,
            button_width,
            button_height,
        )
        self._modal_cancel_button = pygame.Rect(
            dialog.centerx + gap // 2,
            button_y,
            button_width,
            button_height,
        )

        modal_btn_font_size = max(16, min(26, int(button_height * 0.48)))
        modal_btn_font = self._get_adaptive_font(modal_btn_font_size, bold=True)

        if self.error_message:
            error = self._render_adaptive_text(
                self.error_message,
                20,
                (255, 100, 100),
                max_w=dialog.width - 40,
                default_font=self.app.font_small,
            )
            if error:
                screen.blit(error, error.get_rect(centerx=dialog.centerx, top=input_rect.bottom + 5))

        keyboard_top = input_rect.bottom + 34
        keyboard_bottom = button_y - 18
        keyboard_rect = pygame.Rect(
            dialog.left + 35,
            keyboard_top,
            dialog.width - 70,
            max(1, keyboard_bottom - keyboard_top),
        )
        self.keyboard.draw(screen, keyboard_rect)

        btn_save = Button(
            self._modal_save_button,
            label="Create" if is_create else "Save",
            variant="yellow",
            font=modal_btn_font,
            stroke_weight=6,
        )
        btn_save.is_pressed = (self.pressed_button == "modal_save")
        btn_save.draw(screen)

        btn_cancel = Button(
            self._modal_cancel_button,
            label="Cancel",
            variant="yellow",
            font=modal_btn_font,
            stroke_weight=6,
        )
        btn_cancel.is_pressed = (self.pressed_button == "modal_cancel")
        btn_cancel.draw(screen)

    def _draw_confirmation_modal(self, screen, width: int, height: int) -> None:
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        dialog = pygame.Rect(0, 0, min(640, width - 80), min(300, height - 80))
        dialog.center = (width // 2, height // 2)

        pygame.draw.rect(screen, (25, 5, 35), dialog.move(4, 4), border_radius=30)
        pygame.draw.rect(screen, (87, 39, 108), dialog, border_radius=30)
        pygame.draw.rect(screen, (127, 63, 151), dialog, width=6, border_radius=30)

        is_reset = self.modal == "reset"
        title_text = "Reset Progress" if is_reset else "Delete Profile"
        title_size = max(22, min(36, int(dialog.height * 0.14)))
        title_font = getattr(self.app, "font_button", self.app.font_title)
        if title_font and hasattr(title_font, "render"):
            title_font.render(title_text, True, (255, 250, 243))
        title = self._render_adaptive_text(title_text, title_size, (255, 250, 243), max_w=dialog.width - 40, bold=True)
        if title:
            screen.blit(title, title.get_rect(centerx=dialog.centerx, top=dialog.top + 24))

        message = (
            f"Erase all learning progress for {self.target_profile_name}? The profile will remain."
            if is_reset
            else f"Delete {self.target_profile_name} and all saved progress? This cannot be undone."
        )
        prompt = self._render_adaptive_text(
            message,
            20,
            (227, 198, 236),
            max_w=dialog.width - 40,
            default_font=self.app.font_small,
        )
        if prompt:
            screen.blit(prompt, prompt.get_rect(centerx=dialog.centerx, top=dialog.top + 95))

        if self.error_message:
            error = self._render_adaptive_text(
                self.error_message,
                20,
                (255, 100, 100),
                max_w=dialog.width - 40,
                default_font=self.app.font_small,
            )
            if error:
                screen.blit(error, error.get_rect(centerx=dialog.centerx, top=dialog.top + 130))

        button_width, button_height, gap = 160, 52, 20
        button_y = dialog.bottom - button_height - 24
        self._modal_save_button = pygame.Rect(
            dialog.centerx - gap // 2 - button_width,
            button_y,
            button_width,
            button_height,
        )
        self._modal_cancel_button = pygame.Rect(
            dialog.centerx + gap // 2,
            button_y,
            button_width,
            button_height,
        )

        modal_btn_font_size = max(16, min(26, int(button_height * 0.48)))
        modal_btn_font = self._get_adaptive_font(modal_btn_font_size, bold=True)

        btn_confirm = Button(
            self._modal_save_button,
            label="Reset" if is_reset else "Delete",
            variant="yellow",
            font=modal_btn_font,
            stroke_weight=6,
        )
        btn_confirm.is_pressed = (self.pressed_button == "modal_confirm")
        btn_confirm.draw(screen)

        btn_cancel = Button(
            self._modal_cancel_button,
            label="Cancel",
            variant="yellow",
            font=modal_btn_font,
            stroke_weight=6,
        )
        btn_cancel.is_pressed = (self.pressed_button == "modal_cancel")
        btn_cancel.draw(screen)

    def _draw_cleanup_warning_modal(self, screen, width: int, height: int) -> None:
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        dialog = pygame.Rect(0, 0, min(600, width - 80), min(260, height - 80))
        dialog.center = (width // 2, height // 2)

        pygame.draw.rect(screen, (25, 5, 35), dialog.move(4, 4), border_radius=30)
        pygame.draw.rect(screen, (87, 39, 108), dialog, border_radius=30)
        pygame.draw.rect(screen, (127, 63, 151), dialog, width=6, border_radius=30)

        title_font = getattr(self.app, "font_button", self.app.font_title)
        if title_font and hasattr(title_font, "render"):
            title_font.render("Profile Deleted", True, (255, 250, 243))
        title_size = max(22, min(36, int(dialog.height * 0.14)))
        title = self._render_adaptive_text("Profile Deleted", title_size, (255, 250, 243), max_w=dialog.width - 40, bold=True)
        if title:
            screen.blit(title, title.get_rect(centerx=dialog.centerx, top=dialog.top + 24))

        warning = self._render_adaptive_text(
            self.error_message,
            20,
            (255, 100, 100),
            max_w=dialog.width - 40,
            default_font=self.app.font_small,
        )
        if warning:
            screen.blit(warning, warning.get_rect(centerx=dialog.centerx, top=dialog.top + 90))

        self._modal_save_button = pygame.Rect(0, 0, 160, 52)
        self._modal_save_button.midbottom = (dialog.centerx, dialog.bottom - 24)
        self._modal_cancel_button = None

        modal_btn_font_size = max(16, min(26, int(52 * 0.48)))
        modal_btn_font = self._get_adaptive_font(modal_btn_font_size, bold=True)

        btn_ok = Button(
            self._modal_save_button,
            label="OK",
            variant="yellow",
            font=modal_btn_font,
            stroke_weight=6,
        )
        btn_ok.is_pressed = (self.pressed_button == "modal_ack")
        btn_ok.draw(screen)
