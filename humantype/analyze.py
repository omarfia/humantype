"""Analyze humantype logs (simulated or recorded) and compare them.

This module is pure Python (no numpy), so it works in the slim EXE build.
Matplotlib is optional and only used for charts when it is installed.
"""

from __future__ import annotations

import csv
import math
import os
import statistics

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MPL = True
except Exception:  # pragma: no cover
    HAS_MPL = False

CSV_FIELDS = ["timestamp", "elapsed", "key", "delay", "event_type", "duration", "detail"]


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def _std(values: list[float]) -> float:
    return statistics.pstdev(values) if values else 0.0


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * (q / 100.0)
    lo = math.floor(k)
    hi = math.ceil(k)
    if lo == hi:
        return s[int(k)]
    return s[int(lo)] * (hi - k) + s[int(hi)] * (k - lo)


def _ks_score(a: list[float], b: list[float]) -> float:
    """1 - Kolmogorov-Smirnov distance between two samples."""
    if not a or not b:
        return float("nan")
    a = sorted(a)
    b = sorted(b)
    combined = sorted(set(a) | set(b))
    n, m = len(a), len(b)
    ia = ib = 0
    dmax = 0.0
    for x in combined:
        while ia < n and a[ia] <= x:
            ia += 1
        while ib < m and b[ib] <= x:
            ib += 1
        dmax = max(dmax, abs(ia / n - ib / m))
    return 1.0 - dmax


