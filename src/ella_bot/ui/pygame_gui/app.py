import queue
import threading
import time
from typing import Dict, List, Optional

from ella_bot.ui.pygame_gui.animator import AvatarAnimator
from ella_bot.ui.pygame_gui.config import GUIConfig
from ella_bot.ui.pygame_gui.scenes.intro import IntroScene
from ella_bot.ui.pygame_gui.scenes.main_menu import MainMenuScene
from ella_bot.ui.pygame_gui.scenes.reading_prompt import ReadingPromptScene
from ella_bot.ui.pygame_gui.scenes.settings import SettingsScene
from ella_bot.services.attempt_runner import AttemptViewModel
from ella_bot.services.session_manager import SessionManager

class EllaGUIApp:
    """Pygame GUI loop for E.L.L.A. serving as a SceneManager."""

    def __init__(
        self,
        expected_sentence: str,
        asr,
        tts,
        audio_feedback: bool,
        pronunciation_overrides: Dict[str, str],
        hard_sentences: Optional[List[str]] = None,
        start_level: str = "1a",
        config: Optional[GUIConfig] = None,
    ) -> None:
        self.asr = asr
        self.tts = tts
        self.audio_feedback = audio_feedback
        self.pronunciation_overrides = pronunciation_overrides
        self.config = config or GUIConfig()

        self.session = SessionManager.from_config_file(
            start_level=start_level,
            hard_sentences=hard_sentences,
            seed_sentence=expected_sentence,
        )

        self.state = "idle"
        self.message = ""
        self.latest_attempt: Optional[AttemptViewModel] = None
        self.event_queue: queue.Queue = queue.Queue()
        self.prompt_active = False

        self.running = False
        self.screen = None
        self.clock = None
        self.animator = None
        
        # Scenes will be initialized after pygame init
        self.scenes = {}
        self.active_scene = None

    # --- Property delegators for session state ---

    @property
    def expected_sentence(self) -> str:
        return self.session.expected_sentence

    @expected_sentence.setter
    def expected_sentence(self, value: str) -> None:
        self.session.expected_sentence = value

    @property
    def current_level(self) -> str:
        return self.session.current_level

    @property
    def completed_in_level(self) -> int:
        return self.session.completed_in_level

    @completed_in_level.setter
    def completed_in_level(self, value: int) -> None:
        self.session.completed_in_level = value

    @property
    def level_goal(self) -> int:
        return self.session.level_goal

    @level_goal.setter
    def level_goal(self, value: int) -> None:
        self.session.level_goal = value

    # --- Thin delegators for session methods ---

    def _current_item_number(self) -> int:
        return self.session.current_item_number()

    def _build_start_announcement(self) -> str:
        return self.session.build_start_announcement()

    def _get_sys_font(self, size, bold=False):
        """Helper to get a system font with cross-platform fallbacks."""
        import pygame
        fonts = ["Changa One","Avenir Next", "Segoe UI", "Arial", "Verdana", "sans-serif"]
        return pygame.font.SysFont(fonts, size, bold=bold)

    def _prompt_font(self, pygame_module):
        width, height = self.screen.get_size()
        # Use cached fonts based on sentence length
        if len(self.expected_sentence) <= 3:
            return self.font_prompt_large
        if len(self.expected_sentence.split()) <= 6:
            return self.font_prompt_medium
        return self.font_prompt_small

    def _pick_sentence_for_level(self, level: str) -> str:
        return self.session.pick_sentence_for_level(level)

    def _display_level_name(self) -> str:
        return self.session.display_level_name()

    def _current_pool_size(self) -> int:
        return self.session.current_pool_size()

    def _advance_to_next_sentence(self) -> None:
        self.session.advance_to_next_sentence()

    def _reset_current_level(self) -> None:
        self.session.reset_current_level()

    def _advance_to_higher_stage(self) -> bool:
        return self.session.advance_to_higher_stage()

    def _try_level_up(self, accuracy: float) -> bool:
        return self.session.try_level_up(accuracy)

    def switch_scene(self, scene_name: str) -> None:
        if self.active_scene:
            self.active_scene.on_exit()
        self.active_scene = self.scenes[scene_name]
        self.active_scene.on_enter()

    def run(self) -> None:
        try:
            import pygame
        except Exception as exc:
            raise RuntimeError("pygame is required for GUI mode. Install with: pip install pygame") from exc

        pygame.init()
        pygame.font.init()

        fullscreen = self.config.fullscreen
        if fullscreen:
            flags = pygame.FULLSCREEN
            self.screen = pygame.display.set_mode((0, 0), flags)
        else:
            flags = 0
            self.screen = pygame.display.set_mode((self.config.width, self.config.height), flags)
        pygame.display.set_caption(self.config.title)

        self.clock = pygame.time.Clock()
        width, height = self.screen.get_size()
        
        # Cache standard fonts
        self.font_title = self._get_sys_font(64)
        self.font_subtitle = self._get_sys_font(24)
        self.font_body = self._get_sys_font(30)
        self.font_small = self._get_sys_font(22)
        self.font_button = self._get_sys_font(48, bold=True)
        
        # Cache prompt fonts to avoid recreation in render loop
        self.font_prompt_large = self._get_sys_font(max(96, int(height * 0.28)))
        self.font_prompt_medium = self._get_sys_font(max(96, int(height * 0.12)))
        self.font_prompt_small = self._get_sys_font(max(96, int(height * 0.09)))
        self.font_button = self._get_sys_font(48, bold=True)

        avatar_size = None
        self.animator = AvatarAnimator(
            pygame_module=pygame,
            assets_dir=self.config.assets_dir,
            frame_size=avatar_size,
            animation_fps=self.config.animation_fps,
            speaking_fps=self.config.speaking_fps,
            loading_fps=self.config.loading_fps,
            processing_fps=self.config.processing_fps,
        )
        self.animator.set_state("warmup", reset=True)

        self.scenes = {
            "intro": IntroScene(self),
            "main_menu": MainMenuScene(self),
            "reading_prompt": ReadingPromptScene(self),
            "settings": SettingsScene(self),
        }
        self.switch_scene("intro")

        self.running = True
        while self.running:
            now_ms = pygame.time.get_ticks()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                else:
                    self.active_scene.handle_event(event)

            self.animator.update(now_ms)
            self.active_scene.update(now_ms)
            self.active_scene.render()
            
            pygame.display.flip()
            self.clock.tick(self.config.fps)

        pygame.quit()
