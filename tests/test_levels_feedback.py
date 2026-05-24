import json
import re
import sys
import os
from typing import Dict, List

# Ensure project src path is in Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from ella_bot.validation.validators import validate_spoken_text
from ella_bot.validation.feedback import build_feedback, build_spoken_feedback_with_coaching, build_targeted_overrides

def run_tests():
    print("==================================================")
    print("  Running Automated Tests for E.L.L.A. Level Feedback")
    print("==================================================")

    # 1. Load Level Pools
    pools_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config", "level_pools.json"))
    with open(pools_path, "r") as f:
        level_pools = json.load(f)

    # 2. Load Overrides
    overrides_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config", "pronunciation_overrides.json"))
    with open(overrides_path, "r") as f:
        overrides = json.load(f)

    suspicious_patterns = [
        r"\blet'suh\b",
        r"\bdon'tuh\b",
        r"\bweh\b",
        r"\bdoh\b",
        r"\bee think\b",
        r"\bI think you skipped the word, a\b"  # Should be 'ah' in hints
    ]

    total_checked = 0
    passed = 0
    failures = []

    for level, sentences in level_pools.items():
        print(f"\n[Level {level}] Testing {len(sentences)} items...")
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
                    # Skip target reading demonstration and coaching templates
                    if (
                        line_lower.startswith("alright, let me read the sentence") or 
                        line_lower == sentence.lower() + "." or
                        "sounds like" in line_lower or
                        "carefully" in line_lower or
                        "with me" in line_lower
                    ):
                        continue
                        
                    # Carrier sentences must not contain basic mangled phonetic letters
                    for pattern in suspicious_patterns:
                        if re.search(pattern, line_lower):
                            # If the pattern matched is exactly the targeted override for this target word, it is expected!
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
                print(f"  [FAIL] Level {level} - '{sentence}': {e}")

    print("\n==================================================")
    print("  Test Execution Summary")
    print("==================================================")
    print(f"Total Sentences Tested: {total_checked}")
    print(f"Passed:                 {passed}")
    print(f"Failed:                 {len(failures)}")
    print("==================================================")

    if failures:
        print("\nList of Failures:")
        for lvl, snt, err in failures:
            print(f" - Level {lvl} | '{snt}' | Error: {err}")
        sys.exit(1)
    else:
        print("\nAll levels and sentences are working perfectly and standardly without any suspicious outputs!")
        sys.exit(0)

if __name__ == "__main__":
    run_tests()
