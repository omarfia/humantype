"""Typo generation: error decisions, wrong-word computation, AutoCorrect set."""

from __future__ import annotations

import random

from . import keymaps

# Common misspellings that Word AutoCorrect fixes by default.  When
# --word-autocorrect is on, humantype avoids generating these typos (Word
# would silently fix them, which would break our backspace correction model).
AUTOCORRECT_FIXES = {
    "teh": "the", "adn": "and", "taht": "that", "ti": "it", "fo": "of",
    "recieve": "receive", "wierd": "weird", "seperate": "separate",
    "definately": "definitely", "occured": "occurred", "untill": "until",
    "alot": "a lot", "tommorow": "tomorrow", "tommorrow": "tomorrow",
    "beleive": "believe", "acheive": "achieve", "freind": "friend",
    "buisness": "business", "calender": "calendar", "enviroment": "environment",
    "goverment": "government", "happend": "happened", "neccessary": "necessary",
    "noticable": "noticeable", "occurence": "occurrence", "posession": "possession",
    "privelege": "privilege", "publically": "publicly", "sucess": "success",
    "sucessful": "successful", "tendancy": "tendency", "thier": "their",
    "truely": "truly", "wether": "weather", "wich": "which", "abotu": "about",
    "agian": "again", "begining": "beginning", "comming": "coming",
    "do'nt": "don't", "does'nt": "doesn't", "is'nt": "isn't",
}

# A small list of very frequent words used as a cheap "rare word" proxy.
COMMON_WORDS = {
    "the", "be", "to", "of", "and", "a", "in", "that", "have", "i", "it",
    "for", "not", "on", "with", "he", "as", "you", "do", "at", "this",
    "but", "his", "by", "from", "they", "we", "say", "her", "she", "or",
    "an", "will", "my", "one", "all", "would", "there", "their", "what",
    "so", "up", "out", "if", "about", "who", "get", "which", "go", "me",
    "when", "make", "can", "like", "time", "no", "just", "him", "know",
    "take", "people", "into", "year", "your", "good", "some", "could",
    "them", "see", "other", "than", "then", "now", "look", "only", "come",
    "its", "over", "think", "also", "back", "after", "use", "two", "how",
    "our", "work", "first", "well", "way", "even", "new", "want", "because",
    "any", "these", "give", "day", "most", "us", "is", "are", "was", "were",
    "been", "has", "had", "did", "said", "each", "many", "more", "where",
    "very", "should", "through", "being", "much", "before", "great", "old",
    "little", "world", "high", "every", "near", "add", "food", "between",
    "own", "below", "country", "plant", "last", "school", "father", "keep",
    "tree", "never", "start", "city", "earth", "eye", "light", "thought",
    "head", "under", "story", "saw", "left", "don't", "few", "while",
    "along", "might", "close", "something", "seem", "next", "hard", "open",
    "example", "begin", "life", "always", "those", "both", "paper", "together",
    "got", "group", "often", "run", "important", "until", "children", "side",
    "feet", "car", "mile", "night", "walk", "white", "sea", "began", "grow",
    "took", "river", "four", "carry", "state", "once", "book", "hear", "stop",
    "without", "second", "late", "miss", "idea", "enough", "eat", "face",
    "watch", "far", "indian", "real", "almost", "let", "above", "girl",
    "sometimes", "mountain", "cut", "young", "talk", "soon", "list", "song",
    "being", "leave", "family", "it's", "body", "music", "color", "stand",
    "sun", "question", "fish", "area", "mark", "dog", "horse", "bird",
    "problem", "complete", "room", "knew", "since", "ever", "piece", "told",
    "usually", "didn't", "friends", "easy", "heard", "order", "red", "door",
    "sure", "become", "top", "ship", "across", "today", "during", "short",
    "better", "best", "however", "low", "hours", "black", "products",
    "happened", "whole", "measure", "remember", "early", "waves", "reached",
    "listen", "wind", "rock", "space", "covered", "fast", "several", "hold",
    "himself", "toward", "five", "step", "morning", "passed", "vowel", "true",
    "hundred", "against", "pattern", "numeral", "table", "north", "slowly",
    "money", "map", "farm", "pulled", "draw", "voice", "seen", "cold", "cried",
    "plan", "notice", "south", "sing", "war", "ground", "fall", "king", "town",
    "i'll", "unit", "figure", "certain", "field", "travel", "wood", "fire",
    "upon", "done", "english", "road", "halt", "ten", "fly", "gave", "box",
    "finally", "wait", "correct", "oh", "quickly", "person", "became", "shown",
    "minutes", "strong", "verb", "stars", "front", "feel", "fact", "inches",
    "street", "decided", "contain", "course", "surface", "produce", "building",
    "ocean", "class", "nothing", "rest", "carefully", "scientists", "inside",
    "wheels", "stay", "green", "known", "island", "week", "less", "machine",
    "base", "ago", "stood", "plane", "system", "behind", "ran", "round",
    "boat", "game", "force", "brought", "understand", "warm", "common",
    "bring", "explain", "dry", "though", "language", "shape", "deep",
    "thousands", "yes", "clear", "equation", "yet", "government", "filled",
    "heat", "full", "hot", "check", "object", "am", "rule", "among", "noun",
    "power", "cannot", "able", "six", "size", "dark", "ball", "material",
    "special", "heavy", "fine", "pair", "circle", "include", "built",
}


