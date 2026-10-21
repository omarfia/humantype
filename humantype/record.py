"""Record real keystroke timings into the same CSV format the typer writes."""

from __future__ import annotations

import csv
import datetime as _dt
import time

CSV_FIELDS = ["timestamp", "elapsed", "key", "delay", "event_type", "duration", "detail"]

_SPECIAL = {
    "space": (" ", " "),
    "enter": ("Key.enter", "Key.enter"),
    "tab": ("Key.tab", "Key.tab"),
    "backspace": ("Key.backspace", "Key.backspace"),
    "shift": ("Key.shift", "Key.shift"),
    "shift_r": ("Key.shift", "Key.shift"),
    "ctrl": ("Key.ctrl", "Key.ctrl"),
    "ctrl_r": ("Key.ctrl", "Key.ctrl"),
    "alt": ("Key.alt", "Key.alt"),
    "left": ("Key.left", "Key.left"),
    "right": ("Key.right", "Key.right"),
    "up": ("Key.up", "Key.up"),
    "down": ("Key.down", "Key.down"),
    "home": ("Key.home", "Key.home"),
    "end": ("Key.end", "Key.end"),
    "esc": ("Key.esc", "Key.esc"),
    "f8": ("Key.f8", "Key.f8"),
    "f9": ("Key.f9", "Key.f9"),
}

_SHIFT_SYMBOLS = {
    "1": "!", "2": "@", "3": "#", "4": "$", "5": "%", "6": "^", "7": "&",
    "8": "*", "9": "(", "0": ")", "-": "_", "=": "+", "[": "{", "]": "}",
    "\\": "|", ";": ":", "'": '"', ",": "<", ".": ">", "/": "?", "`": "~",
}


def _normalize_key(key) -> tuple[str, str]:
    """Return (csv_key, base_char_or_key) for a pynput key."""
    try:
        if hasattr(key, "char") and key.char is not None:
            return (key.char, key.char)
    except Exception:
        pass
    name = getattr(key, "name", None)
    if name:
        return _SPECIAL.get(name, (f"Key.{name}", f"Key.{name}"))
    return (str(key), str(key))


def _produced(base: str, shift_down: bool) -> str:
    if len(base) != 1:
        return ""
    if not shift_down:
        return base
    if base.isalpha():
        return base.upper()
    return _SHIFT_SYMBOLS.get(base, base)


def record(output: str, stop_key: str = "F9"):
    """Record keystrokes until the stop key is pressed.  Writes CSV rows."""
    try:
        from pynput import keyboard
    except ImportError as exc:
        raise SystemExit("pynput is required for `humantype record`; pip install pynput") from exc

    start = time.time()
    shift_down = False
    held: dict[str, float] = {}
    last_keydown_elapsed = None
    stop_csv = f"Key.{stop_key.lower()}"

    with open(output, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()

        def on_press(key):
            nonlocal shift_down, last_keydown_elapsed
            csv_key, base = _normalize_key(key)
            elapsed = time.time() - start
            if csv_key == stop_csv:
                return False
            if csv_key in ("Key.shift",):
                shift_down = True
                return
            if csv_key in ("Key.ctrl", "Key.alt"):
                return
            if csv_key in held:  # auto-repeat
                return
            delay = "" if last_keydown_elapsed is None else f"{elapsed - last_keydown_elapsed:.4f}"
            last_keydown_elapsed = elapsed
            event_type = "backspace" if csv_key == "Key.backspace" else "normal"
            writer.writerow({
                "timestamp": _dt.datetime.now().isoformat(timespec="milliseconds"),
                "elapsed": f"{elapsed:.4f}",
                "key": csv_key,
                "delay": delay,
                "event_type": event_type,
                "duration": "",
                "detail": f"char:{_produced(base, shift_down)}",
            })
            held[csv_key] = elapsed
            fh.flush()

        def on_release(key):
            nonlocal shift_down
            csv_key, _ = _normalize_key(key)
            elapsed = time.time() - start
            if csv_key == "Key.shift":
                shift_down = False
                return
            if csv_key in ("Key.ctrl", "Key.alt"):
                return
            down = held.pop(csv_key, None)
            if down is None:
                return
            writer.writerow({
                "timestamp": _dt.datetime.now().isoformat(timespec="milliseconds"),
                "elapsed": f"{elapsed:.4f}",
                "key": csv_key,
                "delay": "",
                "event_type": "keyup",
                "duration": f"{elapsed - down:.4f}",
                "detail": "",
            })
            fh.flush()

        print(f"Recording keystrokes to {output}.  Press {stop_key} to stop.")
        try:
            with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
                listener.join()
        except KeyboardInterrupt:
            pass
    print(f"recording saved to {output}")
