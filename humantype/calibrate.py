"""Fit timing/error parameters from a real recording to a profile file.

Pure Python (no numpy), so it works in the slim EXE build as well.
"""

from __future__ import annotations

import math
import statistics

import yaml

from .analyze import compute_metrics, load_log
from .keymaps import COMMON_BIGRAMS


def _mean(values) -> float:
    return statistics.fmean(values) if values else 0.0


def _std(values) -> float:
    return statistics.pstdev(values) if values else 0.0


def calibrate(log_path: str, output: str = "humantype_profile.yaml"):
    rows = load_log(log_path)
    if not rows:
        raise SystemExit(f"no events found in {log_path}")

    keydowns = [r for r in rows if r["event_type"] not in ("keyup", "pause", "para_end")]
    keyups = [r for r in rows if r["event_type"] == "keyup"]

    delays = [r["delay"] for r in keydowns if r["delay"] is not None and 0.005 < r["delay"] < 2.0]
    if len(delays) < 20:
        raise SystemExit("not enough keystrokes to calibrate (need 20+ keydowns)")

    log_delays = [math.log(d) for d in delays]
    mu = _mean(log_delays)
    sigma = _std(log_delays)
    mean_delay = math.exp(mu + sigma ** 2 / 2.0)
    wpm = 12.0 / mean_delay if mean_delay > 0 else 45.0

    # Per-bigram speed multipliers relative to the overall mean.
    bigram_speeds = {}
    pair_delays = {}
    for i in range(1, len(keydowns)):
        prev = keydowns[i - 1]["key"]
        cur = keydowns[i]["key"]
        if len(prev) != 1 or len(cur) != 1:
            continue
        pair = prev.lower() + cur.lower()
        if pair not in COMMON_BIGRAMS:
            continue
        d = keydowns[i]["delay"]
        if d is not None and 0.005 < d < 2.0:
            pair_delays.setdefault(pair, []).append(d)
    for pair, values in pair_delays.items():
        if len(values) >= 5:
            ratio = _mean(values) / mean_delay
            bigram_speeds[pair] = round(min(1.5, max(0.5, ratio)), 3)

    # Pause durations: long gaps after space / comma / sentence enders.
    word_pauses, comma_pauses, sentence_pauses = [], [], []
    for i in range(1, len(keydowns)):
        prev = keydowns[i - 1]
        gap = keydowns[i]["elapsed"] - prev["elapsed"]
        key = prev["key"]
        if key == " " and 0.03 <= gap <= 0.8:
            word_pauses.append(gap)
        elif key in ",;:" and 0.05 <= gap <= 2.0:
            comma_pauses.append(gap)
        elif key in ".!?" and 0.15 <= gap <= 5.0:
            sentence_pauses.append(gap)

    holds = [r["duration"] for r in keyups if r["duration"] and r["duration"] < 0.5]
    hold_mean = _mean(holds) if holds else 0.09
    hold_std = _std(holds) if holds else 0.02

    metrics = compute_metrics(rows)
    backspace_rate = metrics["backspace_rate"]
    rollover_rate = metrics["rollover_rate"]
    burst_mean = metrics["burst_mean"]

    profile = {
        "typing": {
            "wpm": round(wpm, 1),
            "error_rate": round(max(0.005, backspace_rate * 0.7), 4),
        },
        "timing": {
            "lognormal_sigma": round(sigma, 3),
            "hold_min": round(max(0.03, hold_mean - hold_std), 3),
            "hold_max": round(hold_mean + hold_std, 3),
            "common_bigram_speed": bigram_speeds if bigram_speeds else 0.85,
        },
        "errors": {
            "error_cluster_window": 3,
        },
    }
    if word_pauses:
        profile["timing"]["word_pause_mean"] = round(_mean(word_pauses), 3)
    if comma_pauses:
        profile["timing"]["comma_pause_mean"] = round(_mean(comma_pauses), 3)
    if sentence_pauses:
        profile["timing"]["sentence_pause_mean"] = round(_mean(sentence_pauses), 3)

    with open(output, "w", encoding="utf-8") as fh:
        fh.write(f"# humantype profile calibrated from {log_path}\n")
        yaml.safe_dump(profile, fh, sort_keys=False)

    print(f"calibrated profile written to {output}")
    print(f"  wpm              : {wpm:.1f}")
    print(f"  lognormal sigma  : {sigma:.3f}")
    print(f"  hold mean/std    : {hold_mean*1000:.1f}/{hold_std*1000:.1f} ms")
    print(f"  backspace rate   : {backspace_rate*100:.2f}%")
    print(f"  rollover rate    : {rollover_rate*100:.2f}%")
    print(f"  burst mean       : {burst_mean:.2f}")
    print(f"  bigram speeds fit: {len(bigram_speeds)} bigrams")
    return profile