class ErrorSpec:
    """A planned typo.

    type: one of substitution, transposition, doubled, dropped, shift_late.
    pos: index in the word core where the error starts.
    notice_after: how many more characters are typed before it is noticed.
    late: notice the error several words later and navigate back to fix it.
    leave: leave the error uncorrected (for the uncorrected_rate option).
    """

    __slots__ = ("type", "pos", "notice_after", "late", "leave", "wrong_char")

    def __init__(self, type, pos, notice_after=0, late=False, leave=False, wrong_char=None):
        self.type = type
        self.pos = pos
        self.notice_after = notice_after
        self.late = late
        self.leave = leave
        self.wrong_char = wrong_char


def error_spec_from_dict(data: dict) -> ErrorSpec:
    """Build an ErrorSpec from a scripted-mistakes JSON/YAML entry.

    Supported keys:
        type           substitution | transposition | doubled | dropped | shift_late
        pos            character index in the word core (default 0)
        wrong_char     the character to type for a substitution
        notice_after   characters typed before the error is noticed (default 0)
        late           true = notice a few words later and navigate back
        leave          true = leave the error uncorrected
    """
    err_type = str(data.get("type", "")).lower()
    if err_type not in ("substitution", "transposition", "doubled", "dropped", "shift_late"):
        raise ValueError(f"unknown scripted mistake type: {err_type!r}")
    return ErrorSpec(
        type=err_type,
        pos=int(data.get("pos", 0)),
        notice_after=int(data.get("notice_after", 0)),
        late=bool(data.get("late", False)),
        leave=bool(data.get("leave", False)),
        wrong_char=data.get("wrong_char"),
    )


