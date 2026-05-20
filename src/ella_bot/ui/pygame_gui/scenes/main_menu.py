import pygame
from ella_bot.ui.pygame_gui.scene import BaseScene
from ella_bot.ui.pygame_gui.ui_helpers import draw_menu_button

class MainMenuScene(BaseScene):
    def __init__(self, app):
        super().__init__(app)
        self.pressed_button = None
        self.show_exit_confirm = False

        self.menu_start_button = None
        self.menu_settings_button = None
        self.menu_exit_button = None
        self.menu_confirm_yes_button = None
        self.menu_confirm_no_button = None

        self.menu_bg_color = (245, 205, 214)
        self.button_bg_color = (248, 111, 150)
        self.button_text_color = (255, 255, 255)
        self.button_outline_color = (0, 0, 0)

    def on_enter(self) -> None:
        self.show_exit_confirm = False
        self.pressed_button = None

    def handle_event(self, event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_mouse_down(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._handle_mouse_up(event.pos)

    def _handle_mouse_down(self, mouse_pos) -> None:
        if self.show_exit_confirm:
            if self.menu_confirm_yes_button and self.menu_confirm_yes_button.collidepoint(mouse_pos):
                self.pressed_button = "confirm_yes"
                return
            if self.menu_confirm_no_button and self.menu_confirm_no_button.collidepoint(mouse_pos):
                self.pressed_button = "confirm_no"
                return

        if self.menu_start_button and self.menu_start_button.collidepoint(mouse_pos):
            self.pressed_button = "start"
        elif self.menu_settings_button and self.menu_settings_button.collidepoint(mouse_pos):
            self.pressed_button = "settings"
        elif self.menu_exit_button and self.menu_exit_button.collidepoint(mouse_pos):
            self.pressed_button = "exit"

    def _handle_mouse_up(self, mouse_pos) -> None:
        try:
            if self.pressed_button == "start" and self.menu_start_button and self.menu_start_button.collidepoint(mouse_pos):
                self.app.switch_scene("reading_prompt")
                self.app.active_scene._start_attempt()
            elif self.pressed_button == "settings" and self.menu_settings_button and self.menu_settings_button.collidepoint(mouse_pos):
                self.app.switch_scene("settings")
            elif self.pressed_button == "exit" and self.menu_exit_button and self.menu_exit_button.collidepoint(mouse_pos):
                self.show_exit_confirm = True
            elif self.pressed_button == "confirm_yes" and self.menu_confirm_yes_button and self.menu_confirm_yes_button.collidepoint(mouse_pos):
                self.app.running = False
            elif self.pressed_button == "confirm_no" and self.menu_confirm_no_button and self.menu_confirm_no_button.collidepoint(mouse_pos):
                self.show_exit_confirm = False
        finally:
            self.pressed_button = None

    def render(self) -> None:
        screen = self.app.screen
        width, height = screen.get_size()

        screen.fill(self.menu_bg_color)

        title_surf = self.app.font_title.render("Welcome to E.L.L.A.", True, (0, 0, 0))
        title_rect = title_surf.get_rect(center=(width // 2, int(height * 0.15)))
        screen.blit(title_surf, title_rect)

        button_width = 320
        button_height = 110
        button_y_start = int(height * 0.32)
        button_spacing = 140
        center_x = width // 2

        self.menu_start_button = pygame.Rect(center_x - button_width // 2, button_y_start, button_width, button_height)
        draw_menu_button(screen, pygame, self.menu_start_button, "Start", self.pressed_button == "start", self.button_bg_color, self.button_text_color, self.button_outline_color, font=self.app.font_button)

        self.menu_settings_button = pygame.Rect(center_x - button_width // 2, button_y_start + button_spacing, button_width, button_height)
        draw_menu_button(screen, pygame, self.menu_settings_button, "Settings", self.pressed_button == "settings", self.button_bg_color, self.button_text_color, self.button_outline_color, font=self.app.font_button)

        self.menu_exit_button = pygame.Rect(center_x - button_width // 2, button_y_start + button_spacing * 2, button_width, button_height)
        draw_menu_button(screen, pygame, self.menu_exit_button, "Exit", self.pressed_button == "exit", self.button_bg_color, self.button_text_color, self.button_outline_color, font=self.app.font_button)

        if self.show_exit_confirm:
            overlay = pygame.Surface((width, height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            screen.blit(overlay, (0, 0))

            dialog_w = int(width * 0.8)
            dialog_h = int(height * 0.32)
            dialog_x = (width - dialog_w) // 2
            dialog_y = (height - dialog_h) // 2
            dialog_rect = pygame.Rect(dialog_x, dialog_y, dialog_w, dialog_h)
            pygame.draw.rect(screen, (255, 255, 255), dialog_rect, border_radius=12)
            pygame.draw.rect(screen, (0, 0, 0), dialog_rect, width=6, border_radius=12)

            msg = "Are you sure you want to exit?"
            msg_surf = self.app.font_body.render(msg, True, (0, 0, 0))
            msg_rect = msg_surf.get_rect(center=(width // 2, dialog_y + int(dialog_h * 0.35)))
            screen.blit(msg_surf, msg_rect)

            btn_w = 160
            btn_h = 70
            btn_y = dialog_y + dialog_h - btn_h - 24
            yes_rect = pygame.Rect((width // 2) - btn_w - 12, btn_y, btn_w, btn_h)
            no_rect = pygame.Rect((width // 2) + 12, btn_y, btn_w, btn_h)
            self.menu_confirm_yes_button = yes_rect
            self.menu_confirm_no_button = no_rect

            yes_bg = (251, 165, 193) if self.pressed_button == "confirm_yes" else self.button_bg_color
            pygame.draw.rect(screen, yes_bg, yes_rect, border_radius=12)
            pygame.draw.rect(screen, self.button_outline_color, yes_rect, width=6, border_radius=12)
            yes_text = self.app.font_body.render("Yes", True, (255, 255, 255))
            screen.blit(yes_text, yes_text.get_rect(center=yes_rect.center))

            no_bg = (251, 165, 193) if self.pressed_button == "confirm_no" else self.button_bg_color
            pygame.draw.rect(screen, no_bg, no_rect, border_radius=12)
            pygame.draw.rect(screen, self.button_outline_color, no_rect, width=6, border_radius=12)
            no_text = self.app.font_body.render("No", True, (255, 255, 255))
            screen.blit(no_text, no_text.get_rect(center=no_rect.center))
