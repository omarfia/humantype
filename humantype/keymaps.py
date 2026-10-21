"""QWERTY layout data: neighbors, fingers, US key mapping, common bigrams."""

from __future__ import annotations

# Adjacent keys for a US QWERTY keyboard.  A mistyped character is usually one
# of these neighbours.  Stored as compact strings, converted to sets below.
_NEIGHBOR_STRINGS = {
    "q": "wa",
    "w": "qeasd",
    "e": "wrsdf",
    "r": "etdfg",
    "t": "ryfgh",
    "y": "tughj",
    "u": "yihjk",
    "i": "uojkl",
    "o": "ipkl",
    "p": "ol",
    "a": "qwszx",
    "s": "qwedazxc",
    "d": "wersf xcv".replace(" ", ""),
    "f": "ertdgcvb",
    "g": "rtyfhvbn",
    "h": "tyugjbnm",
    "j": "yuihknm",
    "k": "uiojlm",
    "l": "iopk",
    "z": "asx",
    "x": "zsdc",
    "c": "xdfv",
    "v": "cfgb",
    "b": "vghn",
    "n": "bhjm",
    "m": "njk",
    "1": "2q",
    "2": "13wq",
    "3": "24ew",
    "4": "35re",
    "5": "46tr",
    "6": "57yt",
    "7": "68uy",
    "8": "79iu",
    "9": "80oi",
    "0": "9po",
}

QWERTY_NEIGHBORS = {k: set(v) for k, v in _NEIGHBOR_STRINGS.items()}

# (hand, finger): hand 'L'/'R'/'B' (both, for space), finger 0=thumb, 1=index,
# 2=middle, 3=ring, 4=pinky.
_FINGER_ROWS = {
    "`1234567890-=": [
        ("L", 4), ("L", 4), ("L", 3), ("L", 2), ("L", 1), ("L", 1),
        ("R", 1), ("R", 1), ("R", 2), ("R", 3), ("R", 4), ("R", 4), ("R", 4),
    ],
    "qwertyuiop[]\\": [
        ("L", 4), ("L", 3), ("L", 2), ("L", 1), ("L", 1),
        ("R", 1), ("R", 1), ("R", 2), ("R", 3), ("R", 4), ("R", 4), ("R", 4), ("R", 4),
    ],
    "asdfghjkl;'": [
        ("L", 4), ("L", 3), ("L", 2), ("L", 1), ("L", 1),
        ("R", 1), ("R", 1), ("R", 2), ("R", 3), ("R", 4), ("R", 4),
    ],
    "zxcvbnm,./": [
        ("L", 4), ("L", 3), ("L", 2), ("L", 1), ("L", 1),
        ("R", 1), ("R", 1), ("R", 2), ("R", 3), ("R", 4),
    ],
}

FINGER_MAP = {}
for row, fingers in _FINGER_ROWS.items():
    for ch, finger in zip(row, fingers):
        FINGER_MAP[ch] = finger
        if "a" <= ch <= "z":
            FINGER_MAP[ch.upper()] = finger
FINGER_MAP[" "] = ("B", 0)

# Common English bigrams typed slightly faster than average.
COMMON_BIGRAMS = {
    "th", "he", "in", "er", "an", "re", "on", "at", "en", "nd", "ti", "es",
    "or", "te", "of", "ed", "is", "it", "al", "ar", "st", "to", "nt", "ng",
    "se", "ha", "as", "ou", "io", "le", "ve", "co", "me", "de", "hi", "ri",
    "ro", "ic", "ne", "ea", "ra", "ce", "li", "ch", "ll", "be", "ma", "si",
    "om", "ur", "wh", "sh", "ta", "wa", "no", "fo", "fi", "ca", "pa", "mo",
}

# Characters that need Shift on a US layout.
_SHIFT_SYMBOLS = {
    "!": "1", "@": "2", "#": "3", "$": "4", "%": "5", "^": "6", "&": "7",
    "*": "8", "(": "9", ")": "0", "_": "-", "+": "=", "{": "[", "}": "]",
    "|": "\\", ":": ";", '"': "'", "<": ",", ">": ".", "?": "/", "~": "`",
}

# Punctuation that is a plain key (no Shift) on a US layout.
_PLAIN_PUNCT = set("`-=[]\\;',./")

# Simple fallbacks for common non-ASCII characters when they cannot be typed
# directly (used only in --keep-originals mode).
UNICODE_FALLBACK = {
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"',
    "\u2013": "-", "\u2014": "-", "\u2015": "-",
    "\u2026": "...", "\u00a0": " ",
    "\u00e9": "e", "\u00e8": "e", "\u00ea": "e", "\u00eb": "e",
    "\u00e0": "a", "\u00e1": "a", "\u00e2": "a", "\u00e4": "a",
    "\u00f6": "o", "\u00f3": "o", "\u00f4": "o",
    "\u00fc": "u", "\u00fa": "u", "\u00fb": "u",
    "\u00f1": "n", "\u00e7": "c", "\u00ed": "i", "\u00ec": "i",
    "\u00ef": "i", "\u00ee": "i",
}


def char_to_key(ch: str):
    """Return (physical_key, needs_shift) for a produced character.

    `physical_key` is what the sender presses; `needs_shift` says whether the
    planner should emit Shift down/up around it.
    """
    if ch == " ":
        return ("Key.space", False)
    if ch == "\n":
        return ("Key.enter", False)
    if ch == "\t":
        return ("Key.tab", False)
    if "a" <= ch <= "z":
        return (ch, False)
    if "A" <= ch <= "Z":
        return (ch.lower(), True)
    if "0" <= ch <= "9":
        return (ch, False)
    if ch in _SHIFT_SYMBOLS:
        return (_SHIFT_SYMBOLS[ch], True)
    if ch in _PLAIN_PUNCT:
        return (ch, False)
    # Unicode or otherwise untypable: try the character itself (works with
    # pynput on Windows/macOS in many cases) and fall back to ASCII.
    if ch in UNICODE_FALLBACK:
        return char_to_key(UNICODE_FALLBACK[ch])
    return (ch, False)


def same_finger(ch1: str, ch2: str) -> bool:
    """True when two produced characters use the same finger."""
    f1 = FINGER_MAP.get(ch1.lower() if ch1.isalpha() else ch1)
    f2 = FINGER_MAP.get(ch2.lower() if ch2.isalpha() else ch2)
    if not f1 or not f2:
        return False
    return f1[0] != "B" and f1 == f2


def alternate_hands(ch1: str, ch2: str) -> bool:
    """True when two characters are typed with different hands (or space)."""
    f1 = FINGER_MAP.get(ch1.lower() if ch1.isalpha() else ch1)
    f2 = FINGER_MAP.get(ch2.lower() if ch2.isalpha() else ch2)
    if not f1 or not f2:
        return False
    if f1[0] == "B" or f2[0] == "B":
        return True
    return f1[0] != f2[0]
