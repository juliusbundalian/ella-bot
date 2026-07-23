import json
from pathlib import Path


OVERRIDES_PATH = Path(__file__).resolve().parents[1] / "config" / "pronunciation_overrides.json"

LEVEL_1A_ENGLISH_PHONICS = {
    "a": "phonemes:ˈæ.",
    "e": "phonemes:ˈɛ.",
    "i": "phonemes:ˈɪ.",
    "o": "phonemes:ˈɑ.",
    "u": "phonemes:ˈʌ.",
}

LEVEL_1B_ENGLISH_PHONICS = {
    "b": "phonemes:b.",
    "c": "phonemes:k.",
    "d": "phonemes:d.",
    "f": "phonemes:f.",
    "g": "phonemes:ɡ.",
    "h": "phonemes:h.",
    "j": "phonemes:dʒ.",
    "k": "phonemes:k.",
    "l": "phonemes:l.",
    "m": "phonemes:m.",
    "n": "phonemes:n.",
    "p": "phonemes:p.",
    "q": "phonemes:kw.",
    "r": "phonemes:ɹ.",
    "s": "phonemes:s.",
    "t": "phonemes:t.",
    "v": "phonemes:v.",
    "w": "phonemes:w.",
    "x": "phonemes:ks.",
    "y": "phonemes:j.",
    "z": "phonemes:z.",
}


def _load_overrides() -> dict[str, str]:
    return json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))


def test_level_1a_uses_short_english_vowel_phonemes():
    overrides = _load_overrides()

    assert {letter: overrides[letter] for letter in LEVEL_1A_ENGLISH_PHONICS} == LEVEL_1A_ENGLISH_PHONICS


def test_level_1b_uses_beginner_english_consonant_phonemes():
    overrides = _load_overrides()

    assert {letter: overrides[letter] for letter in LEVEL_1B_ENGLISH_PHONICS} == LEVEL_1B_ENGLISH_PHONICS


def test_level_1c_blend_overrides_are_unchanged():
    overrides = _load_overrides()

    assert {key: overrides[key] for key in ("ba", "be", "bi", "bo", "bu")} == {
        "ba": "bah",
        "be": "phonemes:bˈɛ.",
        "bi": "bee",
        "bo": "phonemes:bˈɔ.",
        "bu": "phonemes:bˈuː.",
    }
