from ella_bot.validation.validators import (
    normalize,
    align_words,
    validate_spoken_text,
    build_highlighted_expected,
    spoken_word_confidence_map,
)


def test_normalize_lowercases_and_strips_punctuation():
    assert normalize("The CAT, sat!") == ["the", "cat", "sat"]


def test_perfect_match_is_full_accuracy():
    result = validate_spoken_text("the cat sat", "the cat sat")
    assert result.accuracy == 1.0
    assert result.wer == 0.0
    assert result.missing_words == []
    assert result.incorrect_words == []
    assert result.extra_words == []


def test_single_letter_homophone_counts_as_match():
    # "see" is a registered homophone of "c"
    result = validate_spoken_text("c", "see")
    assert result.accuracy == 1.0


def test_missing_word_is_detected():
    result = validate_spoken_text("the cat sat", "the sat")
    assert result.missing_words == ["cat"]
    assert result.wer == 1 / 3


def test_substitution_is_detected():
    result = validate_spoken_text("the cat sat", "the dog sat")
    assert result.incorrect_words == [("cat", "dog")]


def test_extra_word_is_detected():
    result = validate_spoken_text("the cat", "the cat now")
    assert result.extra_words == ["now"]


def test_highlight_brackets_non_matching_expected_words():
    result = validate_spoken_text("the cat sat", "the dog sat")
    assert build_highlighted_expected(result.alignment) == "the [cat] sat"


def test_confidence_map_pairs_tokens_to_scores():
    assert spoken_word_confidence_map(["a", "b"], [0.1, 0.9]) == {"a": 0.1, "b": 0.9}


def test_strict_fluency_accepts_matching_word_at_35_percent_confidence():
    result = validate_spoken_text(
        "we waited",
        "we waited",
        spoken_confidences=[0.35, 0.9],
        strict_fluency=True,
    )

    assert result.accuracy == 1.0


def test_strict_fluency_rejects_matching_word_below_35_percent_confidence():
    result = validate_spoken_text(
        "we waited",
        "we waited",
        spoken_confidences=[0.34, 0.9],
        strict_fluency=True,
    )

    assert result.incorrect_words == [("we", "we")]
