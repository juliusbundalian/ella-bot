from __future__ import annotations

import re
import random
from difflib import SequenceMatcher
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional

from ella_bot.validation.validators import ValidationResult
from ella_bot.core.constants import get_level1_sound_and_word

try:
    import pronouncing
except Exception:
    pronouncing = None


@dataclass
class FeedbackResult:
    level_message: str
    detailed_messages: List[str]
    pronunciation_hints: List[str]


_CORRECT_PHRASES = [
    "Excellent work! That was perfect!",
    "Great job! You red that really well!",
    "Wonderful! You got it!",
    "That is right! Amazing reading!",
    "Perfect! I knew you could do it!",
]

_ALMOST_PHRASES = [
    "So close! You are almost there, just a tiny bit more.",
    "Really good try! You have almost got it.",
    "Nice effort! Let's try that one more time.",
    "That was good! You are really close — let's try again.",
]

_RETRY_PHRASES = [
    "Alright, let's give that another shot. You can do it!",
    "That is okay! Let's try reading it again.",
    "Don't worry, let's have another go at it!",
    "It is tricky, I know. Let's try one more time!",
]


def score_to_level(accuracy: float) -> str:
    if accuracy >= 0.95:
        return random.choice(_CORRECT_PHRASES)
    if accuracy >= 0.75:
        return random.choice(_ALMOST_PHRASES)
    return random.choice(_RETRY_PHRASES)


