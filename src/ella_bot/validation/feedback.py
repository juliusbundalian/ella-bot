from __future__ import annotations

import re
from difflib import SequenceMatcher
from dataclasses import dataclass
from typing import Dict, List, Mapping

from ella_bot.validation.validators import ValidationResult

try:
    import pronouncing
except Exception:
    pronouncing = None


@dataclass
class FeedbackResult:
    level_message: str
    detailed_messages: List[str]
    pronunciation_hints: List[str]


def score_to_level(accuracy: float) -> str:
    if accuracy >= 0.95:
        return "Correct!"
    if accuracy >= 0.75:
        return "Almost there!"
    return "Try again"


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


def pronunciation_hints(
    validation: ValidationResult,
    spoken_confidence_by_word: Dict[str, float],
) -> List[str]:
    hints: List[str] = []

    for expected, spoken in validation.incorrect_words:
        conf = spoken_confidence_by_word.get(spoken, 0.0)
        similarity = SequenceMatcher(None, expected, spoken).ratio()

        if conf < 0.65 or similarity < 0.7:
            hints.append(f"Let's try the word '{expected}' again.")

    for missing in validation.missing_words:
        hints.append(f"You missed the word '{missing}'. Try saying it clearly.")

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
    pattern = re.compile(rf"\b{re.escape(word)}\b", flags=re.IGNORECASE)
    return pattern.sub(replacement, text)


def _sanitize_for_tts(text: str) -> str:
    # Remove quote wrapping around words to prevent odd phoneme output.
    output = re.sub(r"'([A-Za-z]+)'", r"\1", text)
    output = output.replace("->", " to ")
    output = output.replace(":", ",")
    output = re.sub(r"\s+", " ", output).strip()
    return output


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


def build_spoken_feedback_clean(feedback: FeedbackResult, max_hints: int = 2) -> List[str]:
    """Build spoken lines without overrides but with TTS-safe text sanitation."""
    lines = build_spoken_feedback(feedback=feedback, max_hints=max_hints)
    return [_sanitize_for_tts(line) for line in lines]


def build_spoken_feedback_with_coaching(
    feedback: FeedbackResult,
    overrides: Mapping[str, str],
    expected_sentence: str = "",
    max_hints: int = 2,
) -> List[str]:
    """Build spoken lines and add explicit pronunciation coaching for matched words.

    This is stronger than plain text replacement because it adds separate coaching lines,
    e.g. "Say this word like, tay buhl".
    """
    lines = build_spoken_feedback_with_overrides(
        feedback=feedback,
        overrides=overrides,
        max_hints=max_hints,
    )

    sentence_line = _sanitize_for_tts(expected_sentence)
    if sentence_line:
        lines.append(_sanitize_for_tts(f"Listen to the full sentence, {sentence_line}."))

    coaching: List[str] = []
    for hint in feedback.pronunciation_hints[:max_hints]:
        match = re.search(r"'([A-Za-z]+)'", hint)
        if not match:
            continue
        word = match.group(1).lower()
        spoken_form = overrides.get(word) or auto_pronunciation_coaching(word)
        if spoken_form:
            coaching.append(_sanitize_for_tts(f"Say this word like, {spoken_form}."))

    return lines + coaching[:max_hints]


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
