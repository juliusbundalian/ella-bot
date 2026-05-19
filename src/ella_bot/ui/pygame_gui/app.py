import random
import queue
import threading
import time
import json
from typing import Dict, List, Optional

from ella_bot.ui.pygame_gui.animator import AvatarAnimator
from ella_bot.ui.pygame_gui.config import GUIConfig
from ella_bot.ui.pygame_gui.scenes.intro import IntroScene
from ella_bot.ui.pygame_gui.scenes.main_menu import MainMenuScene
from ella_bot.ui.pygame_gui.scenes.reading_prompt import ReadingPromptScene, AttemptViewModel
from ella_bot.core.constants import LEVEL_ORDER, LEVEL_THRESHOLDS

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

        self.level_order = list(LEVEL_ORDER)
        self.level_thresholds = dict(LEVEL_THRESHOLDS)

        with open("config/level_pools.json", "r") as f:
            self.level_pools = json.load(f)
        if hard_sentences:
            self.level_pools["hard"] = hard_sentences
        elif expected_sentence and expected_sentence not in self.level_pools["hard"]:
            self.level_pools["hard"] = [expected_sentence]

        if start_level not in self.level_order:
            start_level = "1a"
        self.current_level = start_level
        self.level_indices: Dict[str, int] = {level: 0 for level in self.level_order}
        self.expected_sentence = self._pick_sentence_for_level(self.current_level)
        self.completed_in_level = 0
        self.level_goal = len(self.level_pools.get(self.current_level, []))

        self.state = "idle"
        self.message = ""
        self.latest_attempt: Optional[AttemptViewModel] = None
        self.event_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.prompt_active = False

        self.running = False
        self.screen = None
        self.clock = None
        self.animator = None
        
        # Scenes will be initialized after pygame init
        self.scenes = {}
        self.active_scene = None

    def _current_item_number(self) -> int:
        return self.level_indices.get(self.current_level, 0) + 1

    def _build_start_announcement(self) -> str:
        import random
        target_sentence = self.expected_sentence.strip() or "the next item"
        level = self._display_level_name()
        item = self._current_item_number()
        intros = [
            f"Alright! You're on the {level} level, item {item}. When you're ready, please read, {target_sentence}.",
            f"Okay, let's do this! {level} level, item {item}. Go ahead and read, {target_sentence}.",
            f"Here we go! Item {item} on the {level} level. Please read out loud, {target_sentence}.",
        ]
        return random.choice(intros)

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
        pool = self.level_pools.get(level, [])
        if not pool:
            return ""
        if level == "hard":
            return random.choice(pool)
        index = self.level_indices.get(level, 0)
        index = max(0, min(index, len(pool) - 1))
        return pool[index]

    def _display_level_name(self) -> str:
        return self.current_level.replace("-", " ").title()

    def _current_pool_size(self) -> int:
        return len(self.level_pools.get(self.current_level, []))

    def _advance_to_next_sentence(self) -> None:
        if self.current_level == "hard":
            self.expected_sentence = self._pick_sentence_for_level(self.current_level)
            return
        pool = self.level_pools.get(self.current_level, [])
        if not pool:
            self.expected_sentence = ""
            return
        next_index = min(self.level_indices.get(self.current_level, 0) + 1, len(pool) - 1)
        self.level_indices[self.current_level] = next_index
        self.expected_sentence = pool[next_index]

    def _reset_current_level(self) -> None:
        self.completed_in_level = 0
        self.level_goal = self._current_pool_size()
        self.level_indices[self.current_level] = 0
        self.expected_sentence = self._pick_sentence_for_level(self.current_level)

    def _advance_to_higher_stage(self) -> bool:
        idx = self.level_order.index(self.current_level)
        if idx + 1 >= len(self.level_order):
            return False
        self.current_level = self.level_order[idx + 1]
        self._reset_current_level()
        return True

    def _try_level_up(self, accuracy: float) -> bool:
        if self.current_level == "hard":
            return False
        threshold = self.level_thresholds.get(self.current_level, 1.0)
        if self.completed_in_level < self.level_goal:
            return False
        if accuracy < threshold:
            return False
        return self._advance_to_higher_stage()

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

        fullscreen = True if not self.config.fullscreen else self.config.fullscreen
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
        self.font_title = self._get_sys_font(42)
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
