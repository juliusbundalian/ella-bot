import sys
import os
import json
import time
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Ensure project src path is in Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import pygame
from ella_bot.ui.pygame_gui.app import EllaGUIApp
from ella_bot.ui.pygame_gui.config import GUIConfig
from ella_bot.ui.pygame_gui.scenes.intro import IntroScene
from ella_bot.ui.pygame_gui.scenes.main_menu import MainMenuScene
from ella_bot.ui.pygame_gui.scenes.profiles import ProfilesScene
from ella_bot.ui.pygame_gui.scenes.level_selection import LevelSelectionScene
from ella_bot.ui.pygame_gui.scenes.reading_prompt import ReadingPromptScene
from ella_bot.ui.pygame_gui.scenes.results import ResultsScene
from ella_bot.ui.pygame_gui.scenes.final_eval import FinalEvaluationScene
from ella_bot.ui.pygame_gui.scenes.settings import SettingsScene
from ella_bot.speech.asr.vosk_engine import BaseASR, ASRResult, WordScore
from ella_bot.speech.tts.base import TTSConfig
from ella_bot.speech.tts.factory import build_tts
from ella_bot.config.app_config import load_settings

class E2ETestASR(BaseASR):
    def __init__(self):
        self.app = None
        self.attempt_counts = {}

    def transcribe(
        self,
        expected_sentence: str = None,
        is_paused=None,
    ) -> ASRResult:
        if not expected_sentence:
            expected_sentence = self.app.expected_sentence
            
        level = self.app.current_level
        key = (level, expected_sentence)
        self.attempt_counts[key] = self.attempt_counts.get(key, 0) + 1
        attempt = self.attempt_counts[key]
        
        print(f"\n[ASR TEST MODEL] Level: {level} | Target: '{expected_sentence}' | Attempt: {attempt}")
        
        if attempt == 1:
            print("[ASR TEST MODEL] Simulating FAILED reading attempt (empty transcription)")
            return ASRResult(transcript="", words=[])
        else:
            print(f"[ASR TEST MODEL] Simulating SUCCESSFUL reading attempt ('{expected_sentence}')")
            words = [WordScore(word=w, confidence=0.98) for w in expected_sentence.split()]
            return ASRResult(transcript=expected_sentence, words=words)


def test_e2e_asr_accepts_attempt_runner_pause_keyword():
    asr = E2ETestASR()
    asr.app = MagicMock(current_level='1a', expected_sentence='cat')

    result = asr.transcribe(expected_sentence='cat', is_paused=lambda: False)

    assert result == ASRResult(transcript='', words=[])


def test_e2e_harness_uses_only_an_isolated_profile_store(tmp_path):
    asr = E2ETestASR()

    app = _build_harness_app(tmp_path, asr=asr, tts=None, overrides={})

    project_data_dir = (Path(__file__).resolve().parents[1] / 'data').resolve()
    assert app.config.session_log_path == tmp_path / 'sessions.jsonl'
    assert app.profile_store.registry_path == tmp_path / 'profiles.json'
    assert app.config.session_log_path.parent.resolve() != project_data_dir
    assert tuple(profile.name for profile in app.profiles()) == ('E2E Reader',)
    assert app.active_profile().name == 'E2E Reader'


class AutoMainMenuScene(MainMenuScene):
    def update(self, now_ms: int) -> None:
        super().update(now_ms)
        # Automatically transition to the reading prompt scene without waiting for mouse clicks
        print("[TEST MANAGER] Main menu active, automatically transitioning to reading prompt scene...")
        if self.app.start_new_session("1a"):
            self.app.switch_scene("reading_prompt")
            self.app.active_scene._start_attempt()


class AutoReadingPromptScene(ReadingPromptScene):
    def update(self, now_ms: int) -> None:
        super().update(now_ms)

        # Automatically start the next attempt if ELLA is back in 'listening' state and prompt isn't active
        if self.app.state == "listening" and not self.app.prompt_active and not self.is_paused:
            # Give a brief simulated delay of 1.5 seconds for a realistic human pacing
            time.sleep(1.5)
            if self.app.state == "listening" and not self.app.prompt_active:
                print(f"[TEST MANAGER] Triggering next automated attempt for target: '{self.app.expected_sentence}'")
                self._start_attempt()


