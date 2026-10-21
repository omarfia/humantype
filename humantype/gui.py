"""Tkinter GUI for humantype.

A simple window: pick a source file, pick a target Word document (or just use
the focused window), set the typing parameters, and press Start.  Typing runs
in a background thread; F8/F9 hotkeys and the Pause/Abort buttons both work.

With "Apply exact source formatting" enabled (the default), humantype types
the text like a human first and then uses Word automation to make the final
document an exact formatted copy of the source.
"""

from __future__ import annotations

import contextlib
import io
import os
import queue
import threading
import time
import traceback
from types import SimpleNamespace

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from . import word_com
from .config import load_settings
from .extract import extract_paragraphs
from .formatting import get_formatting_docx
from .typer import RunController, run_typing, run_typing_com, start_hotkey_listener

FILE_TYPES = [
    ("Documents", "*.md *.markdown *.txt *.doc *.docx *.pdf"),
    ("All files", "*.*"),
]


class HumantypeGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("humantype - human-like typing for Word")
        self.root.geometry("860x640")
        self.root.minsize(720, 560)

        self.queue: queue.Queue = queue.Queue()
        self.controller: RunController | None = None
        self.listener = None
        self.running = False
        self.last_log_path = None

        self.source_var = tk.StringVar()
        self.target_var = tk.StringVar(value="Focused window (click it during countdown)")
        self.target_index = None  # 1-based Word Documents index, or None for focused

        self.wpm_var = tk.StringVar(value="45")
        self.countdown_var = tk.StringVar(value="5")
        self.error_var = tk.StringVar(value="0.03")
        self.uncorrected_var = tk.StringVar(value="0.0")
        self.autocorrect_var = tk.StringVar(value="on")
        self.backend_var = tk.StringVar(value="pynput")
        self.seed_var = tk.StringVar(value="")
        self.sessions_var = tk.StringVar(value="1")
        self.schedule_var = tk.StringVar(value="")
        self.format_var = tk.BooleanVar(value=True)
        self.resume_var = tk.BooleanVar(value=False)
        self.auto_save_var = tk.BooleanVar(value=False)
        self.save_minutes_var = tk.StringVar(value="4")
        self.mode_var = tk.StringVar(value="focused")
        self.start_para_var = tk.StringVar(value="1")
        self.end_para_var = tk.StringVar(value="")
        self.scripted_var = tk.StringVar(value="")
        self.format_target_var = tk.StringVar(value="word")

        # Pause/time-range customization.  Populated from the active config.
        self.pause_vars: dict[str, tk.StringVar] = {}
        self._init_pause_vars()

        self.progress_var = tk.DoubleVar(value=0.0)
        self.status_var = tk.StringVar(value="Ready.")

        self._build()
        self.root.after(100, self._poll_queue)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _init_pause_vars(self):
        cfg = load_settings(None)
        t, p = cfg.timing, cfg.pauses
        defaults = {
            "word_pause_mean": t.word_pause_mean, "word_pause_min": t.word_pause_min,
            "word_pause_max": t.word_pause_max,
            "comma_pause_mean": t.comma_pause_mean, "comma_pause_min": t.comma_pause_min,
            "comma_pause_max": t.comma_pause_max,
            "sentence_pause_mean": t.sentence_pause_mean,
            "sentence_pause_min": t.sentence_pause_min, "sentence_pause_max": t.sentence_pause_max,
            "paragraph_pause_mean": t.paragraph_pause_mean,
            "paragraph_pause_min": t.paragraph_pause_min,
            "paragraph_pause_max": t.paragraph_pause_max,
            "chunk_pause_min": t.chunk_pause_min, "chunk_pause_max": t.chunk_pause_max,
            "thinking_pause_min": cfg.typing.thinking_pause_min,
            "thinking_pause_max": cfg.typing.thinking_pause_max,
            "thinking_pause_rate": cfg.typing.thinking_pause_rate,
            "idle_min": p.idle_min, "idle_max": p.idle_max,
            "idle_rate_per_hour": p.idle_rate_per_hour,
            "hold_min": t.hold_min, "hold_max": t.hold_max,
        }
        for key, value in defaults.items():
            self.pause_vars[key] = tk.StringVar(value=str(value))

    # ------------------------------------------------------------------ UI
    def _build(self):
        pad = {"padx": 6, "pady": 4}

        source_frame = ttk.LabelFrame(self.root, text="Source document")
        source_frame.pack(fill="x", **pad)
        ttk.Entry(source_frame, textvariable=self.source_var).pack(
            side="left", fill="x", expand=True, padx=6, pady=6
        )
        ttk.Button(source_frame, text="Browse...", command=self._pick_source).pack(
            side="left", padx=6, pady=6
        )

        target_frame = ttk.LabelFrame(self.root, text="Target Word document")
        target_frame.pack(fill="x", **pad)
        self.target_combo = ttk.Combobox(
            target_frame, textvariable=self.target_var, state="readonly", width=70
        )
        self.target_combo.pack(side="left", fill="x", expand=True, padx=6, pady=6)
        ttk.Button(target_frame, text="Refresh list", command=self._refresh_targets).pack(
            side="left", padx=6, pady=6
        )

        settings_frame = ttk.LabelFrame(self.root, text="Typing settings")
        settings_frame.pack(fill="x", **pad)
        grid = settings_frame.grid_columnconfigure
        for col in (1, 3, 5, 7):
            grid(col, weight=1)

        self._setting(settings_frame, 0, 0, "WPM", self.wpm_var)
        self._setting(settings_frame, 0, 2, "Countdown (s)", self.countdown_var)
        self._setting(settings_frame, 0, 4, "Error rate", self.error_var)
        self._setting(settings_frame, 0, 6, "Uncorrected rate", self.uncorrected_var)

        self._setting(settings_frame, 1, 0, "AutoCorrect", self.autocorrect_var,
                      values=["on", "off"])
        self._setting(settings_frame, 1, 2, "Backend", self.backend_var,
                      values=["pynput", "pyautogui"])
        self._setting(settings_frame, 1, 4, "Seed (blank=random)", self.seed_var)
        self._setting(settings_frame, 1, 6, "Sessions", self.sessions_var)

        ttk.Label(settings_frame, text="Schedule (e.g. 10m,30m)").grid(
            row=2, column=0, sticky="w", **pad)
        ttk.Entry(settings_frame, textvariable=self.schedule_var, width=12).grid(
            row=2, column=1, sticky="w", **pad)

        ttk.Checkbutton(settings_frame, text="Apply exact source formatting after typing",
                        variable=self.format_var).grid(row=2, column=2, columnspan=3, sticky="w")
        ttk.Checkbutton(settings_frame, text="Resume from saved progress",
                        variable=self.resume_var).grid(row=2, column=5, columnspan=2, sticky="w")

        auto_save_row = ttk.Frame(settings_frame)
        auto_save_row.grid(row=3, column=0, columnspan=7, sticky="w", padx=6, pady=2)
        ttk.Checkbutton(auto_save_row, text="Auto-save (Ctrl+S) every",
                        variable=self.auto_save_var).pack(side="left")
        ttk.Entry(auto_save_row, textvariable=self.save_minutes_var, width=5).pack(side="left", padx=4)
        ttk.Label(auto_save_row, text="minutes (only for documents that already have a saved path)").pack(
            side="left")

        range_row = ttk.Frame(settings_frame)
        range_row.grid(row=4, column=0, columnspan=7, sticky="w", padx=6, pady=2)
        ttk.Label(range_row, text="Typing mode:").pack(side="left")
        self.mode_combo = ttk.Combobox(range_row, textvariable=self.mode_var, state="readonly",
                                       width=34, values=[
                                           "focused (real keystrokes into the focused window)",
                                           "background (Word COM - use your computer meanwhile)",
                                       ])
        self.mode_combo.pack(side="left", padx=4)
        ttk.Label(range_row, text="Start at paragraph:").pack(side="left", padx=(12, 2))
        ttk.Entry(range_row, textvariable=self.start_para_var, width=5).pack(side="left")
        ttk.Label(range_row, text="End at (blank = end):").pack(side="left", padx=(8, 2))
        ttk.Entry(range_row, textvariable=self.end_para_var, width=5).pack(side="left")
        ttk.Button(range_row, text="Preview source & pick...", command=self._preview_source).pack(
            side="left", padx=8)
        ttk.Button(range_row, text="Pause/time settings...", command=self._open_pause_dialog).pack(
            side="left", padx=4)

        scripted_row = ttk.Frame(settings_frame)
        scripted_row.grid(row=5, column=0, columnspan=7, sticky="w", padx=6, pady=2)
        ttk.Label(scripted_row, text="Scripted mistakes JSON (optional):").pack(side="left")
        ttk.Entry(scripted_row, textvariable=self.scripted_var, width=52).pack(side="left", padx=4)
        ttk.Button(scripted_row, text="Browse...", command=self._pick_scripted).pack(side="left")

        format_target_row = ttk.Frame(settings_frame)
        format_target_row.grid(row=6, column=0, columnspan=7, sticky="w", padx=6, pady=2)
        ttk.Label(format_target_row, text="Formatting target:").pack(side="left")
        self.format_target_combo = ttk.Combobox(
            format_target_row, textvariable=self.format_target_var, state="readonly", width=36,
            values=["word (exact via Word COM)", "gdocs (Google Docs clipboard paste)"],
        )
        self.format_target_combo.pack(side="left", padx=4)
        ttk.Label(format_target_row,
                  text="(used by 'Apply exact source formatting' - for gdocs, keep the tab focused)").pack(
            side="left")

        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill="x", **pad)
        self.preview_btn = ttk.Button(button_frame, text="Preview plan", command=self._preview)
        self.preview_btn.pack(side="left", padx=4)
        self.start_btn = ttk.Button(button_frame, text="Start typing", command=self._start)
        self.start_btn.pack(side="left", padx=4)
        self.pause_btn = ttk.Button(button_frame, text="Pause / Resume", command=self._toggle_pause,
                                    state="disabled")
        self.pause_btn.pack(side="left", padx=4)
        self.abort_btn = ttk.Button(button_frame, text="Abort", command=self._abort,
                                    state="disabled")
        self.abort_btn.pack(side="left", padx=4)
        self.analyze_btn = ttk.Button(button_frame, text="Analyze log...", command=self._analyze)
        self.analyze_btn.pack(side="left", padx=4)

        progress_frame = ttk.Frame(self.root)
        progress_frame.pack(fill="x", **pad)
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=1.0)
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=6)
        ttk.Label(progress_frame, textvariable=self.status_var, width=52).pack(side="right", padx=6)

        self.output = scrolledtext.ScrolledText(self.root, height=16, state="disabled",
                                                font=("Consolas", 9))
        self.output.pack(fill="both", expand=True, **pad)

        self._refresh_targets()
        self._log("Ready. Pick a source file, choose a target Word document, and press Start.")

    def _setting(self, parent, row, col, label, var, values=None):
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", padx=6, pady=2)
        if values:
            widget = ttk.Combobox(parent, textvariable=var, values=values, state="readonly",
                                  width=10)
        else:
            widget = ttk.Entry(parent, textvariable=var, width=10)
        widget.grid(row=row, column=col + 1, sticky="w", padx=6, pady=2)

    # ------------------------------------------------------------- actions
    def _pick_source(self):
        path = filedialog.askopenfilename(title="Choose source document", filetypes=FILE_TYPES)
        if path:
            self.source_var.set(path)

    def _pick_scripted(self):
        path = filedialog.askopenfilename(
            title="Choose scripted mistakes JSON", filetypes=[("JSON", "*.json"), ("All files", "*.*")]
        )
        if path:
            self.scripted_var.set(path)

    def _preview_source(self):
        """Open a scrollable paragraph list; the user picks start/end spots."""
        source = self.source_var.get().strip()
        if not source or not os.path.exists(source):
            messagebox.showwarning("humantype", "Choose an existing source file first.")
            return
        try:
            cfg = self._build_config(dry_run=True)
            paragraphs = extract_paragraphs(source, keep_originals=cfg.typing.keep_originals)
        except Exception as exc:
            messagebox.showerror("humantype", f"could not read source: {exc}")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Preview: {os.path.basename(source)} ({len(paragraphs)} paragraphs)")
        dialog.geometry("720x520")
        ttk.Label(dialog, text="Select a paragraph, then choose what it should mark.").pack(
            anchor="w", padx=8, pady=4)
        listbox = tk.Listbox(dialog, font=("Consolas", 9), activestyle="dotbox")
        listbox.pack(fill="both", expand=True, padx=8, pady=4)
        for i, para in enumerate(paragraphs, 1):
            preview = para if len(para) <= 90 else para[:87] + "..."
            listbox.insert("end", f"{i:>4}: {preview}")

        def set_start():
            sel = listbox.curselection()
            if sel:
                self.start_para_var.set(str(sel[0] + 1))

        def set_end():
            sel = listbox.curselection()
            if sel:
                self.end_para_var.set(str(sel[0] + 1))

        def clear_range():
            self.start_para_var.set("1")
            self.end_para_var.set("")

        buttons = ttk.Frame(dialog)
        buttons.pack(fill="x", padx=8, pady=6)
        ttk.Button(buttons, text="Set as start", command=set_start).pack(side="left", padx=4)
        ttk.Button(buttons, text="Set as end", command=set_end).pack(side="left", padx=4)
        ttk.Button(buttons, text="Clear (whole document)", command=clear_range).pack(side="left", padx=4)
        ttk.Button(buttons, text="Close", command=dialog.destroy).pack(side="right", padx=4)

    def _open_pause_dialog(self):
        """Dialog to customize every pause/time range used by the typer."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Pause and timing customization")
        dialog.geometry("640x560")

        rows = [
            ("Word pause mean (s)", "word_pause_mean"),
            ("Word pause min (s)", "word_pause_min"),
            ("Word pause max (s)", "word_pause_max"),
            ("Comma pause mean (s)", "comma_pause_mean"),
            ("Comma pause min (s)", "comma_pause_min"),
            ("Comma pause max (s)", "comma_pause_max"),
            ("Sentence pause mean (s)", "sentence_pause_mean"),
            ("Sentence pause min (s)", "sentence_pause_min"),
            ("Sentence pause max (s)", "sentence_pause_max"),
            ("Paragraph pause mean (s)", "paragraph_pause_mean"),
            ("Paragraph pause min (s)", "paragraph_pause_min"),
            ("Paragraph pause max (s)", "paragraph_pause_max"),
            ("Chunk pause min (s)", "chunk_pause_min"),
            ("Chunk pause max (s)", "chunk_pause_max"),
            ("Thinking pause min (s)", "thinking_pause_min"),
            ("Thinking pause max (s)", "thinking_pause_max"),
            ("Thinking pause rate (per char)", "thinking_pause_rate"),
            ("Idle gap min (s)", "idle_min"),
            ("Idle gap max (s)", "idle_max"),
            ("Idle gaps per hour", "idle_rate_per_hour"),
            ("Key hold min (s)", "hold_min"),
            ("Key hold max (s)", "hold_max"),
        ]
        grid = ttk.Frame(dialog)
        grid.pack(fill="both", expand=True, padx=10, pady=10)
        for r, (label, key) in enumerate(rows):
            ttk.Label(grid, text=label).grid(row=r // 2, column=(r % 2) * 2, sticky="w", padx=6, pady=2)
            ttk.Entry(grid, textvariable=self.pause_vars[key], width=10).grid(
                row=r // 2, column=(r % 2) * 2 + 1, sticky="w", padx=6, pady=2)

        ttk.Button(dialog, text="Done (applies to the next run)", command=dialog.destroy).pack(pady=8)

    def _refresh_targets(self):
        self.target_combo["values"] = ()
        entries = ["Focused window (click it during countdown)"]
        self._doc_entries = []
        try:
            if word_com.available():
                for index, name, path in word_com.list_open_documents():
                    label = f"Word doc {index}: {name}"
                    if path:
                        label += f"  ({path})"
                    entries.append(label)
                    self._doc_entries.append((label, index))
        except Exception as exc:
            entries.append(f"(could not read Word: {exc})")
        self.target_combo["values"] = entries
        if self.target_var.get() not in entries:
            self.target_var.set(entries[0])
            self.target_index = None

    def _selected_target_index(self):
        for label, index in self._doc_entries:
            if label == self.target_var.get():
                return index
        return None

    def _build_config(self, dry_run=False):
        args = SimpleNamespace(
            config=None, profile=None,
            wpm=self._float_or_none(self.wpm_var),
            countdown=self._float_or_none(self.countdown_var),
            error_rate=self._float_or_none(self.error_var),
            uncorrected_rate=self._float_or_none(self.uncorrected_var),
            backend=self.backend_var.get(),
            seed=self._int_or_none(self.seed_var),
            sessions=self._int_or_none(self.sessions_var) or 1,
            schedule=self.schedule_var.get() or None,
            word_autocorrect=self.autocorrect_var.get(),
            keep_originals=False,
            dry_run=dry_run,
            allow_mouse=False,
            log=None,
            no_log=False,
            verify_docx=None,
            no_verify=True,
            scripted_mistakes=self.scripted_var.get() or None,
        )
        cfg = load_settings(args)
        if self.auto_save_var.get():
            try:
                cfg.logging.save_interval_minutes = max(0.0, float(self.save_minutes_var.get() or "4"))
            except ValueError:
                cfg.logging.save_interval_minutes = 4.0
        else:
            cfg.logging.save_interval_minutes = 0
        self._apply_pause_overrides(cfg)
        return cfg

    def _apply_pause_overrides(self, cfg):
        """Copy the pause-dialog values onto the config namespace."""
        def f(key):
            try:
                return float(self.pause_vars[key].get())
            except (ValueError, tk.TclError):
                return None

        t, p = cfg.timing, cfg.pauses
        mapping = {
            "word_pause_mean": t, "word_pause_min": t, "word_pause_max": t,
            "comma_pause_mean": t, "comma_pause_min": t, "comma_pause_max": t,
            "sentence_pause_mean": t, "sentence_pause_min": t, "sentence_pause_max": t,
            "paragraph_pause_mean": t, "paragraph_pause_min": t, "paragraph_pause_max": t,
            "chunk_pause_min": t, "chunk_pause_max": t,
            "hold_min": t, "hold_max": t,
        }
        for key, namespace in mapping.items():
            value = f(key)
            if value is not None:
                setattr(namespace, key, value)
        for key in ("thinking_pause_min", "thinking_pause_max", "thinking_pause_rate"):
            value = f(key)
            if value is not None:
                setattr(cfg.typing, key, value)
        for key in ("idle_min", "idle_max", "idle_rate_per_hour"):
            value = f(key)
            if value is not None:
                setattr(p, key, value)

    @staticmethod
    def _float_or_none(var):
        text = var.get().strip()
        if not text:
            return None
        return float(text)

    @staticmethod
    def _int_or_none(var):
        text = var.get().strip()
        if not text:
            return None
        return int(text)

    def _set_running(self, running: bool):
        self.running = running
        state = "disabled" if running else "normal"
        self.start_btn.config(state=state)
        self.preview_btn.config(state=state)
        self.analyze_btn.config(state=state)
        self.pause_btn.config(state="normal" if running else "disabled")
        self.abort_btn.config(state="normal" if running else "disabled")

    def _preview(self):
        source = self.source_var.get().strip()
        if not source:
            messagebox.showwarning("humantype", "Choose a source file first.")
            return
        cfg = self._build_config(dry_run=True)
        self._set_running(True)
        threading.Thread(target=self._preview_worker, args=(cfg, source), daemon=True).start()

    def _selected_paragraphs(self, cfg, source):
        """Apply the start/end paragraph fields; return (sliced, offset, full)."""
        paragraphs = extract_paragraphs(source, keep_originals=cfg.typing.keep_originals)
        full = len(paragraphs)
        start_text = self.start_para_var.get().strip()
        end_text = self.end_para_var.get().strip()
        try:
            start = int(start_text or 1)
        except ValueError:
            start = 1
        try:
            end = int(end_text) if end_text else full
        except ValueError:
            end = full
        start = max(1, min(start, full))
        end = max(start, min(end, full))
        return paragraphs[start - 1:end], start - 1, full

    def _preview_worker(self, cfg, source):
        try:
            paragraphs, offset, full = self._selected_paragraphs(cfg, source)
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                run_typing(cfg, paragraphs, source, progress_offset=offset)
            self.queue.put(("output", buffer.getvalue()))
        except Exception:
            self.queue.put(("error", traceback.format_exc()))
        finally:
            self.queue.put(("idle", None))

    def _start(self):
        source = self.source_var.get().strip()
        if not source or not os.path.exists(source):
            messagebox.showwarning("humantype", "Choose an existing source file first.")
            return
        self._set_running(True)
        self.progress_var.set(0.0)
        self.controller = RunController()
        self.listener = None
        threading.Thread(target=self._start_worker, args=(source,), daemon=True).start()

    def _start_worker(self, source):
        try:
            cfg = self._build_config(dry_run=False)
            self.queue.put(("status", f"extracting text from {os.path.basename(source)}..."))
            paragraphs, offset, full_count = self._selected_paragraphs(cfg, source)
            if offset or len(paragraphs) < full_count:
                self.queue.put(("status",
                                f"typing paragraphs {offset + 1}-{offset + len(paragraphs)} of {full_count}"))
            else:
                self.queue.put(("status", f"extracted {len(paragraphs)} paragraphs"))

            mode = "com" if self.mode_var.get().startswith("background") else "focused"
            target_index = self._selected_target_index()
            word = None
            target_doc = None

            if mode == "com":
                if not word_com.available():
                    raise Exception("background mode needs pywin32 (pip install pywin32)")
                word = word_com.get_word(attach=True)
                target_doc = (word.Documents(target_index) if target_index is not None
                              else word.ActiveDocument)
                self.queue.put(("status", "background mode: typing via Word COM - you can keep working"))
            else:
                # Focused keystroke mode: bring the chosen Word doc to the front.
                if word_com.available():
                    try:
                        word = word_com.get_word(attach=True)
                        if target_index is not None:
                            word_com.activate_document(word, target_index)
                            self.queue.put(("status", "activated the chosen Word document"))
                        # Never auto-save into an unsaved document: Ctrl+S would
                        # open the Save As dialog and keystrokes would land in
                        # the filename box.
                        try:
                            target_doc = (word.Documents(target_index) if target_index is not None
                                          else word.ActiveDocument)
                            if not (target_doc.Path or ""):
                                cfg.logging.save_interval_minutes = 0
                                self.queue.put(("status",
                                                "auto-save disabled: target document has no saved path yet"))
                        except Exception:
                            pass
                    except Exception as exc:
                        self.queue.put(("status", f"could not activate Word doc: {exc}"))

                # Hotkeys work alongside the GUI buttons (focused mode only).
                try:
                    self.listener = start_hotkey_listener(cfg, self.controller)
                except Exception:
                    self.listener = None

            progress_cb = lambda done, total: self.queue.put(("progress", (done + 1, total)))
            status_cb = lambda msg: self.queue.put(("status", msg))

            if mode == "com":
                result = run_typing_com(
                    cfg, paragraphs, source, target_doc,
                    resume=self.resume_var.get(),
                    controller=self.controller,
                    progress_cb=progress_cb, status_cb=status_cb,
                    progress_offset=offset,
                )
            else:
                result = run_typing(
                    cfg, paragraphs, source,
                    resume=self.resume_var.get(),
                    controller=self.controller,
                    progress_cb=progress_cb, status_cb=status_cb,
                    progress_offset=offset,
                )
            self.last_log_path = result.get("log_path")

            if not result["aborted"] and self.format_var.get():
                if self.format_target_var.get().startswith("gdocs"):
                    if mode == "com":
                        self.queue.put(("status", "formatting skipped: gdocs target needs focused mode"))
                    else:
                        try:
                            from .gdocs_format import apply_gdocs_formatting
                            apply_gdocs_formatting(
                                source,
                                status_cb=lambda msg: self.queue.put(("status", msg)),
                            )
                        except Exception as exc:
                            self.queue.put(("status", f"Google Docs formatting failed: {exc}"))
                elif word_com.available():
                    self.queue.put(("status", "applying exact source formatting..."))
                    self._apply_formatting(source, word, target_index)
                    self.queue.put(("status", "exact formatting applied"))
                else:
                    self.queue.put(("status", "formatting skipped: pywin32 not installed"))

            self.queue.put(("status", "done."))
        except Exception:
            self.queue.put(("error", traceback.format_exc()))
        finally:
            if self.listener:
                try:
                    self.listener.stop()
                except Exception:
                    pass
            self.queue.put(("idle", None))

    def _apply_formatting(self, source, word, target_index):
        fmt_docx = get_formatting_docx(source)
        if word is None:
            word = word_com.get_word(attach=True)
        if target_index is not None:
            target_doc = word.Documents(target_index)
        else:
            target_doc = word.ActiveDocument
        word_com.apply_exact_formatting(fmt_docx, target_doc)

        # Verify the final document text against the formatting source.
        expected = extract_paragraphs(fmt_docx)
        from .normalize import normalize_text
        actual_text = normalize_text(word_com.document_text(target_doc))
        actual = [p for p in actual_text.split("\n\n") if p.strip()]
        if actual == expected:
            self.queue.put(("status", "verification: formatting matches the source exactly"))
        else:
            self.queue.put(("status", "verification: some text differences remain"))
            import difflib
            diff = list(difflib.unified_diff(expected, actual, fromfile="source",
                                             tofile="word", lineterm=""))
            for line in diff[:20]:
                self.queue.put(("output", line))

    def _toggle_pause(self):
        if self.controller is not None:
            self.controller.paused = not self.controller.paused
            self.controller._pause_notified = False

    def _abort(self):
        if self.controller is not None:
            self.controller.aborted = True

    def _analyze(self):
        path = filedialog.askopenfilename(
            title="Choose a humantype log CSV", filetypes=[("CSV", "*.csv"), ("All files", "*.*")]
        )
        if not path:
            return
        threading.Thread(target=self._analyze_worker, args=(path,), daemon=True).start()

    def _analyze_worker(self, path):
        try:
            from .analyze import analyze_command
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                analyze_command([path], outdir="humantype_charts")
            self.queue.put(("output", buffer.getvalue()))
        except Exception:
            self.queue.put(("error", traceback.format_exc()))

    # ------------------------------------------------------------- queue
    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "status":
                    self.status_var.set(payload)
                    self._log(payload)
                elif kind == "progress":
                    done, total = payload
                    self.progress_var.set(done / total if total else 0.0)
                    self.status_var.set(f"paragraph {done} of {total}")
                elif kind == "output":
                    self._log(payload)
                elif kind == "error":
                    self._log("ERROR:\n" + payload)
                    messagebox.showerror("humantype", payload[-1500:])
                elif kind == "idle":
                    self._set_running(False)
                    self.pause_btn.config(state="disabled")
                    self.abort_btn.config(state="disabled")
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    def _log(self, text: str):
        self.output.config(state="normal")
        self.output.insert("end", str(text).rstrip() + "\n")
        self.output.see("end")
        self.output.config(state="disabled")

    def _on_close(self):
        if self.controller is not None:
            self.controller.aborted = True
        self.root.destroy()


def launch():
    root = tk.Tk()
    HumantypeGUI(root)
    root.mainloop()
