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


import random

_CORRECT_PHRASES = [
    "Excellent work! That was perfect!",
    "Great job! You read that really well!",
    "Wonderful! You got it!",
    "That's right! Amazing reading!",
    "Perfect! I knew you could do it!",
]

_ALMOST_PHRASES = [
    "So close! You're almost there, just a tiny bit more.",
    "Really good try! You've almost got it.",
    "Nice effort! Let's try that one more time.",
    "That was good! You're really close — let's try again.",
]

_RETRY_PHRASES = [
    "Hmm, let's give that another shot. You can do it!",
    "That's okay! Let's try reading it again.",
    "Don't worry, let's have another go at it!",
    "It's tricky, I know. Let's try one more time!",
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
        
    words = text.split()
    
    # 1. Single character is always a sound (Level 1a, 1b)
    if len(text) == 1:
        return "sound"
        
    # 2. Syllable blends in Level 1c
    level_1c_blends = {
        "ba", "be", "bi", "bo", "bu",
        "ca", "ce", "ci", "co", "cu",
        "da", "de", "di", "do", "du",
        "fa", "fe", "fi", "fo", "fu",
        "ga", "ge", "gi", "go", "gu",
        "ha", "he", "hi", "ho", "hu",
        "ja", "je", "ji", "jo", "ju",
        "ka", "ke", "ki", "ko", "ku",
        "la", "le", "li", "lo", "lu",
        "ma", "me", "mi", "mo", "mu",
        "na", "ne", "ni", "no", "nu",
        "pa", "pe", "pi", "po", "pu",
        "qua", "que", "qui", "quo",
        "ra", "re", "ri", "ro", "ru",
        "sa", "se", "si", "so", "su",
        "ta", "te", "ti", "to", "tu",
        "va", "ve", "vi", "vo", "vu",
        "wa", "we", "wi", "wo", "wu",
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
            "Hmm, let's work on the sound, {word}. Can you say it again?",
            "Let's take another look at, {word}. Give it another try!",
            "The sound, {word}, is a little tricky. Let's practice it!",
        ]
        _MISSING_HINTS = [
            "I think you skipped the sound, {word}. Try including it this time!",
            "Don't forget, {word}! Let's make sure we say the sound.",
        ]
    elif t_type == "word":
        _INCORRECT_HINTS = [
            "Hmm, let's work on the word, {word}. Can you say it again?",
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
            "Hmm, let's work on the word, {word}. Can you say it again?",
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

        if conf < 0.65 or similarity < 0.7:
            template = random.choice(_INCORRECT_HINTS)
            hints.append(template.format(word=expected))

    for missing in validation.missing_words:
        template = random.choice(_MISSING_HINTS)
        hints.append(template.format(word=missing))

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
) -> List[str]:
    """Build spoken lines and add explicit pronunciation coaching for matched words."""
    # 1. Build targeted overrides based only on the expected target sentence words
    targeted_overrides = build_targeted_overrides(expected_sentence, overrides)

    # 2. Build clean spoken feedback carrier lines
    lines = build_spoken_feedback_clean(
        feedback=feedback,
        max_hints=max_hints,
    )

    # 3. Apply targeted overrides to the conversational carrier lines
    # This ensures only target words (like "a" or "t") are overridden in the hints!
    lines = [apply_pronunciation_overrides(line, targeted_overrides) for line in lines]

    # 4. Append target sentence read demonstration with targeted overrides applied
    sentence_line = _sanitize_for_tts(expected_sentence)
    if sentence_line:
        t_type = get_target_type(expected_sentence)
        if t_type == "sound":
            lines.append("Alright, let me make the sound for you.")
        elif t_type == "word":
            lines.append("Alright, let me read the word for you.")
        elif t_type == "phrase":
            lines.append("Alright, let me read the phrase for you.")
        else:
            lines.append("Alright, let me read the sentence for you.")
        overridden_sentence = apply_pronunciation_overrides(sentence_line, targeted_overrides)
        lines.append(overridden_sentence + ".")

    coaching: List[str] = []
    _COACHING_TEMPLATES = [
        "Say it with me, {spoken_form}!",
        "The word sounds like, {spoken_form}. Can you try that?",
        "Listen carefully, {spoken_form}. Now you try!",
    ]
    for hint in feedback.pronunciation_hints[:max_hints]:
        # Match words from comma-separated template format: "..., word. ..."
        match = re.search(r",\s*([A-Za-z]+)[.!?]", hint) or re.search(r"\b([A-Za-z]{3,})\b", hint)
        if not match:
            continue
        word = match.group(1).lower()
        # If this is a multi-word sentence lesson, bypass phonics overrides for common sight words
        # (like "we", "me", "be", "he", "do") which are pronounced standardly in fluent speech.
        if len(expected_sentence.split()) > 1 and word in {"we", "me", "be", "he", "do", "to", "so", "go", "no", "by", "my"}:
            spoken_form = auto_pronunciation_coaching(word)
        else:
            spoken_form = overrides.get(word) or auto_pronunciation_coaching(word)
        if spoken_form:
            template = random.choice(_COACHING_TEMPLATES)
            coaching.append(_sanitize_for_tts(template.format(spoken_form=spoken_form)))

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
