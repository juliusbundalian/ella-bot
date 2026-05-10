import random
import queue
import threading
import time
from typing import Dict, List, Optional

from ella_bot.ui.pygame_gui.animator import AvatarAnimator
from ella_bot.ui.pygame_gui.config import GUIConfig
from ella_bot.ui.pygame_gui.scenes.main_menu import MainMenuScene
from ella_bot.ui.pygame_gui.scenes.reading_prompt import ReadingPromptScene, AttemptViewModel

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
        start_level: str = "easy",
        config: Optional[GUIConfig] = None,
    ) -> None:
        self.asr = asr
        self.tts = tts
        self.audio_feedback = audio_feedback
        self.pronunciation_overrides = pronunciation_overrides
        self.config = config or GUIConfig()

        self.level_order = ["easy", "medium-a", "medium-b", "medium-c", "hard"]
        self.level_thresholds = {
            "easy": 0.85,
            "medium-a": 0.88,
            "medium-b": 0.90,
            "medium-c": 0.92,
            "hard": 1.01,
        }

        self.level_pools: Dict[str, List[str]] = {
            "easy": list("abcdefghijklmnopqrstuvwxyz"),
            "medium-a": ["cat", "dog", "sun", "hat", "red", "pen", "map", "cup", "bed", "fish"],
            "medium-b": ["train", "green", "brush", "clock", "smile", "chair", "storm", "light", "plant", "school"],
            "medium-c": [
                "animal", "battery", "celebrate", "dinosaur", "elephant",
                "favorite", "important", "library", "remember", "wonderful",
            ],
            "hard": hard_sentences or ([expected_sentence] if expected_sentence else ["The cat sits on the table."]),
        }

        if start_level not in self.level_order:
            start_level = "easy"
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
        target_sentence = self.expected_sentence.strip() or "the next item"
        return (
            f"We are about to begin. You are on level {self._display_level_name()}, "
            f"item {self._current_item_number()}. First, read: {target_sentence}."
        )

    def _prompt_font(self, pygame_module):
        width, height = self.screen.get_size()
        if len(self.expected_sentence) <= 3:
            return pygame_module.font.SysFont("Avenir Next", max(72, int(height * 0.28)))
        if len(self.expected_sentence.split()) <= 6:
            return pygame_module.font.SysFont("Avenir Next", max(54, int(height * 0.12)))
        return pygame_module.font.SysFont("Avenir Next", max(42, int(height * 0.08)))

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

    def _startup_sequence(self) -> None:
        self.event_queue.put(("state", "warmup"))
        self.event_queue.put(("message", ""))
        time.sleep(2)
        self.event_queue.put(("state", "speaking"))
        self.event_queue.put(("message", ""))
        if self.tts is not None:
            try:
                self.tts.speak("Hello, I am Ella, your offline reading assistant. I am ready when you are.")
            except Exception as exc:
                self.event_queue.put(("error", str(exc)))

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
        self.font_title = pygame.font.SysFont("Avenir Next", 42)
        self.font_subtitle = pygame.font.SysFont("Avenir Next", 24)
        self.font_body = pygame.font.SysFont("Avenir Next", 30)
        self.font_small = pygame.font.SysFont("Avenir Next", 22)

        avatar_size = (360, 360)
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
            "main_menu": MainMenuScene(self),
            "reading_prompt": ReadingPromptScene(self),
        }
        self.switch_scene("main_menu")

        startup_thread = threading.Thread(target=self._startup_sequence, daemon=True)
        startup_thread.start()

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
