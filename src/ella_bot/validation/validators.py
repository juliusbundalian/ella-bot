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
STRICT_FLUENCY_CONFIDENCE = 0.35


def normalize(text: str) -> List[str]:
    return [token.lower() for token in _WORD_RE.findall(text)]

ASR_HOMOPHONES: Dict[str, set[str]] = {
    "a": {"uh", "ah", "a", "up", "ha"},
    "b": {"buh", "but", "ba", "b", "bah"},
    "c": {"car", "cuh", "cat", "cow", "huh", "her", "cur", "cup", "cut", "come", "co", "can", "with into", "see", "sea"},
    "d": {"duh", "the", "do", "done", "du", "d"},
    "e": {"a", "eh", "ed", "head", "hey", "he", "egg", "it", "the", "in", "eight", "is", "under"},
    "f": {"fah", "fuck", "fe", "fa", "fu", "for", "far", "four", "ha"},
    "g": {"gah", "guh", "gay", "go", "good", "got", "get", "god", "the"},
    "h": {"ha", "huh", "her", "he", "him", "his", "hot", "house"},
    "i": {"ee", "he", "huh", "e", "in", "it", "is", "his", "if", "eat", "hit", "me", "we", "bee", "here"},
    "j": {"juh", "ja", "je", "ju", "jo", "job", "jump", "just"},
    "k": {"kuh", "ka", "ke", "ku", "ko", "key", "keep", "kid", "kill", "come", "car", "cat"},
    "l": {"luh", "la", "le", "lu", "lo", "look", "love", "like", "let", "low"},
    "m": {"muh", "ma", "me", "my", "more", "man", "make", "meow"},
    "n": {"nuh", "na", "ne", "nu", "no", "not", "new", "now", "net"},
    "o": {"oh", "owe", "o", "a", "ah", "all", "or", "on", "of", "off", "old", "go", "so", "no"},
    "p": {"puh", "pa", "pe", "pu", "po", "up", "put", "pop", "pin", "pen", "paper"},
    "q": {"kwuh", "qua", "que", "qui", "quo", "quick", "queen", "quiet"},
    "r": {"ruh", "ra", "re", "ru", "ro", "run", "red", "read", "ride", "ring"},
    "s": {"suh", "sa", "se", "su", "so", "see", "sea", "sun", "sit", "six"},
    "t": {"tuh", "ta", "te", "tu", "to", "two", "the", "that", "this", "ten", "toy"},
    "u": {"oo", "oh", "to", "do", "who", "two", "through", "blue", "new", "true", "up", "us", "wood", "would"},
    "v": {"vuh", "va", "ve", "vu", "vo", "very", "voice", "vote", "van"},
    "w": {"wuh", "wa", "we", "wi", "wo", "wu", "with", "we", "will", "was", "went", "win"},
    "x": {"ks", "box", "fox", "six", "mix", "axe", "taxi"},
    "y": {"yuh", "ya", "ye", "yi", "yo", "yu", "yes", "you", "yellow", "yesterday"},
    "z": {"zuh", "za", "ze", "zi", "zo", "zu", "zoo", "zebra", "zero"},

    # Two-letter consonant-vowel blends
    "ba": {"ba", "bah", "bay", "bar", "but"},
    "be": {"be", "bee", "beh", "bed", "bet", "bell", "bay", "bear", "bare", "but"},
    "bi": {"bi", "bee", "bee", "bih", "big", "bit", "by", "buy"},
    "bo": {"bo", "boh", "boy", "box", "boat", "bow"},
    "bu": {"bu", "buh", "but", "bus", "bug"},

    "ca": {"ca", "cah", "cat", "car", "can"},
    "ce": {"ce", "seh", "say", "set", "sell", "send", "sad", "she", "keh", "kay", "care"},
    "ci": {"ci", "kee", "see", "sea", "key", "sit", "six"},
    "co": {"co", "coh", "cop", "cot", "cow", "cold"},
    "cu": {"cu", "cuh", "cut", "cup", "cub"},

    "da": {"da", "dah", "day", "dad", "dark"},
    "de": {"de", "dee", "deh", "dead", "debt", "dell", "dare", "they", "then", "day"},
    "di": {"di", "dee", "dih", "dig", "did", "dip", "die", "day"},
    "do": {"do", "doh", "dog", "dot", "doll", "done"},
    "du": {"du", "duh", "duck", "dust", "dull"},

    "fa": {"fa", "fah", "fat", "far", "fan"},
    "fe": {"fe", "feh", "fed", "fell", "fair", "for", "fay"},
    "fi": {"fi", "fee", "fih", "fit", "fig", "five", "fly"},
    "fo": {"fo", "foh", "fox", "for", "fog"},
    "fu": {"fu", "fuh", "fun", "full", "fur"},

    "ga": {"ga", "gah", "gap", "gas"},
    "ge": {"ge", "geh", "get", "gem", "gear", "go", "gay"},
    "gi": {"gi", "gee", "gih", "gig", "give", "guy"},
    "go": {"go", "goh", "got", "god"},
    "gu": {"gu", "guh", "gum", "gun", "gut"},

    "ha": {"ha", "hah", "hat", "has", "had"},
    "he": {"he", "heh", "hay", "hey", "head", "hen", "hair", "her", "him"},
    "hi": {"hi", "hee", "hih", "hit", "him", "his", "high"},
    "ho": {"ho", "hoh", "hot", "hop", "how"},
    "hu": {"hu", "huh", "hug", "hut", "hum"},

    "ja": {"ja", "jah", "jam", "jar"},
    "je": {"je", "jeh", "jet", "gem", "jail", "jay"},
    "ji": {"ji", "jee", "jih", "jig", "jim"},
    "jo": {"jo", "joh", "job", "jog", "joy"},
    "ju": {"ju", "juh", "jug", "jump", "just"},

    "ka": {"ka", "kah", "cat", "car"},
    "ke": {"ke", "keh", "keg", "key", "care", "can", "kay"},
    "ki": {"ki", "kee", "kih", "kid", "kit", "kin"},
    "ko": {"ko", "koh", "cop", "cot"},
    "ku": {"ku", "kuh", "cup", "cub"},

    "la": {"la", "lah", "lap", "lad"},
    "le": {"le", "leh", "lay", "let", "led", "leg", "less", "lair", "late"},
    "li": {"li", "lee", "lih", "lip", "lit", "lid", "like"},
    "lo": {"lo", "loh", "lot", "log", "low"},
    "lu": {"lu", "luh", "luck", "lug"},

    "ma": {"ma", "mah", "map", "man", "mad"},
    "me": {"me", "meh", "may", "met", "men", "mail", "my"},
    "mi": {"mi", "mee", "mih", "mix", "mid", "my"},
    "mo": {"mo", "moh", "mop", "mom", "more"},
    "mu": {"mu", "muh", "mud", "mug"},

    "na": {"na", "nah", "nap", "not"},
    "ne": {"ne", "neh", "nay", "net", "nest", "near", "no", "any"},
    "ni": {"ni", "nee", "nih", "nit", "nil", "night"},
    "no": {"no", "noh", "not", "now"},
    "nu": {"nu", "nuh", "nut", "nun"},

    "pa": {"pa", "pah", "pat", "pan", "pad"},
    "pe": {"pe", "peh", "pay", "pet", "pen", "peg", "pair", "page"},
    "pi": {"pi", "pee", "pih", "pin", "pig", "pit", "pie"},
    "po": {"po", "poh", "pot", "pop", "pod"},
    "pu": {"pu", "puh", "pup", "pub", "push"},

    "ra": {"ra", "rah", "rat", "ran", "rag"},
    "re": {"re", "reh", "ray", "red", "read", "rent", "rare", "are"},
    "ri": {"ri", "ree", "rih", "rib", "rid", "ring", "right"},
    "ro": {"ro", "roh", "rot", "rob", "rod", "row"},
    "ru": {"ru", "ruh", "run", "rug", "rub"},

    "sa": {"sa", "sah", "sad", "sat", "sam"},
    "se": {"se", "seh", "say", "set", "sell", "send", "sad", "she"},
    "si": {"si", "see", "sea", "sih", "sit", "six", "sing", "say"},
    "so": {"so", "soh", "sob", "sod", "son", "saw"},
    "su": {"su", "suh", "sun", "sub", "such"},

    "ta": {"ta", "tah", "tap", "tan", "tag"},
    "te": {"te", "teh", "tay", "ten", "tell", "ted", "tent", "tear", "take", "to"},
    "ti": {"ti", "tee", "tih", "tin", "tip", "ticket", "tie"},
    "to": {"to", "toh", "top", "toy", "two", "to"},
    "tu": {"tu", "tuh", "tub", "tug", "turn"},

    "va": {"va", "vah", "van", "vast"},
    "ve": {"ve", "veh", "very", "veil", "vet", "vow"},
    "vi": {"vi", "vee", "vih", "win", "view"},
    "vo": {"vo", "voh", "vote", "voice"},
    "vu": {"vu", "vuh", "vulcan"},

    "wa": {"wa", "wah", "wet", "one", "was", "war"},
    "we": {"we", "weh", "way", "wet", "well", "web", "wear"},
    "wi": {"wi", "wee", "wih", "win", "wig", "wit", "with", "why"},
    "wo": {"wo", "woh", "won", "one", "would"},
    "wu": {"wu", "wuh", "wood", "wool"},

    "ya": {"ya", "yah", "yak", "yard"},
    "ye": {"ye", "yeh", "yay", "yes", "yet", "yell", "year"},
    "yi": {"yi", "yee", "yih", "year", "yield"},
    "yo": {"yo", "yoh", "you", "your", "yolk"},
    "yu": {"yu", "yuh", "yum", "yuck"},

    "za": {"za", "zah", "zap", "zar"},
    "ze": {"ze", "zeh", "zee", "zen", "zest"},
    "zi": {"zi", "zee", "zih", "zip", "zinc"},
    "zo": {"zo", "zoh", "zoo", "zone"},
    "zu": {"zu", "zuh", "zoo"}
}

