from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class AlignmentToken:
    expected: str
    spoken: str
    op: str  # equal | sub | del | ins


@dataclass
class ValidationResult:
    wer: float
    accuracy: float
    missing_words: List[str]
    incorrect_words: List[Tuple[str, str]]
    extra_words: List[str]
    alignment: List[AlignmentToken]


_WORD_RE = re.compile(r"[a-zA-Z']+")


def normalize(text: str) -> List[str]:
    return [token.lower() for token in _WORD_RE.findall(text)]

ASR_HOMOPHONES: Dict[str, set[str]] = {
    "a": {"uh", "ah"},
    "b": {"bee", "be"},
    "c": {"see", "sea"},
    "d": {"dee", "the"},
    "e": {"ee"},
    "f": {"ef", "eff"},
    "g": {"jee", "gee"},
    "h": {"aitch"},
    "i": {"eye", "aye"},
    "j": {"jay"},
    "k": {"kay"},
    "l": {"el", "ell"},
    "m": {"em"},
    "n": {"en", "in", "an"},
    "o": {"oh", "owe"},
    "p": {"pee", "pea"},
    "q": {"cue", "queue"},
    "r": {"are", "our"},
    "s": {"es", "ess", "is", "as"},
    "t": {"tee", "tea"},
    "u": {"you", "ewe"},
    "v": {"vee"},
    "w": {"doubleyou"},
    "x": {"ex"},
    "y": {"why"},
    "z": {"zee"}
}

def align_words(expected: List[str], spoken: List[str]) -> List[AlignmentToken]:
    n, m = len(expected), len(spoken)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    bt: List[List[Tuple[int, int, str] | None]] = [[None] * (m + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        dp[i][0] = i
        bt[i][0] = (i - 1, 0, "del")
    for j in range(1, m + 1):
        dp[0][j] = j
        bt[0][j] = (0, j - 1, "ins")

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            is_match = expected[i - 1] == spoken[j - 1] or spoken[j - 1] in ASR_HOMOPHONES.get(expected[i - 1], set())
            cost_sub = 0 if is_match else 1
            choices = [
                (dp[i - 1][j] + 1, (i - 1, j, "del")),
                (dp[i][j - 1] + 1, (i, j - 1, "ins")),
                (dp[i - 1][j - 1] + cost_sub, (i - 1, j - 1, "equal" if cost_sub == 0 else "sub")),
            ]
            best = min(choices, key=lambda x: x[0])
            dp[i][j] = best[0]
            bt[i][j] = best[1]

    out: List[AlignmentToken] = []
    i, j = n, m
    while i > 0 or j > 0:
        prev = bt[i][j]
        if prev is None:
            break
        pi, pj, op = prev
        if op == "equal" or op == "sub":
            out.append(AlignmentToken(expected=expected[i - 1], spoken=spoken[j - 1], op=op))
        elif op == "del":
            out.append(AlignmentToken(expected=expected[i - 1], spoken="", op=op))
        else:
            out.append(AlignmentToken(expected="", spoken=spoken[j - 1], op=op))
        i, j = pi, pj

    out.reverse()
    return out


def validate_spoken_text(expected_sentence: str, spoken_sentence: str) -> ValidationResult:
    expected = normalize(expected_sentence)
    spoken = normalize(spoken_sentence)

    alignment = align_words(expected, spoken)
    missing_words = [a.expected for a in alignment if a.op == "del"]
    incorrect_words = [(a.expected, a.spoken) for a in alignment if a.op == "sub"]
    extra_words = [a.spoken for a in alignment if a.op == "ins"]

    edits = len(missing_words) + len(incorrect_words) + len(extra_words)
    wer = edits / max(1, len(expected))
    accuracy = max(0.0, 1.0 - wer)

    return ValidationResult(
        wer=wer,
        accuracy=accuracy,
        missing_words=missing_words,
        incorrect_words=incorrect_words,
        extra_words=extra_words,
        alignment=alignment,
    )


def build_highlighted_expected(alignment: List[AlignmentToken]) -> str:
    """Wrap non-matching expected words in brackets for simple UI highlighting."""
    output: List[str] = []
    for item in alignment:
        if item.expected == "":
            continue
        if item.op == "equal":
            output.append(item.expected)
        else:
            output.append(f"[{item.expected}]")
    return " ".join(output)


def spoken_word_confidence_map(spoken_tokens: List[str], confidences: List[float]) -> Dict[str, float]:
    """Map each spoken token to its latest confidence value."""
    out: Dict[str, float] = {}
    for token, conf in zip(spoken_tokens, confidences):
        out[token] = conf
    return out
