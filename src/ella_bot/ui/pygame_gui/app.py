import queue
from dataclasses import asdict
from typing import Dict, List, Optional

from ella_bot.core.constants import LEVEL_ORDER
from ella_bot.services.attempt_runner import AttemptViewModel
from ella_bot.services.evaluation import EvaluationService
from ella_bot.services.session_checkpoint import SessionCheckpointStore
from ella_bot.services.session_manager import SessionManager
from ella_bot.ui.pygame_gui.animator import AvatarAnimator
from ella_bot.ui.pygame_gui.config import GUIConfig
from ella_bot.ui.pygame_gui.scenes.final_eval import FinalEvaluationScene
from ella_bot.ui.pygame_gui.scenes.intro import IntroScene
from ella_bot.ui.pygame_gui.scenes.level_selection import LevelSelectionScene
from ella_bot.ui.pygame_gui.scenes.main_menu import MainMenuScene
from ella_bot.ui.pygame_gui.scenes.reading_prompt import ReadingPromptScene
from ella_bot.ui.pygame_gui.scenes.results import ResultsScene
from ella_bot.ui.pygame_gui.scenes.settings import SettingsScene
from ella_bot.utils.logging import get_logger


logger = get_logger(__name__)

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
        self._hard_sentences = hard_sentences
        self._seed_sentence = expected_sentence

        self.session = SessionManager.from_config_file(
            start_level=start_level,
            hard_sentences=hard_sentences,
            seed_sentence=expected_sentence,
        )

        self.evaluation = EvaluationService(
            log_path=self.config.session_log_path,
            pass_bar=self.config.pass_bar,
        )
        self.latest_result = None
        self.latest_result_kind = None
        self.selected_start_level: str | None = None
        self.checkpoint_phase: str | None = None
        self.checkpoint_latest_result: dict | None = None
        checkpoint_path = self.config.session_log_path.with_name("active_session.json")
        self.checkpoint_store = SessionCheckpointStore(checkpoint_path)

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

    def _get_prompt_font(self, size):
        """Return Arial exclusively for words, phrases, and sentences to read."""
        import pygame
        return pygame.font.SysFont("Arial", size)

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

    # --- Active-session checkpoint orchestration ---

    def has_saved_session(self) -> bool:
        return self.saved_session_summary() is not None

    def saved_session_summary(self):
        return self.checkpoint_store.summary(
            self.session.level_pools,
            self.evaluation.log_path,
            self.evaluation.pass_bar,
        )

    def start_new_session(self, level: str) -> bool:
        if level not in LEVEL_ORDER:
            return False
        candidate_session = SessionManager.from_config_file(
            start_level=level,
            hard_sentences=self._hard_sentences,
            seed_sentence=self._seed_sentence,
        )
        candidate_evaluation = EvaluationService(
            log_path=self.evaluation.log_path,
            pass_bar=self.evaluation.pass_bar,
        )
        try:
            self.checkpoint_store.save(
                level,
                "reading",
                candidate_session,
                candidate_evaluation,
            )
        except Exception as exc:
            logger.error("Unable to create a new session checkpoint: %s", exc)
            self.message = "Progress could not be saved."
            return False
        self.session = candidate_session
        self.evaluation = candidate_evaluation
        self.selected_start_level = level
        self.checkpoint_phase = "reading"
        self.checkpoint_latest_result = None
        self.latest_result = None
        self.latest_result_kind = None
        return True

    def save_active_session(
        self,
        phase: str,
        latest_result: dict | None = None,
    ) -> bool:
        if self.selected_start_level is None:
            return False
        try:
            self.checkpoint_store.save(
                self.selected_start_level,
                phase,
                self.session,
                self.evaluation,
                latest_result,
            )
            self.checkpoint_phase = phase
            self.checkpoint_latest_result = latest_result
            return True
        except Exception as exc:
            logger.error("Unable to save active session: %s", exc)
            self.message = "Progress could not be saved."
            return False

    def continue_saved_session(self) -> str | None:
        try:
            restored = self.checkpoint_store.restore(
                self.session.level_pools,
                self.evaluation.log_path,
                self.evaluation.pass_bar,
            )
        except Exception as exc:
            logger.error("Unable to restore active session: %s", exc)
            self.message = "Saved progress could not be restored."
            return None
        if restored is None:
            self.message = "Saved progress could not be restored."
            return None
        self.session = restored.session
        self.evaluation = restored.evaluation
        self.selected_start_level = restored.selected_start_level
        self.latest_result_kind = restored.latest_result_kind
        self.latest_result = restored.latest_result
        self.checkpoint_phase = restored.phase
        self.checkpoint_latest_result = (
            None
            if restored.latest_result is None
            else {
                "kind": restored.latest_result_kind,
                "payload": asdict(restored.latest_result),
            }
        )
        return restored.phase

    def clear_active_session(self) -> None:
        self.checkpoint_store.clear()
        self.selected_start_level = None
        self.checkpoint_phase = None
        self.checkpoint_latest_result = None

    def shutdown(self) -> None:
        prepare = getattr(self.active_scene, "prepare_shutdown", None)
        if callable(prepare):
            prepare()
        if self.selected_start_level is not None and self.checkpoint_phase is not None:
            self.save_active_session(
                self.checkpoint_phase,
                self.checkpoint_latest_result,
            )

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
        self.font_prompt_large = self._get_prompt_font(max(96, int(height * 0.28)))
        self.font_prompt_medium = self._get_prompt_font(max(96, int(height * 0.12)))
        self.font_prompt_small = self._get_prompt_font(max(96, int(height * 0.09)))
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
            "level_selection": LevelSelectionScene(self),
            "reading_prompt": ReadingPromptScene(self),
            "settings": SettingsScene(self),
            "results": ResultsScene(self),
            "final_eval": FinalEvaluationScene(self),
        }
        self.switch_scene("intro")

        try:
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
        finally:
            try:
                self.shutdown()
            finally:
                pygame.quit()
