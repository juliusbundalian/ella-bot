import io
from datetime import datetime

import pygame

from ella_bot.ui.pygame_gui.scene import BaseScene
from ella_bot.ui.pygame_gui.bot_sprite import BotSprite
from ella_bot.utils.file_utils import resolve_asset_path

_CARD_BG = (0, 0, 0)
_WHITE = (255, 255, 255)
_OUTER_BORDER = (94, 42, 59)
_INNER_BORDER = (255, 185, 207)
_BTN_FILL = (255, 182, 193)
_BTN_OUTLINE = (94, 42, 59)
_BTN_PRESSED = (251, 165, 193)


class MainMenuScene(BaseScene):
    def __init__(self, app):
        super().__init__(app)
        self.pressed_button = None
        self.show_exit_confirm = False
        self.show_resume_prompt = False
        self.resume_summary = None

        self.menu_start_button = None
        self.menu_exit_button = None
        self.menu_gear_button = None
        self.menu_confirm_yes_button = None
        self.menu_confirm_no_button = None
        self.resume_continue_button = None
        self.resume_new_button = None
        self.resume_cancel_button = None

        self.bot = BotSprite()
        self._title_img = None
        self._settings_icon = None

    def on_enter(self) -> None:
        self.show_exit_confirm = False
        self.show_resume_prompt = False
        self.resume_summary = None
        self.pressed_button = None

    def _do_start(self) -> None:
        summary = self.app.saved_session_summary()
        if summary is None:
            self.app.switch_scene("level_selection")
            return
        self.resume_summary = summary
        self.show_resume_prompt = True

    def _do_continue(self) -> None:
        phase = self.app.continue_saved_session()
        if phase == "reading":
            self.show_resume_prompt = False
            self.app.switch_scene("reading_prompt")
            self.app.active_scene._start_attempt()
        elif phase == "results":
            self.show_resume_prompt = False
            self.app.switch_scene("results")

    def _do_new_session(self) -> None:
        self.show_resume_prompt = False
        self.app.switch_scene("level_selection")

    def _load_assets(self) -> None:
        if self._title_img is None:
            try:
                raw = pygame.image.load(
                    str(resolve_asset_path("assets/menu-title.png"))
                ).convert_alpha()
                # Composite onto white to prevent dark fringing during smoothscale
                # (transparent pixels have black RGB which bleeds into edges)
                white = pygame.Surface(raw.get_size())
                white.fill((255, 255, 255))
                white.blit(raw, (0, 0))
                self._title_img = white
            except Exception:
                self._title_img = False

        if self._settings_icon is None:
            try:
                svg_text = resolve_asset_path("assets/ic_settings.svg").read_text()
                svg_sized = svg_text.replace('height="24px"', 'height="48px"').replace('width="24px"', 'width="48px"')
                self._settings_icon = pygame.image.load(io.BytesIO(svg_sized.encode())).convert_alpha()
            except Exception:
                self._settings_icon = False

    def update(self, now_ms: int) -> None:
        self.bot.update(now_ms, "idle")

    def handle_event(self, event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_mouse_down(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._handle_mouse_up(event.pos)

    def _handle_mouse_down(self, mouse_pos) -> None:
        if self.show_resume_prompt:
            if self.resume_continue_button and self.resume_continue_button.collidepoint(mouse_pos):
                self.pressed_button = "resume_continue"
            elif self.resume_new_button and self.resume_new_button.collidepoint(mouse_pos):
                self.pressed_button = "resume_new"
            elif self.resume_cancel_button and self.resume_cancel_button.collidepoint(mouse_pos):
                self.pressed_button = "resume_cancel"
            return

        if self.show_exit_confirm:
            if self.menu_confirm_yes_button and self.menu_confirm_yes_button.collidepoint(mouse_pos):
                self.pressed_button = "confirm_yes"
            elif self.menu_confirm_no_button and self.menu_confirm_no_button.collidepoint(mouse_pos):
                self.pressed_button = "confirm_no"
            return

        if self.menu_start_button and self.menu_start_button.collidepoint(mouse_pos):
            self.pressed_button = "start"
        elif self.menu_exit_button and self.menu_exit_button.collidepoint(mouse_pos):
            self.pressed_button = "exit"
        elif self.menu_gear_button and self.menu_gear_button.collidepoint(mouse_pos):
            self.pressed_button = "gear"

    def _handle_mouse_up(self, mouse_pos) -> None:
        try:
            if self.pressed_button == "resume_continue" and self.resume_continue_button and self.resume_continue_button.collidepoint(mouse_pos):
                self._do_continue()
            elif self.pressed_button == "resume_new" and self.resume_new_button and self.resume_new_button.collidepoint(mouse_pos):
                self._do_new_session()
            elif self.pressed_button == "resume_cancel" and self.resume_cancel_button and self.resume_cancel_button.collidepoint(mouse_pos):
                self.show_resume_prompt = False
            elif self.pressed_button == "start" and self.menu_start_button and self.menu_start_button.collidepoint(mouse_pos):
                self._do_start()
            elif self.pressed_button == "exit" and self.menu_exit_button and self.menu_exit_button.collidepoint(mouse_pos):
                self.show_exit_confirm = True
            elif self.pressed_button == "gear" and self.menu_gear_button and self.menu_gear_button.collidepoint(mouse_pos):
                self.app.switch_scene("settings")
            elif self.pressed_button == "confirm_yes" and self.menu_confirm_yes_button and self.menu_confirm_yes_button.collidepoint(mouse_pos):
                self.app.running = False
            elif self.pressed_button == "confirm_no" and self.menu_confirm_no_button and self.menu_confirm_no_button.collidepoint(mouse_pos):
                self.show_exit_confirm = False
        finally:
            self.pressed_button = None

    def _draw_button(self, screen, rect, label, key, radius=20) -> None:
        is_pressed = self.pressed_button == key
        bg = _BTN_PRESSED if is_pressed else _BTN_FILL
        if not is_pressed:
            # Shadow shift creates thick right+bottom (shadow 4px + outline 2px = 6px)
            # while top+left show only the 2px outline
            pygame.draw.rect(screen, _BTN_OUTLINE,
                             pygame.Rect(rect.left + 4, rect.top + 4, rect.width, rect.height),
                             border_radius=radius)
        pygame.draw.rect(screen, bg, rect, border_radius=radius)
        pygame.draw.rect(screen, _BTN_OUTLINE, rect, width=2, border_radius=radius)
        surf = self.app.font_body.render(label, True, _WHITE)
        screen.blit(surf, surf.get_rect(center=rect.center))

    def render(self) -> None:
        screen = self.app.screen
        width, height = screen.get_size()
        self._load_assets()

        prompt_rect = pygame.Rect(0, 0, width, height)

        # --- card frame (identical to reading prompt) ---
        pygame.draw.rect(screen, _CARD_BG, prompt_rect, border_radius=0)
        middle_rect = prompt_rect.inflate(-24, -24)
        pygame.draw.rect(screen, _WHITE, middle_rect, border_radius=56)
        inner_rect = prompt_rect.inflate(-64, -64)
        pygame.draw.rect(screen, _WHITE, inner_rect, border_radius=36)

        # --- title image ---
        if self._title_img:
            max_title_w = int(inner_rect.width * 0.58)
            raw_w, raw_h = self._title_img.get_size()
            scale = max_title_w / raw_w
            title_w = max_title_w
            title_h = int(raw_h * scale)
            title_surf = pygame.transform.smoothscale(self._title_img, (title_w, title_h))
            title_rect = title_surf.get_rect(centerx=inner_rect.centerx, top=inner_rect.top + 24)
            screen.blit(title_surf, title_rect)
            content_top = title_rect.bottom + 18
        else:
            content_top = inner_rect.top + 80

        # --- Start and Exit buttons ---
        btn_w, btn_h, btn_gap = 300, 85, 22
        btn_x = inner_rect.centerx - btn_w // 2
        self.menu_start_button = pygame.Rect(btn_x, content_top, btn_w, btn_h)
        self.menu_exit_button = pygame.Rect(btn_x, content_top + btn_h + btn_gap, btn_w, btn_h)
        self._draw_button(screen, self.menu_start_button, "Start", "start")
        self._draw_button(screen, self.menu_exit_button, "Exit", "exit")

        # --- Bot (bottom-right, same as reading prompt) ---
        self.bot.draw(screen, inner_rect)

        # --- Outer/inner pink borders (drawn on top so they frame everything) ---
        pygame.draw.rect(screen, _OUTER_BORDER, prompt_rect, width=12, border_radius=68)
        pygame.draw.rect(screen, _INNER_BORDER, inner_rect, width=12, border_radius=36)

        # --- Gear button (bottom-left of inner_rect) ---
        gear_size = 72
        gear_pad = 24
        self.menu_gear_button = pygame.Rect(
            inner_rect.left + gear_pad,
            inner_rect.bottom - gear_pad - gear_size,
            gear_size, gear_size,
        )
        gear_bg = _BTN_PRESSED if self.pressed_button == "gear" else _BTN_FILL
        if self.pressed_button != "gear":
            pygame.draw.rect(screen, _BTN_OUTLINE,
                             pygame.Rect(self.menu_gear_button.left + 4, self.menu_gear_button.top + 4,
                                         self.menu_gear_button.width, self.menu_gear_button.height),
                             border_radius=16)
        pygame.draw.rect(screen, gear_bg, self.menu_gear_button, border_radius=16)
        pygame.draw.rect(screen, _BTN_OUTLINE, self.menu_gear_button, width=2, border_radius=16)
        if self._settings_icon:
            screen.blit(self._settings_icon, self._settings_icon.get_rect(center=self.menu_gear_button.center))
        else:
            gear_surf = self.app.font_body.render("⚙", True, _WHITE)
            screen.blit(gear_surf, gear_surf.get_rect(center=self.menu_gear_button.center))

        if self.show_exit_confirm:
            self._draw_exit_confirm(screen, width, height)
        elif self.show_resume_prompt:
            self._draw_resume_prompt(screen, width, height)

    def _draw_resume_prompt(self, screen, width, height) -> None:
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        dlg_w = min(760, int(width * 0.68))
        dlg_h = min(390, int(height * 0.58))
        dlg_rect = pygame.Rect(
            (width - dlg_w) // 2,
            (height - dlg_h) // 2,
            dlg_w,
            dlg_h,
        )
        pygame.draw.rect(screen, _WHITE, dlg_rect, border_radius=24)
        pygame.draw.rect(screen, _BTN_OUTLINE, dlg_rect, width=4, border_radius=24)

        title = self.app.font_title.render("Saved Session", True, (50, 50, 50))
        screen.blit(title, title.get_rect(centerx=dlg_rect.centerx, top=dlg_rect.top + 30))

        summary = self.resume_summary
        if summary is not None:
            details = f"Level {summary.level.upper()}  •  Item {summary.item_number}"
            detail_surf = self.app.font_body.render(details, True, (50, 50, 50))
            screen.blit(
                detail_surf,
                detail_surf.get_rect(centerx=dlg_rect.centerx, top=dlg_rect.top + 120),
            )
            try:
                saved = datetime.fromisoformat(summary.saved_at).astimezone()
                saved_text = saved.strftime("Saved %b %d, %Y at %I:%M %p")
            except (TypeError, ValueError):
                saved_text = f"Saved {summary.saved_at}"
            saved_surf = self.app.font_small.render(saved_text, True, (78, 78, 78))
            screen.blit(
                saved_surf,
                saved_surf.get_rect(centerx=dlg_rect.centerx, top=dlg_rect.top + 168),
            )

        btn_gap = 16
        btn_w = min(190, (dlg_w - 80 - 2 * btn_gap) // 3)
        btn_h = 66
        total_w = 3 * btn_w + 2 * btn_gap
        btn_x = dlg_rect.centerx - total_w // 2
        btn_y = dlg_rect.bottom - btn_h - 34
        self.resume_continue_button = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
        self.resume_new_button = pygame.Rect(
            btn_x + btn_w + btn_gap,
            btn_y,
            btn_w,
            btn_h,
        )
        self.resume_cancel_button = pygame.Rect(
            btn_x + 2 * (btn_w + btn_gap),
            btn_y,
            btn_w,
            btn_h,
        )
        self._draw_button(
            screen,
            self.resume_continue_button,
            "Continue",
            "resume_continue",
        )
        self._draw_button(
            screen,
            self.resume_new_button,
            "New Session",
            "resume_new",
        )
        self._draw_button(
            screen,
            self.resume_cancel_button,
            "Cancel",
            "resume_cancel",
        )

    def _draw_exit_confirm(self, screen, width, height) -> None:
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))

        dlg_w = int(width * 0.55)
        dlg_h = int(height * 0.32)
        dlg_x = (width - dlg_w) // 2
        dlg_y = (height - dlg_h) // 2
        dlg_rect = pygame.Rect(dlg_x, dlg_y, dlg_w, dlg_h)
        pygame.draw.rect(screen, _WHITE, dlg_rect, border_radius=20)
        pygame.draw.rect(screen, _BTN_OUTLINE, dlg_rect, width=4, border_radius=20)

        msg = self.app.font_body.render("Are you sure you want to exit?", True, (50, 50, 50))
        screen.blit(msg, msg.get_rect(center=(width // 2, dlg_y + int(dlg_h * 0.35))))

        btn_w, btn_h = 150, 62
        btn_y = dlg_y + dlg_h - btn_h - 22
        yes_rect = pygame.Rect(width // 2 - btn_w - 14, btn_y, btn_w, btn_h)
        no_rect = pygame.Rect(width // 2 + 14, btn_y, btn_w, btn_h)
        self.menu_confirm_yes_button = yes_rect
        self.menu_confirm_no_button = no_rect
        self._draw_button(screen, yes_rect, "Yes", "confirm_yes")
        self._draw_button(screen, no_rect, "No", "confirm_no")
