"""Tests for the typo engine and the exact-match guarantee of the planner."""

import random

from humantype.config import DEFAULTS, deep_merge, to_namespace
from humantype.errors import ErrorSpec, TypoEngine
from humantype.typer import TypingPlanner


def make_cfg(**overrides):
    return to_namespace(deep_merge(DEFAULTS, overrides))


def base_cfg(extra=None):
    overrides = {
        "typing": {
            "error_rate": 0.25,
            "uncorrected_rate": 0.0,
            "thinking_pause_rate": 0.0,
            "word_autocorrect": "off",
        },
        "errors": {
            "late_correction_rate": 0.6,
            "lose_place_probability": 0.03,
            "notice_after_max": 4,
        },
        "pauses": {"idle_rate_per_hour": 0},
        "sessions": {"count": 1},
        "logging": {"save_interval_minutes": 0},
    }
    overrides = deep_merge(overrides, extra or {})
    return make_cfg(**overrides)


CORPUS = [
    "The quick brown fox jumps over the lazy dog.",
    "She said, \"hello there\" - and then she paused... for a moment.",
    "Typing a 1234 number, an UPPERCASE word, and a very long word like incomprehensible.",
    "teh adn taht recieve seperate wierd words appear here on purpose.",
    "Short. Then a sentence with commas, semicolons; and a question? Yes!",
]


def test_wrong_word_computation():
    engine_cfg = base_cfg()
    rng = random.Random(1)
    engine = TypoEngine(engine_cfg, rng)

    spec = ErrorSpec("substitution", 1, wrong_char="o")
    assert TypoEngine.wrong_word("cat", spec) == "cot"

    spec = ErrorSpec("transposition", 1)
    assert TypoEngine.wrong_word("the", spec) == "teh"

    spec = ErrorSpec("doubled", 1)
    assert TypoEngine.wrong_word("the", spec) == "thhe"

    spec = ErrorSpec("dropped", 1)
    assert TypoEngine.wrong_word("the", spec) == "te"

    spec = ErrorSpec("shift_late", 0)
    assert TypoEngine.wrong_word("The", spec) == "THe"


def test_wrong_chars_lengths():
    assert TypoEngine.wrong_chars("the", ErrorSpec("transposition", 1))[0][0] == "t"
    assert TypoEngine.wrong_chars("the", ErrorSpec("transposition", 1))[1][0] == "e"
    pairs = TypoEngine.wrong_chars("the", ErrorSpec("doubled", 1))
    assert [c for c, _ in pairs] == ["t", "h", "h", "e"]
    pairs = TypoEngine.wrong_chars("the", ErrorSpec("dropped", 1))
    assert [c for c, _ in pairs] == ["t", "e"]


def test_autocorrect_mode_skips_fixable_typos():
    cfg = base_cfg({"typing": {"word_autocorrect": "on", "error_rate": 1.0}})
    engine = TypoEngine(cfg, random.Random(0))
    # With error_rate 1.0 and autocorrect on, "the" must never be mistyped as
    # "teh" (autocorrect would silently fix it), but longer rare words still get
    # errors whenever possible.
    for _ in range(200):
        spec = engine.maybe_error("the", in_burst=False)
        if spec is not None:
            assert TypoEngine.wrong_word("the", spec).lower() != "teh"


def test_planner_exact_match_uncorrected_zero():
    """The final buffer must exactly match the source for many seeds and modes."""
    for autocorrect in ("off", "on"):
        for seed in range(10):
            cfg = base_cfg({"typing": {"word_autocorrect": autocorrect}})
            planner = TypingPlanner(cfg, CORPUS, rng=random.Random(seed))
            planner.plan()
            expected = "\n".join(CORPUS)
            assert planner.buffer == expected, (
                f"mismatch with autocorrect={autocorrect}, seed={seed}"
            )
            # Sanity: events exist and backspaces happened (errors were made).
            types = [e["event_type"] for e in planner.events]
            assert "backspace" in types


def test_planner_exact_match_with_thinking_and_idle():
    cfg = base_cfg({
        "typing": {"thinking_pause_rate": 0.02, "word_autocorrect": "on"},
        "pauses": {"idle_rate_per_hour": 30},
    })
    for seed in range(3):
        planner = TypingPlanner(cfg, CORPUS, rng=random.Random(seed))
        planner.plan()
        assert planner.buffer == "\n".join(CORPUS)


def test_planner_uncorrected_errors_can_differ():
    cfg = base_cfg({"typing": {"uncorrected_rate": 1.0, "error_rate": 0.9}})
    mismatches = 0
    for seed in range(5):
        planner = TypingPlanner(cfg, CORPUS, rng=random.Random(seed))
        planner.plan()
        if planner.buffer != "\n".join(CORPUS):
            mismatches += 1
    assert mismatches > 0


