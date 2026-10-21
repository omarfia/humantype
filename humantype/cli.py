"""Command-line interface for humantype."""

from __future__ import annotations

import argparse
import os
import sys

from . import __version__
from .config import load_settings
from .extract import extract_paragraphs


def _add_common_type_flags(parser: argparse.ArgumentParser):
    parser.add_argument("--wpm", type=float, help="target words per minute (default 45)")
    parser.add_argument("--countdown", type=float, help="countdown seconds before typing starts")
    parser.add_argument("--error-rate", type=float, help="fraction of words with a typo (default 0.03)")
    parser.add_argument("--uncorrected-rate", type=float, help="fraction of typos left uncorrected (default 0)")
    parser.add_argument("--backend", choices=["pynput", "pyautogui"], help="keyboard backend")
    parser.add_argument("--seed", type=int, help="random seed for reproducible runs")
    parser.add_argument("--sessions", type=int, help="split the document into N sessions with breaks")
    parser.add_argument("--schedule", help="break lengths between sessions, e.g. '10m,2h,30'")
    parser.add_argument("--save-interval", type=float,
                        help="auto-save (Ctrl+S) every N minutes; 0 disables (default 0). "
                             "Only use when the target Word document already has a saved path")
    parser.add_argument("--scripted-mistakes", help="path to a JSON file of scripted mistakes "
                        "(disables random errors and uses only the mistakes in the file)")
    parser.add_argument("--word-autocorrect", choices=["on", "off"],
                        help="on = assume Word AutoCorrect is enabled (default)")
    parser.add_argument("--keep-originals", action="store_true",
                        help="keep smart quotes/dashes instead of normalizing them")
    parser.add_argument("--allow-mouse", action="store_true", help="permit mouse use (off by default)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the planned keystroke stream instead of typing")
    parser.add_argument("--max-events", type=int, help="limit printed events in --dry-run")
    parser.add_argument("--resume", action="store_true", help="resume from saved progress")
    parser.add_argument("--config", help="path to a YAML config file")
    parser.add_argument("--profile", help="path to a calibrated profile YAML")
    parser.add_argument("--log", help="path for the event CSV log")
    parser.add_argument("--no-log", action="store_true", help="do not write a CSV log")
    parser.add_argument("--verify-docx", help="compare a saved .docx against the source after typing")
    parser.add_argument("--no-verify", action="store_true", help="skip post-typing verification")
    parser.add_argument("--apply-formatting", action="store_true",
                        help="after typing, apply the source's exact formatting to the active "
                             "Word document (Windows + Word + pywin32)")


def _build_type_parser(subparsers):
    parser = subparsers.add_parser("type", help="type a document into the focused window")
    parser.add_argument("source", help="path to a .pdf, .doc, .docx, or .md file")
    _add_common_type_flags(parser)
    parser.set_defaults(func=cmd_type)


def _build_gui_parser(subparsers):
    parser = subparsers.add_parser("gui", help="open the graphical interface")
    parser.set_defaults(func=cmd_gui)


def _build_record_parser(subparsers):
    parser = subparsers.add_parser("record", help="record your own keystroke timings to a CSV")
    parser.add_argument("--output", "-o", default="humantype_record.csv",
                        help="output CSV path (default humantype_record.csv)")
    parser.add_argument("--stop-key", default="F9", help="key that stops recording (default F9)")
    parser.set_defaults(func=cmd_record)


def _build_analyze_parser(subparsers):
    parser = subparsers.add_parser("analyze", help="analyze one or two humantype logs")
    parser.add_argument("logs", nargs="+", help="one log, or two logs (real then simulated) to compare")
    parser.add_argument("--outdir", default="humantype_charts", help="directory for matplotlib charts")
    parser.set_defaults(func=cmd_analyze)


def _build_calibrate_parser(subparsers):
    parser = subparsers.add_parser("calibrate", help="fit a profile to a recording")
    parser.add_argument("log", help="CSV log from `humantype record`")
    parser.add_argument("--output", "-o", default="humantype_profile.yaml",
                        help="profile output path (default humantype_profile.yaml)")
    parser.set_defaults(func=cmd_calibrate)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="humantype",
        description="Type a document into Microsoft Word with human-like keystrokes.",
    )
    parser.add_argument("--version", action="version", version=f"humantype {__version__}")
    subparsers = parser.add_subparsers(dest="command")
    _build_type_parser(subparsers)
    _build_gui_parser(subparsers)
    _build_record_parser(subparsers)
    _build_analyze_parser(subparsers)
    _build_calibrate_parser(subparsers)
    return parser


def cmd_type(args):
    cfg = load_settings(args)
    if getattr(args, "max_events", None):
        cfg.logging.dry_run_max_events = args.max_events

    paragraphs = extract_paragraphs(args.source, keep_originals=cfg.typing.keep_originals)
    print(f"extracted {len(paragraphs)} paragraphs from {args.source}")

    from .typer import run_typing
    # Only an explicit --verify-docx triggers the post-typing Ctrl+S +
    # comparison, because Ctrl+S on an unsaved blank document would open the
    # Save As dialog and the remaining keystrokes would land in the filename
    # box.
    verify = args.verify_docx
    result = run_typing(cfg, paragraphs, args.source, resume=args.resume,
                        verify_docx=verify, send_final_save=verify is not None)

    if getattr(args, "apply_formatting", False) and not result["aborted"]:
        from . import word_com
        from .formatting import get_formatting_docx
        from .normalize import normalize_text
        print("applying exact source formatting via Word...")
        fmt_docx = get_formatting_docx(args.source)
        word = word_com.get_word(attach=True)
        target = word.ActiveDocument
        word_com.apply_exact_formatting(fmt_docx, target)
        expected = extract_paragraphs(fmt_docx)
        actual_text = normalize_text(word_com.document_text(target))
        actual = [p for p in actual_text.split("\n\n") if p.strip()]
        if actual == expected:
            print("verification: formatting matches the source exactly")
        else:
            print("verification: text differences remain (see below)")
            import difflib
            diff = list(difflib.unified_diff(expected, actual, fromfile="source",
                                             tofile="word", lineterm=""))
            for line in diff[:40]:
                print("  " + line)


def cmd_gui(args):
    from .gui import launch
    launch()


def cmd_record(args):
    from .record import record
    record(args.output, stop_key=args.stop_key)


def cmd_analyze(args):
    from .analyze import analyze_command
    analyze_command(args.logs, outdir=args.outdir)


def cmd_calibrate(args):
    from .calibrate import calibrate
    calibrate(args.log, output=args.output)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()

    # Allow `humantype SOURCE [flags]` as shorthand for `humantype type SOURCE`.
    if argv and argv[0] not in ("type", "gui", "record", "analyze", "calibrate",
                                "--version", "-h", "--help"):
        argv.insert(0, "type")

    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\naborted")
        return 130
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