def simple_syllable_split(word: str) -> str:
    vowels = "aeiouy"
    chunks: List[str] = []
    current = ""

    for i, ch in enumerate(word.lower()):
        current += ch
        next_is_vowel = i + 1 < len(word) and word[i + 1].lower() in vowels
        this_is_vowel = ch in vowels
        if this_is_vowel and not next_is_vowel:
            chunks.append(current)
            current = ""

    if current:
        chunks.append(current)

    if len(chunks) <= 1:
        mid = max(1, len(word) // 2)
        return f"{word[:mid]}-{word[mid:]}" if len(word) > 3 else word

    return "-".join(chunks)


def get_target_type(expected_sentence: str) -> str:
    """Determine the type of target text: 'sound', 'word', 'phrase', or 'sentence'."""
    text = expected_sentence.strip().lower()
    if not text:
        return "sentence"

    if "(" in text and ")" in text:
        return "sound"

    words = text.split()

    # 1. Single character is always a sound (Level 1a, 1b)
    if len(text) == 1:
        return "sound"

    # 2. Syllable blends in Level 1c (excluding standard sight words to classify them correctly as words)
    level_1c_blends = {
        "ba", "be", "bi", "bo", "bu",
        "ca", "ce", "ci", "co", "cu",
        "da", "de", "di", "du",
        "fa", "fe", "fi", "fo", "fu",
        "ga", "ge", "gi", "gu",
        "ha", "hi", "ho", "hu",
        "ja", "je", "ji", "jo", "ju",
        "ka", "ke", "ki", "ko", "ku",
        "la", "le", "li", "lo", "lu",
        "ma", "mi", "mo", "mu",
        "na", "ne", "ni", "nu",
        "pa", "pe", "pi", "po", "pu",
        "qua", "que", "qui", "quo",
        "ra", "re", "ri", "ro", "ru",
        "sa", "se", "si", "su",
        "ta", "te", "ti", "tu",
        "va", "ve", "vi", "vo", "vu",
        "wa", "wi", "wo", "wu",
        "xa", "xe", "xi", "xo", "xu",
        "ya", "ye", "yi", "yo", "yu",
        "za", "ze", "zi", "zo", "zu"
    }
    if len(words) == 1 and text in level_1c_blends:
        return "sound"

    # 3. Single word is a word
    if len(words) == 1:
        return "word"

    # 4. Multi-word but doesn't end with a sentence punctuation (like ".", "!", "?") or under 4 words is a phrase
    if len(words) <= 3 or not text.endswith((".", "!", "?")):
        return "phrase"

    return "sentence"


def pronunciation_hints(
    validation: ValidationResult,
    spoken_confidence_by_word: Dict[str, float],
) -> List[str]:
    # Determine the target type from the alignment tokens
    expected_words = [token.expected for token in validation.alignment if token.expected]
    expected_sentence = " ".join(expected_words)
    t_type = get_target_type(expected_sentence)

    if t_type == "sound":
        _INCORRECT_HINTS = [
            "Alright, let's work on the sound, {word}. Can you say it again?",
            "Let's take another look at, {word}. Give it another try!",
            "The sound, {word}, is a little tricky. Let's practice it!",
        ]
        _MISSING_HINTS = [
            "I think you skipped the sound, {word}. Try including it this time!",
            "Don't forget, {word}! Let's make sure we say the sound.",
        ]
    elif t_type == "word":
        _INCORRECT_HINTS = [
            "Alright, let's work on the word, {word}. Can you say it again?",
            "Let's take another look at, {word}. Give it another try!",
            "The word, {word}, is a little tricky. Let's practice it!",
        ]
        _MISSING_HINTS = [
            "I think you skipped the word, {word}. Try including it this time!",
            "Don't forget, {word}! Let's make sure we say the word.",
        ]
    else:
        # For phrases and sentences: ELLA is giving a hint about a single word that was missed/incorrect.
        # So she says "skipped the word, {word}" and "let's make sure we say every word."
        _INCORRECT_HINTS = [
            "Alright, let's work on the word, {word}. Can you say it again?",
            "Let's take another look at, {word}. Give it another try!",
            "The word, {word}, is a little tricky. Let's practice it!",
        ]
        _MISSING_HINTS = [
            "I think you skipped the word, {word}. Try including it this time!",
            "Don't forget, {word}! Let's make sure we say every word.",
        ]

    hints: List[str] = []

    for expected, spoken in validation.incorrect_words:
        conf = spoken_confidence_by_word.get(spoken, 0.0)
        similarity = SequenceMatcher(None, expected, spoken).ratio()

        sound_target, _ = get_level1_sound_and_word(expected)
        if conf < 0.65 or similarity < 0.7:
            template = random.choice(_INCORRECT_HINTS)
            hints.append(template.format(word=sound_target))

    for missing in validation.missing_words:
        template = random.choice(_MISSING_HINTS)
        sound_target, _ = get_level1_sound_and_word(missing)
        hints.append(template.format(word=sound_target))

    # Keep feedback brief for children.
    return hints[:4]


def build_feedback(
    validation: ValidationResult,
    spoken_confidence_by_word: Dict[str, float],
) -> FeedbackResult:
    level = score_to_level(validation.accuracy)
    details: List[str] = []

    if validation.missing_words:
        details.append("Missing words: " + ", ".join(validation.missing_words))
    if validation.incorrect_words:
        wrong = [f"{exp}->{got}" for exp, got in validation.incorrect_words]
        details.append("Incorrect words: " + ", ".join(wrong))
    if validation.extra_words:
        details.append("Extra words: " + ", ".join(validation.extra_words))

    hints = pronunciation_hints(validation, spoken_confidence_by_word)
    return FeedbackResult(level_message=level, detailed_messages=details, pronunciation_hints=hints)


def build_spoken_feedback(feedback: FeedbackResult, max_hints: int = 2) -> List[str]:
    """Build short spoken lines suitable for TTS playback in child-facing mode."""
    lines: List[str] = [feedback.level_message]

    for hint in feedback.pronunciation_hints[:max_hints]:
        # Rephrase hint markers for natural speech synthesis.
        lines.append(hint.replace("Listen and repeat:", "Listen and repeat,"))

    # Filter out empty lines and cap to keep playback brief.
    return [line.strip() for line in lines if line.strip()][: 1 + max_hints]


def _replace_word_case_insensitive(text: str, word: str, replacement: str) -> str:
    # If the word is lowercase "i", treat it as case-sensitive to avoid matching capitalized conversational "I"
    if word == "i":
        pattern = re.compile(rf"\b{re.escape(word)}\b")
    # Avoid matching single-letter/phonics overrides if preceded by an apostrophe
    # (e.g. don't replace "s" in "Let's" or "t" in "Don't")
    elif len(word) == 1:
        pattern = re.compile(rf"(?<!')\b{re.escape(word)}\b", flags=re.IGNORECASE)
    else:
        pattern = re.compile(rf"\b{re.escape(word)}\b", flags=re.IGNORECASE)
    return pattern.sub(replacement, text)


def _sanitize_for_tts(text: str) -> str:
    # Remove quote wrapping around words to prevent odd phoneme output.
    output = re.sub(r"'([A-Za-z]+)'", r"\1", text)
    output = output.replace("->", " to ")
    # Replace colons with commas unless preceded by "phonemes" or "SLOW"
    output = re.sub(r'(?<!\bphonemes)(?<!\bSLOW):', ',', output)
    output = re.sub(r"\s+", " ", output).strip()
    return output


def overrides_for_level(level: str, overrides: Mapping[str, str]) -> Dict[str, str]:
    """Return the pronunciation overrides that apply on the given level.

    The override table is entirely tier-1 phonics content (single letters and
    consonant-vowel blends like "go", "do", "no"). Those spellings reappear as
    real sight words on tier 2+, where they must be spoken naturally rather than
    sounded out with the tier-1 phoneme. Scope the overrides to tier 1 so a level-1
    blend pronunciation never leaks into a higher level's word.
    """
    from ella_bot.core.constants import tier_of

    if tier_of(level) == 1:
        return dict(overrides)
    return {}


def apply_pronunciation_overrides(text: str, overrides: Mapping[str, str]) -> str:
    """Replace specific words with TTS-friendly pronunciations (for spoken output only)."""
    output = _sanitize_for_tts(text)
    for source_word, spoken_form in overrides.items():
        if not source_word or not spoken_form:
            continue
        output = _replace_word_case_insensitive(output, source_word, spoken_form)

    return _sanitize_for_tts(output)


def build_spoken_feedback_with_overrides(
    feedback: FeedbackResult,
    overrides: Mapping[str, str],
    max_hints: int = 2,
) -> List[str]:
    """Build spoken lines and apply pronunciation overrides for better TTS quality."""
    lines = build_spoken_feedback(feedback=feedback, max_hints=max_hints)
    return [apply_pronunciation_overrides(line, overrides) for line in lines]


def build_targeted_overrides(expected_sentence: str, overrides: Mapping[str, str]) -> Dict[str, str]:
    if not expected_sentence:
        return {}

    clean_target = expected_sentence.strip().lower()
    targeted: Dict[str, str] = {}

    # Check if the entire target sentence is a single word or single phoneme (no spaces)
    if " " not in clean_target:
        # Single word/letter lesson: apply the override if it exists
        if clean_target in overrides:
            targeted[clean_target] = overrides[clean_target]
        return targeted

    # Multi-word sentence lesson:
    # Find all words in the target sentence
    words = re.findall(r"\b[A-Za-z0-9'-]+\b", clean_target)
    for w in words:
        # Skip single-letter overrides (like "a", "i") in multi-word sentences
        # to prevent mangling pronouns/articles in the carrier phrases.
        if len(w) <= 1:
            continue
        # Also skip common open-syllable overrides like "we", "me", "be", "he", "do"
        # in multi-word sentences because they are pronounced standardly in fluent speech.
        if w in {"we", "me", "be", "he", "do", "to", "so", "go", "no", "by", "my"}:
            continue
        if w in overrides:
            targeted[w] = overrides[w]

    return targeted


def build_spoken_feedback_clean(feedback: FeedbackResult, max_hints: int = 2) -> List[str]:
    """Build spoken lines without overrides but with TTS-safe text sanitation."""
    lines = build_spoken_feedback(feedback=feedback, max_hints=max_hints)
    return [_sanitize_for_tts(line) for line in lines]


def build_spoken_feedback_with_coaching(
    feedback: FeedbackResult,
    overrides: Mapping[str, str],
    expected_sentence: str = "",
    max_hints: int = 2,
    validation: Optional[ValidationResult] = None,
) -> List[str]:
    """Build child-facing spoken lines for an attempt, with target model demonstrations and natural word coaching."""
    t_type = get_target_type(expected_sentence)

    # Check if the attempt was successful
    is_correct = (
        "excellent" in feedback.level_message.lower() or
        "wonderful" in feedback.level_message.lower() or
        "that's right" in feedback.level_message.lower() or
        "perfect" in feedback.level_message.lower() or
        "good" in feedback.level_message.lower() or
        "correct" in feedback.level_message.lower() or
        "great" in feedback.level_message.lower() or
        not feedback.pronunciation_hints
    )

    if is_correct:
        return [_sanitize_for_tts(feedback.level_message)]

    # --- INCORRECT ANSWER / COACHING FLOW ---
    lines: List[str] = [_sanitize_for_tts(feedback.level_message)]

    if t_type in ("sound", "word"):
        # For single sounds or single words:
        sound_target, _ = get_level1_sound_and_word(expected_sentence)
        if t_type == "sound":
            lines.append("Alright, let me make the sound for you.")
        else:
            lines.append("Alright, let me read the word for you.")

        target_override = overrides.get(sound_target.lower(), sound_target)
        if target_override.startswith("phonemes:"):
            lines.append(target_override)
        else:
            sentence_line = _sanitize_for_tts(sound_target)
            if sentence_line.endswith((".", "!", "?")):
                lines.append(sentence_line)
            else:
                lines.append(sentence_line + ".")
        lines.append("Now you try!")

    else:
        # For multi-word phrases and sentences:
        target_word = None
        if validation:
            if validation.incorrect_words:
                target_word = validation.incorrect_words[0][0]
            elif validation.missing_words:
                target_word = validation.missing_words[0]

        sentence_line = _sanitize_for_tts(expected_sentence)
        targeted_overrides = build_targeted_overrides(expected_sentence, overrides)
        overridden_sentence = apply_pronunciation_overrides(sentence_line, targeted_overrides)
        if not overridden_sentence.endswith((".", "!", "?")):
            overridden_sentence += "."

        if target_word:
            spoken_target = overrides.get(target_word.lower(), target_word)
            lines.append(f"I noticed you had trouble with the word, {spoken_target}.")
            lines.append(f"Listen closely.")
            lines.append(f"SLOW: {spoken_target}.")
            lines.append(f"Now, let's read the whole {'phrase' if t_type == 'phrase' else 'sentence'} together.")
            lines.append(f"SLOW: {overridden_sentence}")
        else:
            if t_type == "phrase":
                lines.append("Alright, let me read the phrase for you.")
            else:
                lines.append("Alright, let me read the sentence for you.")
            lines.append(f"SLOW: {overridden_sentence}")

        lines.append("Now you try!")

    # Clean and sanitize lines for final playback
    sanitized_lines: List[str] = []
    for line in lines:
        if line.startswith("phonemes:"):
            sanitized_lines.append(line)
        else:
            sanitized_lines.append(_sanitize_for_tts(line))

    return sanitized_lines


_ARPABET_TO_SOUND = {
    "AA": "ah",
    "AE": "a",
    "AH": "uh",
    "AO": "aw",
    "AW": "ow",
    "AY": "ay",
    "B": "b",
    "CH": "ch",
    "D": "d",
    "DH": "th",
    "EH": "eh",
    "ER": "er",
    "EY": "ey",
    "F": "f",
    "G": "g",
    "HH": "h",
    "IH": "ih",
    "IY": "ee",
    "JH": "j",
    "K": "k",
    "L": "l",
    "M": "m",
    "N": "n",
    "NG": "ng",
    "OW": "oh",
    "OY": "oy",
    "P": "p",
    "R": "r",
    "S": "s",
    "SH": "sh",
    "T": "t",
    "TH": "th",
    "UH": "oo",
    "UW": "oo",
    "V": "v",
    "W": "w",
    "Y": "y",
    "Z": "z",
    "ZH": "zh",
}

_VOWEL_CHUNKS = {"a", "ah", "aw", "ow", "ay", "ey", "eh", "ee", "ih", "oh", "oy", "oo", "uh", "er"}


def _strip_stress(arpabet: str) -> List[str]:
    parts = arpabet.split()
    return [re.sub(r"\d", "", p).upper() for p in parts]


def _merge_chunks(units: List[str]) -> List[str]:
    if len(units) == 3 and len(units[0]) <= 2 and units[1] in _VOWEL_CHUNKS and len(units[2]) <= 2:
        return [units[0] + units[1] + units[2]]

    out: List[str] = []
    i = 0
    while i < len(units):
        if i + 2 < len(units) and len(units[i]) <= 2 and units[i + 1] == "uh" and units[i + 2] == "l":
            out.append(units[i] + "ul")
            i += 3
            continue
        if i + 1 < len(units) and len(units[i]) <= 2 and units[i + 1] in _VOWEL_CHUNKS:
            out.append(units[i] + units[i + 1])
            i += 2
            continue
        out.append(units[i])
        i += 1
    return out


def _arpabet_to_coaching(arpabet: str) -> str:
    phones = _strip_stress(arpabet)
    units = [_ARPABET_TO_SOUND.get(phone, phone.lower()) for phone in phones]
    merged = _merge_chunks(units)
    return " ".join(merged)


def auto_pronunciation_coaching(word: str) -> str:
    """Generate a spoken coaching form without manual overrides.

    Strategy:
    1. Use CMU dictionary via `pronouncing` when installed.
    2. Fallback to lightweight syllable splitting.
    """
    w = word.strip().lower()
    if not w:
        return ""

    # Function words are usually clearer when spoken naturally.
    if w in {"the", "a", "an", "to", "on", "in", "of", "and"}:
        return w

    if pronouncing is not None:
        try:
            phones = pronouncing.phones_for_word(w)
            if phones:
                first = phones[0]
                # For short one-syllable words, speaking the plain word is clearer
                # than decomposed phone chunks (e.g., "sits" vs "s ih t s").
                if len(w) <= 5 and pronouncing.syllable_count(first) <= 1:
                    return w
                return _arpabet_to_coaching(first)
        except Exception:
            pass

    return simple_syllable_split(w).replace("-", " ")