class AutoResultsScene(ResultsScene):
    def on_enter(self) -> None:
        super().on_enter()
        self._auto_next_at = time.monotonic() + 2.0

    def update(self, now_ms: int) -> None:
        super().update(now_ms)
        if hasattr(self, "_auto_next_at") and time.monotonic() >= self._auto_next_at:
            delattr(self, "_auto_next_at")
            print("[TEST MANAGER] Results screen active, automatically continuing...")
            if getattr(self.app.latest_result, "passed", True):
                self._do_next()
            else:
                self._do_retry()


class AutoFinalEvaluationScene(FinalEvaluationScene):
    def on_enter(self) -> None:
        super().on_enter()
        self._auto_exit_at = time.monotonic() + 3.0

    def update(self, now_ms: int) -> None:
        super().update(now_ms)
        if hasattr(self, "_auto_exit_at") and time.monotonic() >= self._auto_exit_at:
            delattr(self, "_auto_exit_at")
            print("\n==================================================")
            print("  SUCCESS: E2E GUI Test Completed All Levels!")
            print("==================================================")
            self.app.running = False


class E2EInteractiveApp(EllaGUIApp):
    def run(self) -> None:
        try:
            import pygame
        except Exception as exc:
            raise RuntimeError("pygame is required for GUI mode.") from exc

        self.shutdown_complete = False
        try:
            self._initialize_e2e_gui(pygame)
            self._run_e2e_loop(pygame)
        finally:
            try:
                self.shutdown_complete = self.shutdown() is not False
            finally:
                pygame.quit()

    def _initialize_e2e_gui(self, pygame_module) -> None:
        pygame_module.init()
        pygame_module.font.init()
        self.screen = pygame_module.display.set_mode(
            (self.config.width, self.config.height)
        )
        pygame_module.display.set_caption(
            'E.L.L.A. E2E Automated Integration Test GUI'
        )
        self.clock = pygame_module.time.Clock()
        width, height = self.screen.get_size()
        self.font_title = self._get_sys_font(42)
        self.font_subtitle = self._get_sys_font(24)
        self.font_body = self._get_sys_font(30)
        self.font_small = self._get_sys_font(22)
        self.font_prompt_large = self._get_sys_font(max(96, int(height * 0.28)))
        self.font_prompt_medium = self._get_sys_font(max(96, int(height * 0.12)))
        self.font_prompt_small = self._get_sys_font(max(96, int(height * 0.09)))
        self.font_button = self._get_sys_font(48, bold=True)

        from ella_bot.ui.pygame_gui.animator import AvatarAnimator
        self.animator = AvatarAnimator(
            pygame_module=pygame_module,
            assets_dir=self.config.assets_dir,
            frame_size=None,
            animation_fps=self.config.animation_fps,
            speaking_fps=self.config.speaking_fps,
            loading_fps=self.config.loading_fps,
            processing_fps=self.config.processing_fps,
        )
        self.animator.set_state('warmup', reset=True)
        self.scenes = {
            'intro': IntroScene(self),
            'main_menu': AutoMainMenuScene(self),
            'profiles': ProfilesScene(self),
            'level_selection': LevelSelectionScene(self),
            'reading_prompt': AutoReadingPromptScene(self),
            'settings': SettingsScene(self),
            'results': AutoResultsScene(self),
            'final_eval': AutoFinalEvaluationScene(self),
        }
        self.switch_scene('intro')

    def _run_e2e_loop(self, pygame_module) -> None:
        self.running = True
        while self.running:
            now_ms = pygame_module.time.get_ticks()
            for event in pygame_module.event.get():
                if event.type == pygame_module.QUIT:
                    self.running = False
                else:
                    self.active_scene.handle_event(event)
            self.animator.update(now_ms)
            self.active_scene.update(now_ms)
            self.active_scene.render()
            pygame_module.display.flip()
            self.clock.tick(self.config.fps)


def test_e2e_run_shuts_down_before_pygame_quit_on_failure(monkeypatch):
    app = object.__new__(E2EInteractiveApp)
    actions = []
    app._initialize_e2e_gui = MagicMock()
    app._run_e2e_loop = MagicMock(side_effect=RuntimeError('loop failed'))
    app.shutdown = MagicMock(side_effect=lambda: actions.append('shutdown'))
    monkeypatch.setattr(pygame, 'quit', lambda: actions.append('quit'))

    with pytest.raises(RuntimeError, match='loop failed'):
        app.run()

    assert actions == ['shutdown', 'quit']