STRICT_HOMOPHONES: Dict[str, set[str]] = {
    "be": {"bee"},
    "to": {"too", "two"},
    "too": {"to", "two"},
    "two": {"to", "too"},
    "their": {"there", "they're"},
    "there": {"their", "they're"},
    "they're": {"their", "there"},
    "your": {"you're"},
    "you're": {"your"},
    "its": {"it's"},
    "it's": {"its"},
    "here": {"hear"},
    "hear": {"here"},
    "right": {"write"},
    "write": {"right"},
    "one": {"won"},
    "won": {"one"},
    "know": {"no"},
    "no": {"know"},
    "see": {"sea"},
    "sea": {"see"},
    "read": {"red"},
    "red": {"read"},
    "wise": {"weiss"},
    "weiss": {"wise"},
    "ana": {"anna"},
    "anna": {"ana"},
    "teacher's": {"teachers"},
    "teachers": {"teacher's"},
    "store's": {"stores"},
    "stores": {"store's"},
    "consumer's": {"consumers"},
    "consumers": {"consumer's"},
    "jose's": {"joses"},
    "joses": {"jose's"},
    "god's": {"gods"},
    "gods": {"god's"},
    "mother's": {"mothers"},
    "mothers": {"mother's"},
    "other's": {"others"},
    "others": {"other's"},
    "ana's": {"anas", "annas"},
    "anas": {"ana's"},
    "annas": {"ana's"},
}

