import sys
import os
import json
import time

# Ensure project src path is in Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import pygame
from ella_bot.ui.pygame_gui.app import EllaGUIApp
from ella_bot.ui.pygame_gui.config import GUIConfig
from ella_bot.ui.pygame_gui.scenes.intro import IntroScene
from ella_bot.ui.pygame_gui.scenes.main_menu import MainMenuScene
from ella_bot.ui.pygame_gui.scenes.reading_prompt import ReadingPromptScene
from ella_bot.speech.asr.vosk_engine import BaseASR, ASRResult, WordScore
from ella_bot.speech.tts.base import TTSConfig
from ella_bot.speech.tts.factory import build_tts
from ella_bot.config.app_config import load_settings

class E2ETestASR(BaseASR):
    def __init__(self):
        self.app = None
        self.attempt_counts = {}

    def transcribe(self, expected_sentence: str = None) -> ASRResult:
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


class AutoMainMenuScene(MainMenuScene):
    def update(self, now_ms: int) -> None:
        super().update(now_ms)
        # Automatically transition to the reading prompt scene without waiting for mouse clicks
        print("[TEST MANAGER] Main menu active, automatically transitioning to reading prompt scene...")
        self.app.switch_scene("reading_prompt")
        self.app.active_scene._start_attempt()


class AutoReadingPromptScene(ReadingPromptScene):
    def update(self, now_ms: int) -> None:
        super().update(now_ms)
        
        # Check if we successfully completed level 4
        if self.app.current_level == "4" and self.app.completed_in_level >= self.app.level_goal:
            print("\n==================================================")
            print("  SUCCESS: E2E GUI Test Completed All Levels!")
            print("==================================================")
            time.sleep(2)
            self.app.running = False
            return

        # Automatically start the next attempt if ELLA is back in 'listening' state and prompt isn't active
        if self.app.state == "listening" and not self.app.prompt_active and not self.is_paused:
            # Give a brief simulated delay of 1.5 seconds for a realistic human pacing
            time.sleep(1.5)
            if self.app.state == "listening" and not self.app.prompt_active:
                print(f"[TEST MANAGER] Triggering next automated attempt for target: '{self.app.expected_sentence}'")
                self._start_attempt()


class E2EInteractiveApp(EllaGUIApp):
    def run(self) -> None:
        try:
            import pygame
        except Exception as exc:
            raise RuntimeError("pygame is required for GUI mode.") from exc

        pygame.init()
        pygame.font.init()

        # Always run E2E test in windowed mode (not fullscreen) for better testing and visualization
        self.screen = pygame.display.set_mode((self.config.width, self.config.height))
        pygame.display.set_caption("E.L.L.A. E2E Automated Integration Test GUI")

        self.clock = pygame.time.Clock()
        width, height = self.screen.get_size()
        
        # Cache standard fonts
        self.font_title = self._get_sys_font(42)
        self.font_subtitle = self._get_sys_font(24)
        self.font_body = self._get_sys_font(30)
        self.font_small = self._get_sys_font(22)
        
        # Cache prompt fonts
        self.font_prompt_large = self._get_sys_font(max(96, int(height * 0.28)))
        self.font_prompt_medium = self._get_sys_font(max(96, int(height * 0.12)))
        self.font_prompt_small = self._get_sys_font(max(96, int(height * 0.09)))
        self.font_button = self._get_sys_font(48, bold=True)

        from ella_bot.ui.pygame_gui.animator import AvatarAnimator
        self.animator = AvatarAnimator(
            pygame_module=pygame,
            assets_dir=self.config.assets_dir,
            frame_size=None,
            animation_fps=self.config.animation_fps,
            speaking_fps=self.config.speaking_fps,
            loading_fps=self.config.loading_fps,
            processing_fps=self.config.processing_fps,
        )
        self.animator.set_state("warmup", reset=True)

        # Inject our customized scenes
        self.scenes = {
            "intro": IntroScene(self),
            "main_menu": AutoMainMenuScene(self),
            "reading_prompt": AutoReadingPromptScene(self),
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
    with open(overrides_path, "r") as f:
        overrides = json.load(f)
        
    asr = E2ETestASR()
    
    config = GUIConfig(
        width=1280,
        height=720,
        fullscreen=False,
    )
    
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
    
    app = E2EInteractiveApp(
        expected_sentence="",
        asr=asr,
        tts=tts,
        audio_feedback=True,
        pronunciation_overrides=overrides,
        config=config,
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
    
    app.run()


if __name__ == "__main__":
    main()
