"""Configuration loading: built-in defaults + config.yaml + profile + CLI."""

from __future__ import annotations

import copy
import os
from types import SimpleNamespace

DEFAULTS = {
    "typing": {
        "wpm": 45,
        "countdown": 5,
        "error_rate": 0.03,
        "uncorrected_rate": 0.0,
        "thinking_pause_rate": 0.001,  # per character typed
        "thinking_pause_min": 2.0,
        "thinking_pause_max": 15.0,
        "word_autocorrect": "on",  # on = assume Word AutoCorrect is enabled
        "keep_originals": False,
        "seed": None,
        "backend": "pynput",  # pynput | pyautogui
        "allow_mouse": False,
    },
    "timing": {
        "lognormal_sigma": 0.32,
        "min_delay": 0.02,
        "max_delay": 2.0,
        "common_bigram_speed": 0.85,
        "capital_slow": 1.25,
        "digit_slow": 1.30,
        "punctuation_slow": 1.35,
        "same_finger_slow": 1.30,
        "alternate_hand_speed": 0.90,
        "burst_speed": 0.90,
        "error_cluster_slow": 1.10,
        "word_pause_mean": 0.12,
        "word_pause_min": 0.02,
        "word_pause_max": 0.40,
        "comma_pause_mean": 0.22,
        "comma_pause_min": 0.10,
        "comma_pause_max": 0.45,
        "sentence_pause_mean": 0.45,
        "sentence_pause_min": 0.25,
        "sentence_pause_max": 0.90,
        "paragraph_pause_mean": 1.50,
        "paragraph_pause_min": 0.80,
        "paragraph_pause_max": 3.00,
        "chunk_pause_min": 0.40,
        "chunk_pause_max": 2.00,
        "chunk_words_min": 3,
        "chunk_words_max": 8,
        "hold_min": 0.060,
        "hold_max": 0.130,
        "backspace_delay": 0.10,
        "warmup_factor": 0.85,
        "warmup_seconds": 300,
        "fatigue_factor": 0.85,
        "fatigue_onset_seconds": 1800,
        "fatigue_full_seconds": 3600,
    },
    "errors": {
        "substitution_weight": 0.35,
        "transposition_weight": 0.25,
        "doubled_weight": 0.15,
        "dropped_weight": 0.15,
        "shift_late_weight": 0.05,
        "lose_place_weight": 0.05,
        "notice_after_max": 4,
        "late_correction_rate": 0.20,
        "late_words_max": 3,
        "error_cluster_window": 3,
        "error_cluster_factor": 1.8,
        "long_word_threshold": 8,
        "long_word_factor": 1.6,
        "rare_word_factor": 1.5,
        "burst_error_factor": 1.3,
        "lose_place_probability": 0.003,
        "scripted_mistakes": None,  # path to a JSON file, or an inline list of dicts
    },
    "pauses": {
        "idle_rate_per_hour": 1.2,
        "idle_min": 30,
        "idle_max": 180,
    },
    "sessions": {
        "count": 1,
        "schedule": [],  # break lengths in minutes between sessions, e.g. [10, 30]
    },
    "logging": {
        "output": None,  # None -> auto humantype_log_YYYYmmdd_HHMMSS.csv
        "progress_file": ".humantype_progress.json",
        # Auto-save via Ctrl+S is OFF by default: on an unsaved blank Word
        # document, Ctrl+S opens the Save As dialog and keystrokes would go
        # into the filename box.  Enable only when typing into a document
        # that already has a saved file path.
        "save_interval_minutes": 0,
        "dry_run_max_events": 0,  # 0 = no limit
    },
    "hotkeys": {
        "pause": "F8",
        "abort": "F9",
    },
}


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge `override` into a copy of `base`."""
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def to_namespace(d: dict) -> SimpleNamespace:
    """Recursively convert a dict to SimpleNamespace attributes."""
    ns = SimpleNamespace()
    for key, value in d.items():
        if isinstance(value, dict):
            setattr(ns, key, to_namespace(value))
        else:
            setattr(ns, key, value)
    return ns


def load_yaml(path: str) -> dict:
    import yaml

    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data if isinstance(data, dict) else {}


def load_settings(args=None) -> SimpleNamespace:
    """Build settings from defaults, config.yaml, profile and CLI args.

    Precedence (lowest to highest):
        built-in defaults < ./config.yaml < --config file < --profile file
        < explicit CLI flags.
    """
    settings = copy.deepcopy(DEFAULTS)

    for candidate in ("config.yaml", "humantype.yaml"):
        if os.path.exists(candidate):
            settings = deep_merge(settings, load_yaml(candidate))
            break

    if args is not None:
        if getattr(args, "config", None):
            settings = deep_merge(settings, load_yaml(args.config))
        if getattr(args, "profile", None):
            profile = load_yaml(args.profile)
            # A profile only overrides the sections it contains.
            settings = deep_merge(settings, profile)
        settings = apply_cli_overrides(settings, args)

    return to_namespace(settings)


# Map CLI flag names -> (section, key, type).  Used by `humantype type`.
CLI_OVERRIDES = {
    "wpm": ("typing", "wpm", float),
    "countdown": ("typing", "countdown", float),
    "error_rate": ("typing", "error_rate", float),
    "uncorrected_rate": ("typing", "uncorrected_rate", float),
    "backend": ("typing", "backend", str),
    "seed": ("typing", "seed", int),
    "sessions": ("sessions", "count", int),
    "save_interval": ("logging", "save_interval_minutes", float),
    "scripted_mistakes": ("errors", "scripted_mistakes", str),
}


def apply_cli_overrides(settings: dict, args) -> dict:
    """Apply scalar CLI flags on top of a settings dict."""
    for flag, (section, key, cast) in CLI_OVERRIDES.items():
        value = getattr(args, flag, None)
        if value is not None:
            settings[section][key] = cast(value)

    if getattr(args, "keep_originals", None):
        settings["typing"]["keep_originals"] = True
    if getattr(args, "dry_run", None):
        settings["typing"]["dry_run"] = True
    else:
        settings["typing"]["dry_run"] = False
    if getattr(args, "allow_mouse", None):
        settings["typing"]["allow_mouse"] = True

    wa = getattr(args, "word_autocorrect", None)
    if wa is not None:
        settings["typing"]["word_autocorrect"] = wa

    schedule = getattr(args, "schedule", None)
    if schedule:
        settings["sessions"]["schedule"] = _parse_schedule(schedule)

    log = getattr(args, "log", None)
    if log:
        settings["logging"]["output"] = log
    if getattr(args, "no_log", None):
        settings["logging"]["output"] = None
    return settings


def _parse_schedule(text: str) -> list[float]:
    """Parse '10m,2h,90' into minutes (floats)."""
    parts = []
    for chunk in text.split(","):
        chunk = chunk.strip().lower()
        if not chunk:
            continue
        multiplier = 1.0
        if chunk.endswith("h"):
            multiplier = 60.0
            chunk = chunk[:-1]
        elif chunk.endswith("m"):
            chunk = chunk[:-1]
        try:
            parts.append(float(chunk) * multiplier)
        except ValueError:
            raise ValueError(f"invalid schedule entry: {chunk!r}")
    return parts