def align_words(
    expected: List[str],
    spoken: List[str],
    spoken_confidences: List[float] | None = None,
    strict_fluency: bool = False
) -> List[AlignmentToken]:
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
            expected_word = expected[i - 1]
            spoken_word = spoken[j - 1]

            is_match = expected_word == spoken_word or spoken_word in STRICT_HOMOPHONES.get(expected_word, set())

            # Dynamic Coarticulation Forgiveness:
            # Vosk often drops subtle suffixes like 'ed' or 's' when spoken fluently before consonants.
            if not is_match:
                # 1. Past Tense Verbs (e.g., liked -> like, walked -> walk)
                if expected_word.endswith("ed"):
                    if spoken_word in (expected_word[:-1], expected_word[:-2]):
                        is_match = True

                # 2. Possessives (e.g., teacher's -> teachers, ana's -> ana)
                elif expected_word.endswith("'s"):
                    base = expected_word[:-2]
                    plural = base + "s"
                    if spoken_word in (base, plural):
                        is_match = True

            # Enforce 35% acoustic fluency requirement for higher levels.
            if is_match and strict_fluency and spoken_confidences and j - 1 < len(spoken_confidences):
                if spoken_confidences[j - 1] < STRICT_FLUENCY_CONFIDENCE:
                    is_match = False

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


