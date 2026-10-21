"""Formatting-source handling for the hybrid mode.

The typing engine types plain text; this module produces a `.docx` that
carries the source document's formatting.  After typing, that docx is pasted
over the typed document by `word_com.apply_exact_formatting`, so the final
Word document matches the source exactly.

Pipeline:
    .docx            -> used directly
    .doc             -> converted to .docx with Word
    .pdf             -> converted to .docx with Word (Word's PDF reflow)
    .md / .markdown  -> rendered to a styled .docx here (headings, bold,
                        italics, code, lists, blockquotes)
    .txt             -> plain paragraphs, no formatting
"""

from __future__ import annotations

import os
import re
import tempfile

from . import word_com

_INLINE_RE = re.compile(
    r"(\*\*\*.+?\*\*\*|\*\*.+?\*\*|\*.+?\*|`[^`]+`|\[[^\]]+\]\([^)]*\))"
)


def get_formatting_docx(source_path: str) -> str:
    """Return the path of a .docx that represents the source's formatting."""
    ext = os.path.splitext(source_path)[1].lower()
    if ext == ".docx":
        return source_path
    if ext == ".doc":
        return word_com.convert_to_docx(source_path)
    if ext == ".pdf":
        return word_com.convert_to_docx(source_path)
    if ext in (".md", ".markdown"):
        out = os.path.join(tempfile.mkdtemp(prefix="humantype_md_"), "source.docx")
        return render_markdown_to_docx(source_path, out)
    if ext == ".txt":
        out = os.path.join(tempfile.mkdtemp(prefix="humantype_txt_"), "source.docx")
        return _render_plain_to_docx(source_path, out)
    raise ValueError(f"no formatting pipeline for {ext!r}")


# --------------------------------------------------------------------------- #
# Markdown -> docx
# --------------------------------------------------------------------------- #

def render_markdown_to_docx(md_path: str, out_path: str) -> str:
    with open(md_path, "r", encoding="utf-8-sig") as fh:
        text = fh.read()
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return markdown_text_to_docx(text, out_path)


def markdown_text_to_docx(text: str, out_path: str) -> str:
    from docx import Document
    from docx.shared import Pt

    document = Document()
    normal = document.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)

    in_fence = False
    fence_lines = []
    for raw_line in text.split("\n"):
        line = raw_line.rstrip()

        if line.strip().startswith("```") or line.strip().startswith("~~~"):
            if not in_fence:
                in_fence = True
                fence_lines = []
            else:
                in_fence = False
                _add_code_block(document, fence_lines)
            continue
        if in_fence:
            fence_lines.append(line)
            continue

        stripped = line.strip()
        if not stripped:
            continue

        if re.match(r"^#{1,6}\s+", stripped):
            level = len(stripped) - len(stripped.lstrip("#"))
            heading = re.sub(r"^#{1,6}\s+", "", stripped)
            para = document.add_heading("", level=min(level, 6))
            _inline_runs(para, heading)
        elif re.match(r"^[-*+]\s+", stripped):
            item = re.sub(r"^[-*+]\s+", "", stripped)
            para = document.add_paragraph(style="List Bullet")
            _inline_runs(para, item)
        elif re.match(r"^\d{1,3}[.)]\s+", stripped):
            item = re.sub(r"^\d{1,3}[.)]\s+", "", stripped)
            para = document.add_paragraph(style="List Number")
            _inline_runs(para, item)
        elif stripped.startswith(">"):
            quote = re.sub(r"^>\s?", "", stripped)
            para = document.add_paragraph(style="Quote")
            _inline_runs(para, quote)
        elif re.match(r"^([-*_])(\s*\1){2,}\s*$", stripped):
            continue  # horizontal rule
        else:
            para = document.add_paragraph()
            _inline_runs(para, stripped)

    document.save(out_path)
    return out_path


def _add_code_block(document, lines: list[str]):
    for line in lines:
        para = document.add_paragraph()
        run = para.add_run(line if line else " ")
        run.font.name = "Consolas"


def _inline_runs(container, text: str):
    """Add runs for inline markdown (**bold**, *italic*, `code`, [links])."""
    parts = _INLINE_RE.split(text)
    for part in parts:
        if not part:
            continue
        bold = italic = code = False
        content = part
        if part.startswith("***") and part.endswith("***") and len(part) >= 6:
            bold = italic = True
            content = part[3:-3]
        elif part.startswith("**") and part.endswith("**") and len(part) >= 4:
            bold = True
            content = part[2:-2]
        elif part.startswith("*") and part.endswith("*") and len(part) >= 2:
            italic = True
            content = part[1:-1]
        elif part.startswith("`") and part.endswith("`") and len(part) >= 2:
            code = True
            content = part[1:-1]
        elif part.startswith("[") and "]" in part and part.endswith(")"):
            match = re.match(r"\[([^\]]+)\]\([^)]*\)", part)
            if match:
                content = match.group(1)
        run = container.add_run(content)
        run.bold = bold
        run.italic = italic
        if code:
            run.font.name = "Consolas"
    return container


def _render_plain_to_docx(txt_path: str, out_path: str) -> str:
    from docx import Document

    document = Document()
    with open(txt_path, "r", encoding="utf-8-sig") as fh:
        text = fh.read()
    from .normalize import text_to_paragraphs

    for para in text_to_paragraphs(text):
        document.add_paragraph(para)
    document.save(out_path)
    return out_path