class TypoEngine:
    """Decides which words get typos and what the typos look like."""

    def __init__(self, cfg, rng: random.Random):
        self.cfg = cfg
        self.rng = rng
        self.words_since_error = 999

    # ------------------------------------------------------------- probability
    def error_probability(self, core: str, in_burst: bool) -> float:
        e = self.cfg.errors
        p = self.cfg.typing.error_rate
        length = len(core)
        if length <= 3:
            p *= 0.6
        elif length >= e.long_word_threshold:
            p *= e.long_word_factor
        if length >= 5 and core.lower() not in COMMON_WORDS:
            p *= e.rare_word_factor
        if in_burst:
            p *= e.burst_error_factor
        if self.words_since_error <= e.error_cluster_window:
            p *= e.error_cluster_factor
        return min(p, 0.5)

    # --------------------------------------------------------------- decisions
    def maybe_error(self, core: str, in_burst: bool = False) -> ErrorSpec | None:
        """Return an ErrorSpec for this word, or None if it is typed cleanly."""
        self.words_since_error += 1
        if len(core) < 2 or not core.isalnum():
            return None
        if self.rng.random() > self.error_probability(core, in_burst):
            return None

        spec = self._choose_error(core)
        if spec is None:
            return None

        # With Word AutoCorrect assumed on, skip typos it would silently fix.
        if self.cfg.typing.word_autocorrect == "on":
            wrong = self.wrong_word(core, spec)
            if wrong is not None and wrong.lower() in AUTOCORRECT_FIXES:
                return None

        spec.leave = self.rng.random() < self.cfg.typing.uncorrected_rate
        spec.late = (
            not spec.leave
            and len(core) >= 4
            and self.rng.random() < self.cfg.errors.late_correction_rate
        )
        self.words_since_error = 0
        return spec

    def _choose_error(self, core: str) -> ErrorSpec | None:
        e = self.cfg.errors
        length = len(core)
        options = []
        if length >= 2:
            options.append("substitution")
            options.append("doubled")
            options.append("dropped")
        if length >= 3:
            options.append("transposition")
        if length >= 2 and core[0].isupper() and core[1].islower():
            options.append("shift_late")

        weights = {
            "substitution": e.substitution_weight,
            "transposition": e.transposition_weight,
            "doubled": e.doubled_weight,
            "dropped": e.dropped_weight,
            "shift_late": e.shift_late_weight,
        }
        total = sum(weights.get(o, 0.0) for o in options)
        if total <= 0:
            return None
        pick = self.rng.uniform(0, total)
        cumulative = 0.0
        chosen = options[-1]
        for option in options:
            cumulative += weights.get(option, 0.0)
            if pick <= cumulative:
                chosen = option
                break

        if chosen == "substitution":
            for _ in range(10):
                pos = self.rng.randrange(length)
                ch = core[pos]
                if "a" <= ch.lower() <= "z" and ch.lower() in keymaps.QWERTY_NEIGHBORS:
                    wrong = self.rng.choice(sorted(keymaps.QWERTY_NEIGHBORS[ch.lower()]))
                    if wrong.isalpha() or ch.isdigit():
                        wrong = wrong.upper() if ch.isupper() else wrong
                        if wrong != ch:
                            return self._with_notice(ErrorSpec("substitution", pos, wrong_char=wrong), length)
            return None
        if chosen == "transposition":
            pos = self.rng.randrange(length - 1)
            return self._with_notice(ErrorSpec("transposition", pos), length)
        if chosen == "doubled":
            pos = self.rng.randrange(length)
            return self._with_notice(ErrorSpec("doubled", pos), length)
        if chosen == "dropped":
            pos = self.rng.randrange(length)
            return self._with_notice(ErrorSpec("dropped", pos), length)
        if chosen == "shift_late":
            return self._with_notice(ErrorSpec("shift_late", 0), length)
        return None

    def _with_notice(self, spec: ErrorSpec, length: int) -> ErrorSpec:
        seg_len = {"substitution": 1, "transposition": 2, "doubled": 2,
                   "dropped": 0, "shift_late": 2}[spec.type]
        max_after = max(0, length - (spec.pos + seg_len))
        spec.notice_after = self.rng.randint(0, min(self.cfg.errors.notice_after_max, max_after))
        return spec

    # ------------------------------------------------------------ wrong word
    @staticmethod
    def wrong_word(core: str, spec: ErrorSpec) -> str | None:
        """The word as it appears after the typo (before correction)."""
        p = spec.pos
        if spec.type == "substitution" and spec.wrong_char:
            return core[:p] + spec.wrong_char + core[p + 1:]
        if spec.type == "transposition":
            return core[:p] + core[p + 1] + core[p] + core[p + 2:]
        if spec.type == "doubled":
            return core[:p + 1] + core[p] + core[p + 1:]
        if spec.type == "dropped":
            return core[:p] + core[p + 1:]
        if spec.type == "shift_late":
            return core[:1] + core[1].upper() + core[2:]
        return None

    # ------------------------------------------------------- typed char lists
    @staticmethod
    def wrong_chars(core: str, spec: ErrorSpec) -> list[tuple[str, bool]]:
        """Return (char, is_typo) pairs for the whole core with the error applied."""
        chars = list(core)
        flags = [False] * len(chars)
        p = spec.pos
        if spec.type == "substitution" and spec.wrong_char:
            chars[p] = spec.wrong_char
            flags[p] = True
        elif spec.type == "transposition":
            chars[p], chars[p + 1] = chars[p + 1], chars[p]
            flags[p] = flags[p + 1] = True
        elif spec.type == "doubled":
            chars.insert(p + 1, chars[p])
            flags.insert(p + 1, True)
        elif spec.type == "dropped":
            del chars[p]
            del flags[p]
        elif spec.type == "shift_late":
            chars[1] = chars[1].upper()
            flags[1] = True
        return list(zip(chars, flags))
