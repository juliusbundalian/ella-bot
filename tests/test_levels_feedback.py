import json
import re
import sys
import os
import time
from typing import Dict, List

# Ensure project src path is in Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from ella_bot.validation.validators import validate_spoken_text
from ella_bot.validation.feedback import build_feedback, build_spoken_feedback_with_coaching, build_targeted_overrides
from ella_bot.config.app_config import load_settings
from ella_bot.speech.tts.base import TTSConfig
from ella_bot.speech.tts.factory import build_tts

def run_tests():
    print("==================================================")
    print("  Running Silent Verification for All 738 Items")
    print("==================================================")

    # 1. Load Level Pools
    pools_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config", "level_pools.json"))
    with open(pools_path, "r", encoding="utf-8") as f:
        level_pools = json.load(f)

    # 2. Load Overrides
    overrides_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config", "pronunciation_overrides.json"))
    with open(overrides_path, "r", encoding="utf-8") as f:
        overrides = json.load(f)

    suspicious_patterns = [
        r"\blet'suh\b",
        r"\bdon'tuh\b",
        r"\bweh\b",
        r"\bdoh\b",
        r"\bee think\b",
        r"\bI think you skipped the word, a\b"
    ]

    total_checked = 0
    passed = 0
    failures = []

    for level, sentences in level_pools.items():
        for sentence in sentences:
            total_checked += 1
            try:
                # Test Scenario 1: Completely missed target (pronunciation coaching test)
                validation = validate_spoken_text(expected_sentence=sentence, spoken_sentence="")
                feedback = build_feedback(validation, {})
                spoken_lines = build_spoken_feedback_with_coaching(
                    feedback=feedback,
                    overrides=overrides,
                    expected_sentence=sentence,
                    max_hints=2
                )

                # Assert spoken lines are built successfully
                assert len(spoken_lines) > 0, "Should generate spoken lines for coaching feedback"
                targeted_overrides = build_targeted_overrides(sentence, overrides)

                # Check for suspicious mangled carrier phrases
                for line in spoken_lines:
                    line_lower = line.lower()
                    if (
                        line_lower.startswith("alright, let me") or 
                        line_lower == sentence.lower() + "." or
                        "sounds like" in line_lower or
                        "carefully" in line_lower or
                        "with me" in line_lower
                    ):
                        continue
                        
                    for pattern in suspicious_patterns:
                        if re.search(pattern, line_lower):
                            is_expected = False
                            for target_w, override_w in targeted_overrides.items():
                                if override_w in line_lower and re.search(pattern, override_w):
                                    is_expected = True
                                    break
                            if is_expected:
                                continue
                                
                            if pattern == r"\bI think you skipped the word, a\b" and "a" not in overrides:
                                continue
                            raise AssertionError(f"Suspicious/mangled word pattern '{pattern}' detected in spoken carrier line: '{line}'")

                # Test Scenario 2: Perfect Match
                validation_perfect = validate_spoken_text(expected_sentence=sentence, spoken_sentence=sentence)
                feedback_perfect = build_feedback(validation_perfect, {})
                spoken_perfect = build_spoken_feedback_with_coaching(
                    feedback=feedback_perfect,
                    overrides=overrides,
                    expected_sentence=sentence,
                    max_hints=2
                )
                assert len(spoken_perfect) > 0, "Should generate spoken lines for perfect feedback"

                passed += 1

            except Exception as e:
                failures.append((level, sentence, str(e)))

    print(f"Passed Silent Verification on all {passed}/{total_checked} target sentences!")

    if failures:
        print("\nList of Failures in Silent Checks:")
        for lvl, snt, err in failures:
            print(f" - Level {lvl} | '{snt}' | Error: {err}")
        sys.exit(1)

    print("\n==================================================")
    print("  Initializing TTS Engine for Audible Levels Demo ")
    print("==================================================")
    
    settings = load_settings()
    # Ensure audio feedback is active for testing
    settings["audio_feedback"] = True
    
    tts_config = TTSConfig(
        voice=None,
        rate=settings.get("tts_rate", 150),
        non_blocking=False,
        piper_binary=settings.get("piper_binary"),
        piper_model=settings.get("piper_model"),
        noise_scale=settings.get("noise_scale", 0.667),
        noise_w=settings.get("noise_w", 0.8),
        length_scale=settings.get("length_scale", 1.0),
        kokoro_model=settings.get("kokoro_model"),
        kokoro_voices=settings.get("kokoro_voices"),
    )
    
    engine_name = settings.get("tts_engine", "auto")
    print(f"[TEST] Instantiating TTS Engine: {engine_name}...")
    tts_engine = build_tts(engine_name, config=tts_config)
    print("[TEST] TTS Engine initialized successfully!")

    # Pick 1 representative sentence from each level to speak out loud
    demo_sentences = {
        "1a": "e",
        "1b": "s",
        "1c": "ba",
        "1d": "ea (seat)",
        "1e": "ch (chip)",
        "1f": "dge (bridge)",
        "1g": "bl (blue)",
        "2a": "go",
        "2b": "people",
        "2c": "computer",
        "2d": "autumn",
        "3": "in the morning",
        "4": "the sun was shining brightly this morning."
    }

    print("\n==================================================")
    print("  Running Audible Level-by-Level Demonstration")
    print("==================================================")

    for level, sentence in demo_sentences.items():
        print(f"\n--------------------------------------------------")
        print(f" LEVEL: {level} | Target: '{sentence}'")
        print(f"--------------------------------------------------")
        
        # Simulate completely missed sentence to generate full coaching
        validation = validate_spoken_text(expected_sentence=sentence, spoken_sentence="")
        feedback = build_feedback(validation, {})
        spoken_lines = build_spoken_feedback_with_coaching(
            feedback=feedback,
            overrides=overrides,
            expected_sentence=sentence,
            max_hints=2
        )

        for idx, line in enumerate(spoken_lines):
            # Print using backslashreplace to prevent Windows console encoding crashes on Unicode IPA characters
            print(f"  [Speaking] -> {line.encode('ascii', 'backslashreplace').decode('ascii')}")
            
            # Determine speech rate using ELLA's UI guidelines
            lower_line = line.lower()
            if idx > 0 or any(kw in lower_line for kw in [
                "work on the word", "look at", "tricky", "skipped", "forget",
                "say it with me", "sounds like", "listen carefully"
            ]):
                if "let me read" in lower_line or "let me make" in lower_line:
                    rate = tts_config.rate
                else:
                    rate = int(tts_config.rate * 0.8)
            else:
                rate = tts_config.rate

            tts_engine.speak(line, rate=rate)
            time.sleep(0.5)

    print("\n==================================================")
    print("  Audible Levels Demonstration Completed!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
