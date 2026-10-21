# humantype

**humantype types a document into Microsoft Word like a real person.**

Give it a file (`.md`, `.docx`, `.doc`, `.pdf`, or `.txt`), point it at a blank
Word document, and it types the text out for you — with human pacing, natural
pauses, occasional typos that get backspaced and fixed, and even speed drift
like someone warming up and getting tired. It never pastes; every character is
typed one key at a time.

It's a desktop app with a simple window. No command line required.

---

## 1. Easy setup (Windows)

### Option A — just download the app (recommended)

1. Download **`humantype.exe`** (from the GitHub **Releases** page, or from the
   `dist` folder if a friend sent it to you).
2. Double-click it.
3. Windows SmartScreen may show *"Windows protected your PC"*. Click
   **More info → Run anyway**. This warning appears because the app is new and
   not signed with an expensive code-signing certificate — it is expected.
4. That's it. The window opens.

> The EXE is a single self-contained file. You do **not** need to install
> Python, Word plugins, or anything else. Microsoft Word must be installed.

### Option B — run from source (for tech-savvy users)

```bash
git clone https://github.com/<your-name>/humantype.git
cd humantype
python -m venv .venv
.venv\Scripts\activate          # PowerShell / Git Bash on Windows
pip install -r requirements.txt
python -m humantype gui
```

Requires Python 3.10+.

---

## 2. First run, step by step

1. **Open Microsoft Word** and start a **blank document**. Click once inside it
   so the cursor is at the top.
2. **Double-click `humantype.exe`**.
3. In the **Source document** box, click **Browse...** and choose the file you
   want typed (Markdown, Word, or PDF).
4. Leave **Target Word document** as *"Focused window"* for your first run.
5. Set the options you care about (everything is explained below) — the
   defaults are fine to start with.
6. Click **Start typing**.
7. The app counts down, then **click into the Word window** during the
   countdown. The typing begins automatically.
8. Sit back and watch. While it runs:
   - `F8` = pause / resume
   - `F9` = abort (your progress is saved automatically)

If you abort or close the app, progress is saved to a small file
(`.humantype_progress.json`). Tick **Resume from saved progress** next time to
continue from the last finished paragraph.

---

## 3. Every setting, toggle, and mode explained

### Typing settings

| Setting | What it does |
|---|---|
| **WPM** | How fast the typing is, in words per minute. Default `45` is a relaxed pace; `60` is brisk; `30` is slow. |
| **Countdown (s)** | Seconds before typing starts, so you have time to click into Word. |
| **Error rate** | The fraction of words that get a typo (then fixed). Default `0.03` = about 3% of words. Set `0` for no typos. |
| **Uncorrected rate** | The fraction of typos that are *left in* instead of being fixed. Default `0` = every typo is corrected, so the final text matches the source exactly. |
| **Word AutoCorrect** | `on` (default) assumes Word's AutoCorrect is enabled, so humantype avoids typos Word would silently fix itself (like `teh`). Choose `off` if you've turned Word AutoCorrect off and want those typos to actually appear and be backspaced. |
| **Backend** | `pynput` (default, recommended) or `pyautogui` (fallback with a mouse-corner failsafe). |
| **Seed** | Leave blank for a different random run every time; type a number to make a run exactly repeatable. |
| **Sessions** | Split the document into that many sessions with breaks in between (see Schedule). `1` = one continuous run. |
| **Schedule** | Break lengths between sessions, e.g. `10m,30m` = first break 10 minutes, next 30 minutes. Only matters when Sessions > 1. |
| **Auto-save (Ctrl+S) every N minutes** | **Off by default.** Ticking it makes humantype press Ctrl+S periodically. Only use it when the Word document already has a saved file path — on an unsaved blank document, Ctrl+S opens the Save As dialog and the typing would land in the filename box. The app disables it automatically when it can see the document is unsaved. |

### Range and mode controls

| Control | What it does |
|---|---|
| **Typing mode** | See *Modes explained* below. `focused` = real keystrokes into the focused window (default). `background` = types into the chosen Word document via Word automation while you keep using your computer. |
| **Start at paragraph / End at paragraph** | Type only part of the source. `1` and blank = the whole document. |
| **Preview source & pick...** | Opens a scrollable list of every paragraph in the source. Click a paragraph, then **Set as start** or **Set as end** (or **Clear** for the whole document). |
| **Pause/time settings...** | Opens a dialog where you can customize every pause range: word pauses, comma pauses, sentence pauses, paragraph pauses, chunk (look-back) pauses, thinking pauses, idle gaps (phone-check breaks), and key hold times. |
| **Scripted mistakes JSON (optional)** | Instead of random typos, load a JSON file that lists exactly which mistakes happen, where, and how they're noticed. While loaded, random errors are disabled — only your scripted mistakes occur. |
| **Formatting target** | Chooses where the *"Apply exact source formatting"* pass runs: **Word** (exact via Word COM) or **Google Docs** (clipboard paste — see below). |

### Checkboxes

| Toggle | What it does |
|---|---|
| **Apply exact source formatting after typing** | On by default. After the human-like typing finishes, the app uses Word automation to make the final document an exact formatted copy of the source (fonts, bold/italic, colors, headings, lists, tables, images). The typing is real keystrokes; the formatting pass is instant. Turn it off if you only want plain text typed. |
| **Resume from saved progress** | Continue from the last completed paragraph instead of starting over. |

### Buttons

| Button | What it does |
|---|---|
| **Preview plan** | Shows the planned keystroke stream with timings in the output box — types nothing. Good for checking a run before committing. |
| **Start typing** | Begins the run (with the countdown). |
| **Pause / Resume** | Pauses or resumes the current run. Same as `F8`. |
| **Abort** | Stops the current run and saves progress. Same as `F9`. |
| **Analyze log...** | Pick a CSV log from a run and get a report: WPM over time, delay distribution, pause histogram, error/backspace rate, correction latency, and charts. |

