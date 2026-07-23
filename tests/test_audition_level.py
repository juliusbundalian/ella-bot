import pytest

from scripts.audition_level import PiperVariant, comparison_variants, consonant_class


@pytest.mark.parametrize(
    ("letter", "expected"),
    [
        ("b", "stop"),
        ("j", "stop"),
        ("f", "continuous"),
        ("z", "continuous"),
        ("q", "sequence"),
        ("x", "sequence"),
    ],
)
def test_consonant_class_identifies_tuning_group(letter, expected):
    assert consonant_class(letter) == expected


def test_consonant_class_rejects_unknown_target():
    with pytest.raises(ValueError, match="Unsupported level 1B consonant"):
        consonant_class("a")


@pytest.mark.parametrize(
    ("letter", "class_rate"),
    [("b", 170), ("f", 125), ("x", 145)],
)
def test_comparison_variants_have_exact_audition_settings(letter, class_rate):
    assert comparison_variants(letter) == (
        PiperVariant("current", 190, 0.667, 0.8, True, 0),
        PiperVariant("clean", 190, 0.3, 0.3, False, 0),
        PiperVariant("relaxed", 145, 0.3, 0.3, False, 200),
        PiperVariant("class-tuned", class_rate, 0.2, 0.2, False, 250),
    )