def validate_spoken_text(
    expected_sentence: str,
    spoken_sentence: str,
    spoken_confidences: List[float] | None = None,
    strict_fluency: bool = False
) -> ValidationResult:
    """Compare spoken text to expected text and return detailed validation results."""
    expected_lower = expected_sentence.lower()
    spoken_lower = spoken_sentence.lower()

    # --- ASR Error Correction Pipeline ---
    # Vosk's offline N-gram model frequently forces uncommon curriculum words into
    # common multi-word English phrases (e.g., "ana" -> "and i").
    # If the target curriculum word is in the expected sentence, we safely reverse the known hallucination.
    ASR_CORRECTIONS = {
        "ana": ["and i", "and know", "anna"],
        "agony": ["have any"],
        "respectfully": ["respect will", "respectful"],
        "stated": ["stay that", "state and"],
        "consumer's": ["consumers", "that the human", "the human"],
        "store's": ["stores", "stars", "story"],
        "told": ["default"],
        "creative": ["predate of"],
        "clear format": ["they are former"],
        "choose a": ["she a"],
        "compose a": ["composer"],
        "fine": ["find"],
        "into": ["enter"],
        "relatable": ["related"],
        "youtube": ["you tube"],
        "oral": ["or a"],
        "carry": ["harry"],
        "face": ["these"],
        "effortless act": ["effortless sack"],
        "meaningful work": ["meaningful were"],
    }

    for target_word, hallucinations in ASR_CORRECTIONS.items():
        if target_word in expected_lower:
            for bad_phrase in hallucinations:
                spoken_lower = spoken_lower.replace(bad_phrase, target_word)

    expected = normalize(expected_lower)
    spoken = normalize(spoken_lower)

    # Special extremely child-friendly rule for single-word / single-sound lessons (Level 1 & 2):
    # If the lesson is a single item, and that item (or any of its homophones) is detected
    # anywhere in the spoken words, we treat it as 100% correct, ignoring surrounding static/noise.
    is_single_item_lesson = len(expected) == 1
    if is_single_item_lesson:
        target = expected[0]
        homophones = ASR_HOMOPHONES.get(target, set())
        has_matching_spoken_word = False
        matching_word = ""
        for sp in spoken:
            if sp == target or sp in homophones:
                has_matching_spoken_word = True
                matching_word = sp
                break

        if has_matching_spoken_word:
            alignment = [AlignmentToken(expected=target, spoken=matching_word, op="equal")]
            return ValidationResult(
                wer=0.0,
                accuracy=1.0,
                missing_words=[],
                incorrect_words=[],
                extra_words=[],
                alignment=alignment,
            )

    alignment = align_words(expected, spoken, spoken_confidences, strict_fluency)
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
