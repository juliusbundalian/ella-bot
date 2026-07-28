from __future__ import annotations

import pygame

from ella_bot.services.profile_store import MAX_PROFILES, ProfileStoreError
from ella_bot.ui.pygame_gui.scene import BaseScene


_CARD_BG = (0, 0, 0)
_WHITE = (255, 255, 255)
_TEXT = (50, 50, 50)
_TEXT_MUTED = (95, 78, 84)
_OUTER_BORDER = (94, 42, 59)
_INNER_BORDER = (255, 185, 207)
_BTN_FILL = (255, 182, 193)
_BTN_PRESSED = (251, 165, 193)
_BTN_OUTLINE = (94, 42, 59)
_CARD_FILL = (255, 246, 249)
_SELECTED_FILL = (117, 67, 84)
_ERROR = (165, 34, 62)


def _summary_text(summary) -> str:
    if summary is None:
        return 'Ready to begin'
    level = summary.level.upper()
    if summary.phase == 'results':
        return f'Level {level} - Results'
    return f'Level {level} - Item {summary.item_number}'


class ProfilesScene(BaseScene):
    '''Browse learner profiles and create or select one.'''

    def __init__(self, app):
        super().__init__(app)
        self.profile_cards: dict[str, pygame.Rect] = {}
        self.manage_buttons: dict[tuple[str, str], pygame.Rect] = {}
        self.create_button: pygame.Rect | None = None
        self.back_button: pygame.Rect | None = None
        self.modal: str | None = None
        self.target_profile_id: str | None = None
        self.name_input = ''
        self.error_message = ''
        self.pressed_button: str | None = None

        self._profile_card_rects: dict[str, pygame.Rect] = {}
        self._modal_save_button: pygame.Rect | None = None
        self._modal_cancel_button: pygame.Rect | None = None

    def on_enter(self) -> None:
        self._close_modal()
        self.error_message = ''
        self.pressed_button = None

    def on_exit(self) -> None:
        pygame.key.stop_text_input()
        self.pressed_button = None

    def _open_create(self) -> None:
        if len(self.app.profiles()) >= MAX_PROFILES:
            return
        self.modal = 'create'
        self.target_profile_id = None
        self.name_input = ''
        self.error_message = ''
        self.pressed_button = None
        pygame.key.start_text_input()

    def _close_modal(self) -> None:
        pygame.key.stop_text_input()
        self.modal = None
        self.target_profile_id = None
        self.name_input = ''
        self.error_message = ''
        self.pressed_button = None

    def _save_name(self) -> None:
        try:
            self.app.create_profile(self.name_input)
        except (ProfileStoreError, OSError) as exc:
            self.error_message = str(exc) or 'Profile could not be saved.'
            return
        self._close_modal()
        self.app.switch_scene('level_selection')

    def _select_profile(self, profile_id: str) -> None:
        try:
            self.app.select_profile(profile_id)
        except (ProfileStoreError, OSError) as exc:
            self.error_message = str(exc) or 'Profile could not be selected.'
            return
        pygame.key.stop_text_input()
        self.app.switch_scene('main_menu')

    def _go_back(self) -> None:
        pygame.key.stop_text_input()
        self.app.switch_scene('main_menu')

    def handle_event(self, event) -> None:
        if event.type == pygame.TEXTINPUT and self.modal == 'create':
            candidate = self.name_input + event.text
            if len(candidate) <= 20:
                self.name_input = candidate
                self.error_message = ''
            return

        if event.type == pygame.KEYDOWN:
            if self.modal == 'create':
                if event.key == pygame.K_BACKSPACE:
                    self.name_input = self.name_input[:-1]
                    self.error_message = ''
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
        if self.modal == 'create':
            if self._modal_save_button and self._modal_save_button.collidepoint(mouse_pos):
                self.pressed_button = 'modal_save'
            elif self._modal_cancel_button and self._modal_cancel_button.collidepoint(mouse_pos):
                self.pressed_button = 'modal_cancel'
            return

        for profile_id, rect in self.profile_cards.items():
            if rect.collidepoint(mouse_pos):
                self.pressed_button = f'profile:{profile_id}'
                return
        if self.create_button and self.create_button.collidepoint(mouse_pos):
            self.pressed_button = 'create'
        elif self.back_button and self.back_button.collidepoint(mouse_pos):
            self.pressed_button = 'back'

    def _handle_mouse_up(self, mouse_pos) -> None:
        pressed = self.pressed_button
        self.pressed_button = None
        if self.modal == 'create':
            if (
                pressed == 'modal_save'
                and self._modal_save_button
                and self._modal_save_button.collidepoint(mouse_pos)
            ):
                self._save_name()
            elif (
                pressed == 'modal_cancel'
                and self._modal_cancel_button
                and self._modal_cancel_button.collidepoint(mouse_pos)
            ):
                self._close_modal()
            return

        if (
            pressed == 'create'
            and self.create_button
            and self.create_button.collidepoint(mouse_pos)
        ):
            self._open_create()
        elif pressed == 'back' and self.back_button and self.back_button.collidepoint(mouse_pos):
            self._go_back()
        elif pressed and pressed.startswith('profile:'):
            profile_id = pressed.split(':', 1)[1]
            rect = self.profile_cards.get(profile_id)
            if rect and rect.collidepoint(mouse_pos):
                self._select_profile(profile_id)

    def _draw_button(
        self,
        screen,
        rect: pygame.Rect,
        label: str,
        key: str,
        *,
        font=None,
    ) -> None:
        is_pressed = self.pressed_button == key
        fill = _BTN_PRESSED if is_pressed else _BTN_FILL
        if not is_pressed:
            pygame.draw.rect(
                screen,
                _BTN_OUTLINE,
                rect.move(4, 4),
                border_radius=16,
            )
        pygame.draw.rect(screen, fill, rect, border_radius=16)
        pygame.draw.rect(screen, _BTN_OUTLINE, rect, width=2, border_radius=16)
        label_font = font or self.app.font_button
        surface = label_font.render(label, True, _WHITE)
        screen.blit(surface, surface.get_rect(center=rect.center))

    def render(self) -> None:
        screen = self.app.screen
        width, height = screen.get_size()
        outer_rect = pygame.Rect(0, 0, width, height)
        inner_rect = outer_rect.inflate(-64, -64)

        pygame.draw.rect(screen, _CARD_BG, outer_rect)
        pygame.draw.rect(screen, _WHITE, outer_rect.inflate(-24, -24), border_radius=56)
        pygame.draw.rect(screen, _WHITE, inner_rect, border_radius=36)

        title = self.app.font_title.render('Choose a Profile', True, _TEXT)
        screen.blit(title, title.get_rect(centerx=inner_rect.centerx, top=inner_rect.top + 18))
        subtitle = self.app.font_body.render(
            'Pick a learner or create a new profile.',
            True,
            _TEXT_MUTED,
        )
        screen.blit(
            subtitle,
            subtitle.get_rect(centerx=inner_rect.centerx, top=inner_rect.top + 82),
        )

        profiles = tuple(self.app.profiles())[:MAX_PROFILES]
        active = self.app.active_profile()
        active_profile_id = active.id if active is not None else None
        entries: list[tuple[str, object | None]] = [
            ('profile', profile) for profile in profiles
        ]
        if len(profiles) < MAX_PROFILES:
            entries.append(('create', None))

        self.profile_cards = {}
        self.manage_buttons = {}
        self.create_button = None
        self._profile_card_rects = {}

        grid_left = inner_rect.left + 74
        grid_top = inner_rect.top + 130
        grid_width = inner_rect.width - 148
        grid_bottom = inner_rect.bottom - 92
        column_gap = 22
        row_gap = 12
        card_width = (grid_width - column_gap) // 2
        card_height = (grid_bottom - grid_top - 2 * row_gap) // 3

        for index, (kind, value) in enumerate(entries):
            row, column = divmod(index, 2)
            card_rect = pygame.Rect(
                grid_left + column * (card_width + column_gap),
                grid_top + row * (card_height + row_gap),
                card_width,
                card_height,
            )
            if kind == 'create':
                self.create_button = card_rect
                self._draw_create_card(screen, card_rect)
                continue

            profile = value
            self._profile_card_rects[profile.id] = card_rect
            selection_rect = pygame.Rect(
                card_rect.left,
                card_rect.top,
                card_rect.width,
                card_rect.height - 48,
            )
            self.profile_cards[profile.id] = selection_rect
            self._draw_profile_card(
                screen,
                card_rect,
                profile,
                profile.id == active_profile_id,
            )

        self.back_button = pygame.Rect(inner_rect.left + 36, inner_rect.bottom - 72, 150, 54)
        self._draw_button(
            screen,
            self.back_button,
            'Back',
            'back',
            font=self.app.font_body,
        )
        if self.error_message and self.modal is None:
            error = self.app.font_small.render(self.error_message, True, _ERROR)
            screen.blit(
                error,
                error.get_rect(centerx=inner_rect.centerx, centery=self.back_button.centery),
            )
        elif len(profiles) >= MAX_PROFILES:
            capacity = self.app.font_small.render('5 of 5 profiles', True, _TEXT_MUTED)
            screen.blit(
                capacity,
                capacity.get_rect(right=inner_rect.right - 40, centery=self.back_button.centery),
            )

        pygame.draw.rect(screen, _OUTER_BORDER, outer_rect, width=12, border_radius=68)
        pygame.draw.rect(screen, _INNER_BORDER, inner_rect, width=12, border_radius=36)

        if self.modal == 'create':
            self._draw_create_modal(screen, width, height)

    def _draw_profile_card(self, screen, rect, profile, is_active: bool) -> None:
        key = f'profile:{profile.id}'
        is_pressed = self.pressed_button == key
        if not is_pressed:
            pygame.draw.rect(screen, _BTN_OUTLINE, rect.move(4, 4), border_radius=18)
        fill = _BTN_PRESSED if is_pressed else _CARD_FILL
        pygame.draw.rect(screen, fill, rect, border_radius=18)
        pygame.draw.rect(screen, _BTN_OUTLINE, rect, width=2, border_radius=18)

        name = self.app.font_body.render(profile.name, True, _TEXT)
        screen.blit(name, name.get_rect(left=rect.left + 22, top=rect.top + 14))
        try:
            summary = self.app.profile_session_summary(profile.id)
        except (ProfileStoreError, OSError) as exc:
            summary = None
            self.error_message = str(exc) or 'Profile progress could not be loaded.'
        progress = self.app.font_small.render(_summary_text(summary), True, _TEXT_MUTED)
        screen.blit(progress, progress.get_rect(left=rect.left + 22, top=rect.top + 52))

        divider_y = rect.bottom - 48
        pygame.draw.line(
            screen,
            _INNER_BORDER,
            (rect.left + 18, divider_y),
            (rect.right - 18, divider_y),
            width=2,
        )
        if is_active:
            selected = self.app.font_small.render('Selected', True, _WHITE)
            pill = selected.get_rect()
            pill.inflate_ip(22, 10)
            pill.midright = (rect.right - 18, rect.top + 30)
            pygame.draw.rect(screen, _SELECTED_FILL, pill, border_radius=12)
            screen.blit(selected, selected.get_rect(center=pill.center))

    def _draw_create_card(self, screen, rect: pygame.Rect) -> None:
        is_pressed = self.pressed_button == 'create'
        if not is_pressed:
            pygame.draw.rect(screen, _BTN_OUTLINE, rect.move(4, 4), border_radius=18)
        fill = _BTN_PRESSED if is_pressed else _BTN_FILL
        pygame.draw.rect(screen, fill, rect, border_radius=18)
        pygame.draw.rect(screen, _BTN_OUTLINE, rect, width=2, border_radius=18)
        label = self.app.font_body.render('+ Create Profile', True, _WHITE)
        screen.blit(label, label.get_rect(center=rect.center))

    def _draw_create_modal(self, screen, width: int, height: int) -> None:
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        dialog = pygame.Rect(0, 0, min(680, width - 120), min(390, height - 120))
        dialog.center = (width // 2, height // 2)
        pygame.draw.rect(screen, _WHITE, dialog, border_radius=24)
        pygame.draw.rect(screen, _BTN_OUTLINE, dialog, width=4, border_radius=24)

        title = self.app.font_title.render('Create Profile', True, _TEXT)
        screen.blit(title, title.get_rect(centerx=dialog.centerx, top=dialog.top + 28))
        prompt = self.app.font_small.render(
            'Enter a name (up to 20 characters)',
            True,
            _TEXT_MUTED,
        )
        screen.blit(prompt, prompt.get_rect(centerx=dialog.centerx, top=dialog.top + 105))

        input_rect = pygame.Rect(dialog.left + 64, dialog.top + 140, dialog.width - 128, 58)
        pygame.draw.rect(screen, _CARD_FILL, input_rect, border_radius=12)
        pygame.draw.rect(screen, _BTN_OUTLINE, input_rect, width=2, border_radius=12)
        input_surface = self.app.font_body.render(self.name_input, True, _TEXT)
        screen.blit(
            input_surface,
            input_surface.get_rect(left=input_rect.left + 15, centery=input_rect.centery),
        )

        if self.error_message:
            error = self.app.font_small.render(self.error_message, True, _ERROR)
            screen.blit(error, error.get_rect(centerx=dialog.centerx, top=input_rect.bottom + 10))

        button_width, button_height, gap = 180, 58, 22
        button_y = dialog.bottom - button_height - 28
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
        self._draw_button(
            screen,
            self._modal_save_button,
            'Create',
            'modal_save',
            font=self.app.font_body,
        )
        self._draw_button(
            screen,
            self._modal_cancel_button,
            'Cancel',
            'modal_cancel',
            font=self.app.font_body,
        )