def test_e2e_run_shuts_down_when_gui_initialization_fails(monkeypatch):
    app = object.__new__(E2EInteractiveApp)
    actions = []
    app._initialize_e2e_gui = MagicMock(
        side_effect=RuntimeError('initialization failed')
    )
    app._run_e2e_loop = MagicMock()
    app.shutdown = MagicMock(side_effect=lambda: actions.append('shutdown'))
    monkeypatch.setattr(pygame, 'quit', lambda: actions.append('quit'))

    with pytest.raises(RuntimeError, match='initialization failed'):
        app.run()

    assert actions == ['shutdown', 'quit']


def test_e2e_cleanup_preserves_data_when_worker_shutdown_is_incomplete(tmp_path):
    data_dir = tmp_path / 'harness-data'
    data_dir.mkdir()
    (data_dir / 'profiles.json').write_text('{}', encoding='utf-8')
    app = MagicMock(shutdown_complete=False)

    cleaned = _cleanup_harness_data(data_dir, app)

    assert cleaned is False
    assert data_dir.exists()


def _build_harness_config(data_dir: Path) -> GUIConfig:
    return GUIConfig(
        width=1280,
        height=720,
        fullscreen=False,
        pass_bar=0.50,
        session_log_path=Path(data_dir) / 'sessions.jsonl',
    )


def _build_harness_app(data_dir: Path, *, asr, tts, overrides):
    config = _build_harness_config(data_dir)
    app = E2EInteractiveApp(
        expected_sentence='',
        asr=asr,
        tts=tts,
        audio_feedback=True,
        pronunciation_overrides=overrides,
        config=config,
    )
    if app.profiles():
        raise RuntimeError('E2E data directory must start without profiles')
    app.create_profile('E2E Reader')
    return app


def _cleanup_harness_data(data_dir: Path, app) -> bool:
    if not getattr(app, 'shutdown_complete', False):
        return False
    shutil.rmtree(data_dir)
    return True


def main():
    settings = load_settings()
    # Explicitly configure audio feedback to True so ELLA speaks
    settings["audio_feedback"] = True
    # Ensure windowed mode
    settings["fullscreen"] = False
    
    # Load full real level pools from config/level_pools.json
    pools_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config", "level_pools.json"))
    with open(pools_path, "r") as f:
        real_level_pools = json.load(f)
    
    # Load pronunciation overrides
    overrides_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config", "pronunciation_overrides.json"))
    with open(overrides_path, "r", encoding="utf-8") as f:
        overrides = json.load(f)
        
    asr = E2ETestASR()
    temporary_data = Path(tempfile.mkdtemp(prefix='ella-e2e-'))
    
    # Build TTS Config
    tts_engine = settings.get("tts_engine", "auto")
    tts_rate = int(settings.get("tts_rate", 150))
    tts_voice = settings.get("tts_voice", None)
    piper_binary = settings.get("piper_binary", "./piper/piper.exe")
    piper_model = settings.get("piper_model", "./models/bmo.onnx")
    kokoro_model = settings.get("kokoro_model", "./models/kokoro-v1.0.onnx")
    kokoro_voices = settings.get("kokoro_voices", "./models/voices-v1.0.bin")
    
    tts = build_tts(
        engine_name=tts_engine,
        config=TTSConfig(
            voice=tts_voice,
            rate=tts_rate,
            piper_binary=piper_binary,
            piper_model=piper_model,
            kokoro_model=kokoro_model,
            kokoro_voices=kokoro_voices,
        )
    )
    
    app = _build_harness_app(
        temporary_data,
        asr=asr,
        tts=tts,
        overrides=overrides,
    )
    
    # Inject references and custom pools
    asr.app = app
    app.level_pools = real_level_pools
    app.level_goal = len(real_level_pools[app.current_level])
    app.expected_sentence = app._pick_sentence_for_level(app.current_level)
    
    print("\n==================================================")
    print("  Starting ELLA GUI E2E Automated Integration Test")
    print("  Flow: 1 Failed Attempt -> 1 Successful Attempt")
    print("        All Items -> Level Up -> Next Level (1a to 4)")
    print("==================================================\n")
    
    try:
        app.run()
    finally:
        _cleanup_harness_data(temporary_data, app)


if __name__ == "__main__":
    main()