def test_planner_paragraphs_have_enter_events():
    cfg = base_cfg()
    planner = TypingPlanner(cfg, CORPUS, rng=random.Random(3))
    planner.plan()
    enter_count = sum(1 for e in planner.events
                      if e["type"] == "keydown" and e["key"] == "Key.enter")
    assert enter_count == len(CORPUS) - 1


def test_events_are_time_sorted():
    cfg = base_cfg()
    planner = TypingPlanner(cfg, CORPUS, rng=random.Random(7))
    events = planner.plan()
    times = [e["t"] for e in events]
    assert times == sorted(times)


def test_no_paste_events():
    """Every produced character is an individual keystroke (no paste events)."""
    cfg = base_cfg()
    planner = TypingPlanner(cfg, CORPUS, rng=random.Random(2))
    events = planner.plan()
    assert all(e["type"] != "paste" for e in events)
    assert all(e["key"] != "Key.cmd" for e in events)
    assert all("ctrl+v" not in str(e["key"]).lower() for e in events)


def test_no_auto_save_events_when_auto_save_disabled():
    """Ctrl+S must never be planned while auto-save is off (default)."""
    cfg = base_cfg({"pauses": {"idle_rate_per_hour": 1000}})
    planner = TypingPlanner(cfg, CORPUS, rng=random.Random(1))
    planner.next_idle_at = 0.0  # force an idle gap early in the plan
    events = planner.plan()
    assert any(e["event_type"] == "pause" and e["detail"] == "idle" for e in events)
    assert all(e["event_type"] != "save" for e in events)


def test_auto_save_events_appear_when_auto_save_enabled():
    cfg = base_cfg({
        "pauses": {"idle_rate_per_hour": 1000},
        "logging": {"save_interval_minutes": 1},
    })
    planner = TypingPlanner(cfg, CORPUS, rng=random.Random(1))
    planner.next_idle_at = 0.0
    events = planner.plan()
    assert any(e["event_type"] == "save" for e in events)


def test_run_typing_dry_run_with_progress_offset(tmp_path):
    """Start/end slicing keeps the exact-match guarantee and reports offsets."""
    from humantype.typer import run_typing
    source = tmp_path / "slice.md"
    source.write_text("One.\n\nTwo.\n\nThree.", encoding="utf-8")
    cfg = base_cfg({"typing": {"dry_run": True}})
    result = run_typing(cfg, ["Two."], str(source), progress_offset=1)
    assert result["aborted"] is False
    assert result["buffer_matches"] is True


def test_scripted_mistakes_apply_and_only_scripted_ones():
    cfg = base_cfg({
        "typing": {"error_rate": 0.9, "word_autocorrect": "off"},
        "errors": {"scripted_mistakes": [
            {"paragraph": 1, "word": 2, "type": "transposition",
             "pos": 1, "notice_after": 1},
        ]},
    })
    planner = TypingPlanner(cfg, CORPUS, rng=random.Random(0))
    events = planner.plan()
    assert planner.buffer == "\n".join(CORPUS)
    typo_events = [e for e in events if e["event_type"] == "typo"]
    # "quick" -> "qiuck": exactly the two transposed characters are typos,
    # and no random errors occur anywhere else.
    assert len(typo_events) == 2
    assert sorted(e["detail"] for e in typo_events) == ["char:i", "char:u"]


def test_scripted_mistakes_word_text_matching():
    cfg = base_cfg({
        "typing": {"error_rate": 0.9},
        "errors": {"scripted_mistakes": [
            {"word_text": "brown", "type": "doubled", "pos": 0, "notice_after": 0},
        ]},
    })
    planner = TypingPlanner(cfg, CORPUS, rng=random.Random(1))
    events = planner.plan()
    assert planner.buffer == "\n".join(CORPUS)
    typo_events = [e for e in events if e["event_type"] == "typo"]
    assert len(typo_events) == 2
    assert all(e["detail"] == "char:b" for e in typo_events)


def test_scripted_mistakes_leave_uncorrected():
    cfg = base_cfg({
        "typing": {"word_autocorrect": "off"},
        "errors": {"scripted_mistakes": [
            {"word_index": 0, "type": "substitution", "pos": 0,
             "wrong_char": "F", "leave": True},
        ]},
    })
    planner = TypingPlanner(cfg, CORPUS, rng=random.Random(2))
    planner.plan()
    assert "Fhe" in planner.buffer
    assert planner.buffer != "\n".join(CORPUS)