---

## 4. Modes explained

### Focused mode (default)

Real simulated keystrokes are sent to whatever window has focus — usually
Word. This is the most realistic mode: key press/release events, Shift timing,
rollover, and typos are all genuinely typed. **Word must stay focused while it
types**, so you can't use the computer for other things during the run.

### Background mode (Word COM)

Types into the chosen Word document through Word automation instead of
keystrokes. The text appears character-by-character in Word while it sits in
the background, so **you can keep using your computer**. Tradeoffs:

- It is not keystroke-level (no real key events, Shift timing, or rollover).
- It needs Word automation to work (see Troubleshooting).
- `F8`/`F9` hotkeys are disabled in this mode (they would steal keystrokes
  while you work) — use the Pause/Resume and Abort buttons instead.

### Hybrid formatting (the "Apply exact source formatting" checkbox)

Keystrokes can only type plain text, so exact formatting is applied in two
steps: (1) the text is typed like a human, then (2) the final document is made
a formatted copy of the source. You see the typing happen, and the document
ends up matching the source.

- **Word** (default): the formatting pass uses Word automation and is exact
  (fonts, bold/italic, colors, headings, lists, tables, images).
- **Google Docs**: the formatting pass builds an HTML version of the source,
  puts it on the Windows clipboard, and sends Ctrl+A / Ctrl+V in the focused
  Google Docs tab. Google Docs pastes the formatting (bold, italics, fonts,
  headings, lists, tables). Keep the tab focused during this pass; your
  previous clipboard content is restored afterwards.

---

## 5. Troubleshooting

**"Windows protected your PC" (SmartScreen).**
Click *More info → Run anyway*. The EXE is unsigned, which triggers this for
any new app.

**Word says "Call was rejected by callee" (formatting pass, document dropdown,
or background mode fails).**
This means Word is busy or running with different privileges. Close any open
Word dialog boxes, and make sure Word is **not** running as Administrator (or
run humantype as the same user). Then try again.

**A Save As dialog opened and the typing went into the filename box.**
That's Ctrl+S being pressed while the target was an unsaved blank document.
Auto-save is **off by default**; only enable it (or `--save-interval`) when the
target document already has a saved path.

**macOS / Linux notes.**
On macOS the terminal app must be allowed under *System Settings → Privacy &
Security → Accessibility*. On Linux, an X11 session is required. The EXE is
Windows-only; macOS/Linux users run from source.

---

## 6. For power users (command line)

The same features are available from the terminal:

```bash
humantype type notes.md                       # type into the focused window
humantype type notes.md --dry-run             # preview the keystroke stream
humantype type notes.md --wpm 60 --error-rate 0.05
humantype type notes.md --resume              # continue from saved progress
humantype type notes.md --save-interval 4     # auto-save every ~4 minutes
humantype type notes.md --apply-formatting    # hybrid formatting pass (Word)
humantype type notes.md --apply-formatting --format-target gdocs  # Google Docs pass
humantype type notes.md --scripted-mistakes mistakes.json
humantype gui                                 # open the GUI
humantype record -o my_typing.csv             # record your own typing (F9 to stop)
humantype analyze my_typing.csv               # stats + charts
humantype calibrate my_typing.csv -o my_profile.yaml
humantype type notes.md --profile my_profile.yaml
```

### Scripted mistakes JSON

```json
[
  {"paragraph": 1, "word": 2, "type": "transposition", "pos": 1, "notice_after": 1},
  {"word_text": "brown", "type": "doubled", "pos": 0, "notice_after": 0},
  {"word_index": 14, "type": "substitution", "wrong_char": "F", "pos": 0, "late": true}
]
```

Each entry accepts one of `word_index` (0-based across the whole document),
`paragraph`+`word` (1-based), or `word_text` (first exact match), plus:

- `type`: `substitution`, `transposition`, `doubled`, `dropped`, `shift_late`
- `pos`: character position inside the word (0-based)
- `wrong_char`: the character to type for a substitution (optional)
- `notice_after`: characters typed before noticing (0–4)
- `late`: `true` to notice a few words later and fix by navigating back
- `leave`: `true` to leave the mistake uncorrected

### config.yaml

Every parameter lives in `config.yaml` with sensible defaults. The GUI and CLI
flags override it. See the comments in the file for every key.

---

## 7. Building the EXE yourself

Two builds are available:

| Build | File | Size | Difference |
|---|---|---|---|
| Full | `dist/humantype.exe` | ~50 MB | Analyze saves matplotlib charts |
| Lite | `dist/humantype-lite.exe` | ~34 MB | No chart images; analyze still prints the full text report |

The typing engine is identical in both — the size difference is only the
chart library (matplotlib/numpy), which the Lite build drops.

```bash
pip install pyinstaller
python build_exe.py          # full build
python build_exe.py --lite   # lite build (no chart library)
```

Optional: put [UPX](https://upx.github.io/) on your `PATH` before building and
PyInstaller will compress the EXE further (that is how the sizes above are
achieved).

## 8. For developers

- Modules: `gui.py` (Tkinter UI), `typer.py` (planning + senders + COM
  executor), `extract.py`, `normalize.py`, `timing.py`, `errors.py`,
  `word_com.py`, `formatting.py`, `analyze.py`, `calibrate.py`, `record.py`.
- Tests: `pytest` (37 tests, including exact-match guarantees for the
  error-correction engine and the scripted-mistakes mode).

## License

MIT — see [LICENSE](LICENSE).
