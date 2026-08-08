from __future__ import annotations

import queue
from dataclasses import asdict
from typing import Dict, List, Optional

from ella_bot.core.constants import LEVEL_ORDER
from ella_bot.services.attempt_runner import AttemptViewModel
from ella_bot.services.evaluation import EvaluationService
from ella_bot.services.profile_store import Profile, ProfileStore
from ella_bot.services.session_checkpoint import SessionCheckpointStore
from ella_bot.services.session_manager import SessionManager
from ella_bot.ui.pygame_gui.animator import AvatarAnimator
from ella_bot.ui.pygame_gui.config import GUIConfig
from ella_bot.ui.pygame_gui.scenes.final_eval import FinalEvaluationScene
from ella_bot.ui.pygame_gui.scenes.intro import IntroScene
from ella_bot.ui.pygame_gui.scenes.level_selection import LevelSelectionScene
from ella_bot.ui.pygame_gui.scenes.main_menu import MainMenuScene
from ella_bot.ui.pygame_gui.scenes.profiles import ProfilesScene
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
        self._default_start_level = start_level
        self.profile_store = ProfileStore(
            self.config.session_log_path.parent / 'profiles.json'
        )

        self._bind_profile(self.profile_store.active_profile())

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
        """Helper to get system or bundled font (Rencana / Changa One) with cross-platform fallbacks."""
        import pygame
        from ella_bot.utils.file_utils import resolve_asset_path

        for font_file in ["assets/fonts/Rencana.ttf", "assets/fonts/Rencana.otf", "assets/fonts/ChangaOne-Regular.ttf"]:
            ttf_path = resolve_asset_path(font_file)
            if ttf_path.exists():
                try:
                    return pygame.font.Font(str(ttf_path), size)
                except Exception:
                    pass

        fonts = ["Rencana", "Changa One", "Avenir Next", "Segoe UI", "Arial", "Verdana", "sans-serif"]
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

    # --- Learner profile orchestration ---

    def _bind_profile(self, profile: Profile | None) -> None:
        self.session = SessionManager.from_config_file(
            start_level=self._default_start_level,
            hard_sentences=self._hard_sentences,
            seed_sentence=self._seed_sentence,
        )
        if profile is None:
            base = self.profile_store.profiles_root / '_unowned'
            history_path = base / 'sessions.jsonl'
            checkpoint_path = base / 'active_session.json'
        else:
            history_path = self.profile_store.history_path(profile.id)
            checkpoint_path = self.profile_store.checkpoint_path(profile.id)
        self.evaluation = EvaluationService(history_path, self.config.pass_bar)
        self.checkpoint_store = SessionCheckpointStore(checkpoint_path)
        self.selected_start_level = None
        self.checkpoint_phase = None
        self.checkpoint_latest_result = None
        self.latest_result = None
        self.latest_result_kind = None
        self._clear_attempt_transients()

    def _clear_attempt_transients(self) -> None:
        self.state = 'idle'
        self.message = ''
        self.latest_attempt = None
        self.prompt_active = False
        event_queue = getattr(self, 'event_queue', None)
        if event_queue is None:
            self.event_queue = queue.Queue()
            return
        while True:
            try:
                event_queue.get_nowait()
            except queue.Empty:
                break

    def profiles(self) -> tuple[Profile, ...]:
        return self.profile_store.list_profiles()

    def active_profile(self) -> Profile | None:
        return self.profile_store.active_profile()

    def create_profile(self, name: str) -> Profile:
        profile = self.profile_store.create(name)
        self._bind_profile(profile)
        return profile

    def rename_profile(self, profile_id: str, name: str) -> Profile:
        return self.profile_store.rename(profile_id, name)

    def select_profile(self, profile_id: str) -> Profile:
        profile = self.profile_store.select(profile_id)
        self._bind_profile(profile)
        return profile

    def reset_profile_progress(self, profile_id: str) -> bool:
        cleaned = self.profile_store.reset_progress(profile_id)
        active = self.active_profile()
        if active is not None and active.id == profile_id:
            self._bind_profile(active)
        return cleaned

    def delete_profile(self, profile_id: str) -> bool:
        was_active = self.active_profile()
        cleaned = self.profile_store.delete(profile_id)
        if was_active is not None and was_active.id == profile_id:
            self._bind_profile(None)
        return cleaned

    def profile_session_summary(self, profile_id: str):
        checkpoint_store = SessionCheckpointStore(
            self.profile_store.checkpoint_path(profile_id)
        )
        return checkpoint_store.summary(
            self.session.level_pools,
            self.profile_store.history_path(profile_id),
            self.config.pass_bar,
        )

    # --- Active-session checkpoint orchestration ---

    def has_saved_session(self) -> bool:
        return self.saved_session_summary() is not None

    def saved_session_summary(self):
        if self.active_profile() is None:
            return None
        return self.checkpoint_store.summary(
            self.session.level_pools,
            self.evaluation.log_path,
            self.evaluation.pass_bar,
        )

    def start_new_session(self, level: str) -> bool:
        if self.active_profile() is None:
            return False
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
        if self.active_profile() is None:
            return False
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
        if self.active_profile() is None:
            return None
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
        if hasattr(self.session, "last_announced_sentence"):
            self.session.last_announced_sentence = ""
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

    def shutdown(self) -> bool:
        prepare = getattr(self.active_scene, "prepare_shutdown", None)
        if callable(prepare) and prepare() is False:
            return False
        if (
            self.active_profile() is not None
            and self.selected_start_level is not None
            and self.checkpoint_phase is not None
        ):
            self.save_active_session(
                self.checkpoint_phase,
                self.checkpoint_latest_result,
            )
        return True

    def switch_scene(self, scene_name: str) -> bool:
        if self.active_scene and self.active_scene.on_exit() is False:
            return False
        self.active_scene = self.scenes[scene_name]
        self.active_scene.on_enter()
        return True

    def _translate_pointer_event(self, pygame_module, event):
        """Keep pointer input aligned with the globally shifted rendering."""
        pointer_events = {
            pygame_module.MOUSEMOTION,
            pygame_module.MOUSEBUTTONDOWN,
            pygame_module.MOUSEBUTTONUP,
        }
        padding = max(0, self.config.left_padding)
        if padding == 0 or event.type not in pointer_events:
            return event
        attributes = event.dict.copy()
        attributes["pos"] = (event.pos[0] - padding, event.pos[1])
        return pygame_module.event.Event(event.type, attributes)

    def _apply_render_padding(self, pygame_module) -> None:
        """Shift the completed frame right, clipping its far-right edge."""
        padding = max(0, self.config.left_padding)
        if padding == 0:
            return
        self.screen.scroll(padding, 0)
        pygame_module.draw.rect(
            self.screen,
            (0, 0, 0),
            (0, 0, padding, self.screen.get_height()),
        )

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
            'profiles': ProfilesScene(self),
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
                        self.active_scene.handle_event(
                            self._translate_pointer_event(pygame, event)
                        )

                self.animator.update(now_ms)
                self.active_scene.update(now_ms)
                self.active_scene.render()
                self._apply_render_padding(pygame)

                pygame.display.flip()
                self.clock.tick(self.config.fps)
        finally:
            try:
                self.shutdown()
            finally:
                pygame.quit()
