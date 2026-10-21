"""Timing model: lognormal inter-key delays, bigram/finger effects, drift."""

from __future__ import annotations

import math
import random

from . import keymaps

# Characters that trigger a sentence / comma pause right after they are typed.
_SENTENCE_ENDERS = set(".!?")
_COMMA_ENDERS = set(",;:")


class TimingModel:
    """Samples realistic human timing values from the active configuration."""

    def __init__(self, cfg, rng: random.Random):
        self.cfg = cfg
        self.rng = rng
        self.base_mean = 12.0 / cfg.typing.wpm  # seconds per keystroke
        self.sigma = cfg.timing.lognormal_sigma

    # ------------------------------------------------------------------ drift
    def speed_factor(self, now: float) -> float:
        """Warm-up at the start, gradual fatigue later in the session."""
        t = self.cfg.timing
        if now < t.warmup_seconds:
            return t.warmup_factor + (1.0 - t.warmup_factor) * (now / t.warmup_seconds)
        if now < t.fatigue_onset_seconds:
            return 1.0
        span = max(1.0, t.fatigue_full_seconds - t.fatigue_onset_seconds)
        progress = min(1.0, (now - t.fatigue_onset_seconds) / span)
        return 1.0 - (1.0 - t.fatigue_factor) * progress

    # ------------------------------------------------------------- distributions
    def lognormal(self, mean: float, lo: float, hi: float, sigma: float | None = None) -> float:
        """Sample a lognormal value with the requested arithmetic mean."""
        sigma = self.sigma if sigma is None else sigma
        if mean <= 0:
            return lo
        mu = math.log(max(mean, 1e-9)) - (sigma ** 2) / 2.0
        value = self.rng.lognormvariate(mu, sigma)
        return min(hi, max(lo, value))

    def uniform(self, lo: float, hi: float) -> float:
        return self.rng.uniform(lo, hi)

    def hold_time(self) -> float:
        return self.uniform(self.cfg.timing.hold_min, self.cfg.timing.hold_max)

    # ----------------------------------------------------------- inter-key delay
    def inter_key_delay(
        self,
        now: float,
        prev_char: str | None,
        current_char: str | None,
        in_burst: bool = False,
        error_cluster: bool = False,
    ) -> float:
        """Delay *after* `prev_char` leading to `current_char`."""
        t = self.cfg.timing
        mult = 1.0

        if current_char is not None:
            pair = (prev_char or "").lower() + current_char.lower()
            bigram_speed = t.common_bigram_speed
            if isinstance(bigram_speed, dict):
                if pair in bigram_speed:
                    mult *= bigram_speed[pair]
            elif pair in keymaps.COMMON_BIGRAMS:
                mult *= bigram_speed
            if current_char.isupper():
                mult *= t.capital_slow
            if current_char.isdigit():
                mult *= t.digit_slow
            if current_char in _SENTENCE_ENDERS | _COMMA_ENDERS:
                mult *= t.punctuation_slow
            elif not current_char.isalnum() and current_char not in " ":
                mult *= t.punctuation_slow
            if prev_char and current_char and prev_char != " " and current_char != " ":
                if keymaps.same_finger(prev_char, current_char):
                    mult *= t.same_finger_slow
                elif keymaps.alternate_hands(prev_char, current_char):
                    mult *= t.alternate_hand_speed

        if in_burst:
            mult *= t.burst_speed
        if error_cluster:
            mult *= t.error_cluster_slow

        speed = self.speed_factor(now)
        mean = self.base_mean * mult / speed
        return self.lognormal(mean, t.min_delay, t.max_delay)

    def backspace_delay(self) -> float:
        return self.uniform(0.05, 0.16)

    def tap_delay(self, key: str) -> float:
        if key in ("Key.backspace",):
            return self.backspace_delay()
        if key == "Key.enter":
            return self.uniform(0.15, 0.4)
        return self.uniform(0.08, 0.25)

    # ------------------------------------------------------------------ pauses
    def word_pause(self) -> float:
        t = self.cfg.timing
        return self.lognormal(t.word_pause_mean, t.word_pause_min, t.word_pause_max)

    def comma_pause(self) -> float:
        t = self.cfg.timing
        return self.lognormal(t.comma_pause_mean, t.comma_pause_min, t.comma_pause_max)

    def sentence_pause(self) -> float:
        t = self.cfg.timing
        return self.lognormal(t.sentence_pause_mean, t.sentence_pause_min, t.sentence_pause_max)

    def paragraph_pause(self) -> float:
        t = self.cfg.timing
        return self.lognormal(t.paragraph_pause_mean, t.paragraph_pause_min, t.paragraph_pause_max)

    def chunk_pause(self) -> float:
        t = self.cfg.timing
        return self.uniform(t.chunk_pause_min, t.chunk_pause_max)

    def thinking_pause(self) -> float:
        t = self.cfg.typing
        return self.uniform(t.thinking_pause_min, t.thinking_pause_max)

    def idle_pause(self) -> float:
        p = self.cfg.pauses
        return self.uniform(p.idle_min, p.idle_max)

    def correction_pause(self) -> float:
        return self.uniform(0.20, 0.70)

    def chunk_sizes(self, n_words: int) -> list[int]:
        """Split `n_words` into chunk sizes of 3-8 words."""
        t = self.cfg.timing
        sizes = []
        remaining = n_words
        while remaining > 0:
            size = self.rng.randint(t.chunk_words_min, t.chunk_words_max)
            size = min(size, remaining)
            if remaining - size == 1 and size < t.chunk_words_max:
                size += 1  # avoid a dangling 1-word chunk
            sizes.append(size)
            remaining -= size
        return sizes