def load_log(path: str) -> list[dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            elapsed = float(row.get("elapsed") or 0.0)
            delay = row.get("delay") or ""
            duration = row.get("duration") or ""
            rows.append({
                "elapsed": elapsed,
                "key": row.get("key", ""),
                "delay": float(delay) if delay not in ("", None) else None,
                "event_type": row.get("event_type", ""),
                "duration": float(duration) if duration not in ("", None) else None,
                "detail": row.get("detail", ""),
            })
    rows.sort(key=lambda r: r["elapsed"])
    return rows


def compute_metrics(rows: list[dict]) -> dict:
    keydowns = [r for r in rows if r["event_type"] not in ("keyup", "pause", "para_end")]
    keyups = [r for r in rows if r["event_type"] == "keyup"]
    pauses = [r for r in rows if r["event_type"] == "pause"]

    char_keydowns = [r for r in keydowns if len(r["key"]) == 1]
    backspaces = [r for r in keydowns if r["key"] == "Key.backspace"]
    typos = [r for r in keydowns if r["event_type"] == "typo"]

    duration = (rows[-1]["elapsed"] - rows[0]["elapsed"]) if rows else 0.0
    total_keys = len(keydowns)
    chars = len(char_keydowns)
    minutes = duration / 60.0 if duration > 0 else 0.0
    wpm_overall = (chars / 5.0) / minutes if minutes > 0 else 0.0

    delays = [r["delay"] for r in keydowns if r["delay"] is not None and r["delay"] > 0.001]
    delays = [d for d in delays if d < 5.0]

    # Pause durations: explicit pause rows plus long gaps between keydowns.
    pause_durations = [r["duration"] for r in pauses if r["duration"]]
    for i in range(1, len(keydowns)):
        gap = keydowns[i]["elapsed"] - keydowns[i - 1]["elapsed"]
        if gap >= 1.5:
            pause_durations.append(gap)
    pause_durations = [p for p in pause_durations if 0 < p < 3600]

    holds = [r["duration"] for r in keyups if r["duration"] and r["duration"] < 1.0]

    # Rollover: keydown starts while another non-modifier key is still held.
    held = set()
    rollovers = 0
    for r in rows:
        key = r["key"]
        if r["event_type"] == "keyup":
            held.discard(key)
        elif r["event_type"] not in ("pause", "para_end"):
            if key not in ("Key.shift", "Key.ctrl", "Key.alt"):
                if held and key not in held:
                    rollovers += 1
                held.add(key)
    rollover_rate = rollovers / total_keys if total_keys else 0.0

    # Burst lengths: consecutive keydowns with inter-key delay < 0.5 s.
    bursts = []
    current = 0
    for r in keydowns:
        if r["delay"] is not None and r["delay"] < 0.5:
            current += 1
        else:
            if current > 0:
                bursts.append(current)
            current = 1 if r["delay"] is not None else 0
    if current > 0:
        bursts.append(current)
    burst_mean = _mean(bursts)
    burst_max = float(max(bursts)) if bursts else 0

    # Correction latency: typo keydown -> next backspace keydown.
    latencies = []
    for typo in typos:
        for bs in backspaces:
            if bs["elapsed"] > typo["elapsed"]:
                lat = bs["elapsed"] - typo["elapsed"]
                if lat < 30.0:
                    latencies.append(lat)
                break

    # WPM over time: 30 s windows, 15 s step.
    times = []
    wpms = []
    if char_keydowns:
        t0 = char_keydowns[0]["elapsed"]
        t1 = char_keydowns[-1]["elapsed"]
        window = 30.0
        step = 15.0
        t = t0
        while t <= t1:
            in_window = [r for r in char_keydowns if t <= r["elapsed"] < t + window]
            times.append(t - t0)
            wpms.append(len(in_window) / 5.0 * (60.0 / window))
            t += step

    metrics = {
        "duration": duration,
        "total_keydowns": total_keys,
        "char_keydowns": chars,
        "wpm_overall": wpm_overall,
        "backspace_rate": len(backspaces) / total_keys if total_keys else 0.0,
        "typo_rate": len(typos) / chars if chars else 0.0,
        "delays": delays,
        "delay_mean": _mean(delays),
        "delay_std": _std(delays),
        "delay_p50": _percentile(delays, 50),
        "delay_p95": _percentile(delays, 95),
        "pause_durations": pause_durations,
        "pause_mean": _mean(pause_durations),
        "pause_p50": _percentile(pause_durations, 50),
        "pause_p95": _percentile(pause_durations, 95),
        "hold_mean": _mean(holds),
        "hold_std": _std(holds),
        "holds": holds,
        "rollover_rate": rollover_rate,
        "burst_mean": burst_mean,
        "burst_max": burst_max,
        "correction_latencies": latencies,
        "correction_latency_mean": _mean(latencies),
        "wpm_times": times,
        "wpm_values": wpms,
    }
    return metrics


def _rel_score(x: float, y: float) -> float:
    denom = max(abs(x), abs(y), 1e-9)
    return max(0.0, 1.0 - abs(x - y) / denom)


def compare_metrics(real: dict, sim: dict) -> dict:
    """Per-feature similarity scores between a real and a simulated log."""
    scores = {}
    scores["inter-key delay dist"] = _ks_score(real["delays"], sim["delays"])
    scores["pause dist"] = _ks_score(real["pause_durations"], sim["pause_durations"])
    scores["hold time dist"] = _ks_score(real["holds"], sim["holds"])
    scores["wpm"] = _rel_score(real["wpm_overall"], sim["wpm_overall"])
    scores["backspace rate"] = _rel_score(real["backspace_rate"], sim["backspace_rate"])
    scores["rollover rate"] = _rel_score(real["rollover_rate"], sim["rollover_rate"])
    scores["burst length"] = _rel_score(real["burst_mean"], sim["burst_mean"])
    scores["correction latency"] = _rel_score(
        real["correction_latency_mean"], sim["correction_latency_mean"]
    )
    valid = {k: v for k, v in scores.items() if not math.isnan(v)}
    scores["overall"] = _mean(list(valid.values())) if valid else float("nan")
    return scores


def print_report(name: str, m: dict):
    print(f"\n=== {name} ===")
    print(f"  duration            : {m['duration']/60:8.2f} min")
    print(f"  characters typed    : {m['char_keydowns']}")
    print(f"  WPM (overall)       : {m['wpm_overall']:8.1f}")
    print(f"  inter-key delay     : mean {m['delay_mean']*1000:7.1f} ms  "
          f"p50 {m['delay_p50']*1000:7.1f} ms  p95 {m['delay_p95']*1000:7.1f} ms")
    print(f"  pause duration      : mean {m['pause_mean']:7.2f} s  "
          f"p50 {m['pause_p50']:7.2f} s  p95 {m['pause_p95']:7.2f} s")
    print(f"  key hold time       : mean {m['hold_mean']*1000:7.1f} ms  std {m['hold_std']*1000:7.1f} ms")
    print(f"  backspace rate      : {m['backspace_rate']*100:6.2f}%")
    print(f"  typo rate           : {m['typo_rate']*100:6.2f}%")
    print(f"  rollover rate       : {m['rollover_rate']*100:6.2f}%")
    print(f"  burst length        : mean {m['burst_mean']:6.2f} keys  max {m['burst_max']}")
    print(f"  correction latency  : mean {m['correction_latency_mean']:7.2f} s "
          f"({len(m['correction_latencies'])} corrections)")


def make_charts(logs: dict[str, dict], outdir: str):
    if not HAS_MPL:
        print("matplotlib not available; skipping charts")
        return
    os.makedirs(outdir, exist_ok=True)

    for name, m in logs.items():
        if m["wpm_times"]:
            plt.figure(figsize=(8, 3))
            plt.plot(m["wpm_times"], m["wpm_values"])
            plt.title(f"{name}: WPM over time")
            plt.xlabel("seconds")
            plt.ylabel("WPM")
            plt.tight_layout()
            plt.savefig(os.path.join(outdir, f"{name}_wpm.png"), dpi=110)
            plt.close()

        if m["delays"]:
            plt.figure(figsize=(8, 3))
            plt.hist([d * 1000 for d in m["delays"]], bins=60, alpha=0.7)
            plt.title(f"{name}: inter-key delay distribution")
            plt.xlabel("delay (ms)")
            plt.ylabel("count")
            plt.tight_layout()
            plt.savefig(os.path.join(outdir, f"{name}_delay_hist.png"), dpi=110)
            plt.close()

        if m["pause_durations"]:
            clipped = [min(120.0, max(0.0, p)) for p in m["pause_durations"]]
            plt.figure(figsize=(8, 3))
            plt.hist(clipped, bins=50, alpha=0.7)
            plt.title(f"{name}: pause duration histogram")
            plt.xlabel("pause (s)")
            plt.ylabel("count")
            plt.tight_layout()
            plt.savefig(os.path.join(outdir, f"{name}_pause_hist.png"), dpi=110)
            plt.close()

    names = list(logs.keys())
    if len(names) == 2 and logs[names[0]]["delays"] and logs[names[1]]["delays"]:
        plt.figure(figsize=(8, 3))
        for name in names:
            plt.hist([d * 1000 for d in logs[name]["delays"]], bins=60, alpha=0.5, label=name)
        plt.title("inter-key delay: real vs simulated")
        plt.xlabel("delay (ms)")
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(outdir, "compare_delays.png"), dpi=110)
        plt.close()

    print(f"charts saved to {outdir}")


def analyze_command(log_paths: list[str], outdir: str = "humantype_charts"):
    logs = {}
    for path in log_paths:
        rows = load_log(path)
        if not rows:
            print(f"warning: {path} is empty")
            continue
        name = os.path.splitext(os.path.basename(path))[0]
        metrics = compute_metrics(rows)
        logs[name] = metrics
        print_report(name, metrics)

    if len(logs) == 2:
        (real_name, real), (sim_name, sim) = list(logs.items())
        scores = compare_metrics(real, sim)
        print(f"\n=== similarity: {real_name} (real) vs {sim_name} (simulated) ===")
        for feature, score in scores.items():
            if feature != "overall":
                print(f"  {feature:<22} {score:5.2f}")
        print(f"  {'overall':<22} {scores['overall']:5.2f}")

    make_charts(logs, outdir)
