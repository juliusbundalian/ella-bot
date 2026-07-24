from ella_bot.validation import feedback as fb
from ella_bot.validation.validators import validate_spoken_text


def test_score_to_level_bands():
    assert fb.score_to_level(0.99) in fb._CORRECT_PHRASES
    assert fb.score_to_level(0.80) in fb._ALMOST_PHRASES
    assert fb.score_to_level(0.10) in fb._RETRY_PHRASES


def test_build_feedback_reports_missing_and_incorrect():
    validation = validate_spoken_text("the cat sat", "the dog")
    result = fb.build_feedback(validation=validation, spoken_confidence_by_word={})
    joined = " ".join(result.detailed_messages)
    assert "Incorrect words" in joined
    assert "Missing words" in joined


def test_apply_pronunciation_overrides_replaces_whole_words_case_insensitive():
    out = fb.apply_pronunciation_overrides("The CAT sat", {"cat": "kat"})
    assert out == "The kat sat"


def test_sanitize_converts_arrow_and_colon():
    out = fb.apply_pronunciation_overrides("cat->dog: now", {})
    assert "->" not in out
    assert ":" not in out


def test_auto_pronunciation_coaching_returns_function_words_verbatim():
    assert fb.auto_pronunciation_coaching("the") == "the"


def test_build_spoken_feedback_with_coaching_error_isolation():
    validation = validate_spoken_text("the cat sat.", "the dog sat.")
    result = fb.build_feedback(validation=validation, spoken_confidence_by_word={})
    lines = fb.build_spoken_feedback_with_coaching(
        feedback=result, overrides={}, expected_sentence="the cat sat.", max_hints=2, validation=validation
    )
    assert lines[0] == result.level_message
    joined = " ".join(lines).lower()
    assert "trouble with the word, cat" in joined
    assert "let's read the whole phrase together" in joined
