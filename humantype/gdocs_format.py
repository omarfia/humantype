"""Google Docs formatting pass (Windows).

Google Docs has no COM automation like Word, so the hybrid formatting pass
works differently here: after the human-like typing finishes, humantype builds
an HTML version of the source (bold, italics, fonts, headings, lists, tables),
puts it on the Windows clipboard as CF_HTML, and sends Ctrl+A / Ctrl+V in the
focused Google Docs tab.  Google Docs pastes the HTML with its formatting.

The typing itself is unchanged; only the post-typing formatting pass uses a
paste.  The previous clipboard content is restored afterwards.
"""

from __future__ import annotations

import html as _html
import time

from .formatting import get_formatting_docx

_HTML_FORMAT_NAME = "HTML Format"


# --------------------------------------------------------------------------- #
# docx -> HTML
# --------------------------------------------------------------------------- #

def _iter_blocks(document):
    """Yield Paragraph and Table objects in document order."""
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, document)
        elif child.tag == qn("w:tbl"):
            yield Table(child, document)


def _run_html(run) -> str:
    text = _html.escape(run.text or "")
    if not text:
        return ""
    style = ""
    if run.bold:
        text = f"<b>{text}</b>"
    if run.italic:
        text = f"<i>{text}</i>"
    if run.underline:
        text = f"<u>{text}</u>"
    font_name = run.font.name
    size = run.font.size
    color = run.font.color
    if font_name or size or (color and color.rgb):
        parts = []
        if font_name:
            parts.append(f"font-family:{font_name}")
        if size and size.pt:
            parts.append(f"font-size:{size.pt:.1f}pt")
        if color and color.rgb:
            parts.append(f"color:#{str(color.rgb)}")
        style = f' style="{";".join(parts)}"'
        text = f'<span{style}>{text}</span>'
    return text


def _paragraph_html(paragraph) -> str:
    runs = "".join(_run_html(r) for r in paragraph.runs)
    text = runs or "&nbsp;"
    style_name = paragraph.style.name if paragraph.style is not None else "Normal"

    tag = "p"
    extra = ""
    if style_name.startswith("Heading"):
        try:
            level = int(style_name.split()[-1])
        except ValueError:
            level = 1
        tag = f"h{min(max(level, 1), 6)}"
    elif style_name == "Title":
        tag = "h1"
    elif style_name in ("Quote", "Intense Quote"):
        tag = "blockquote"
    elif style_name == "List Bullet":
        tag = "li"
    elif style_name == "List Number":
        tag = "li"
        extra = ' class="numbered"'

    alignment = None
    try:
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        mapping = {
            WD_ALIGN_PARAGRAPH.CENTER: "center",
            WD_ALIGN_PARAGRAPH.RIGHT: "right",
            WD_ALIGN_PARAGRAPH.JUSTIFY: "justify",
        }
        alignment = mapping.get(paragraph.paragraph_format.alignment)
    except Exception:
        alignment = None
    if alignment:
        extra += f' style="text-align:{alignment}"'

    return f"<{tag}{extra}>{text}</{tag}>"


def _table_html(table) -> str:
    rows = ["<table border='1' cellspacing='0' cellpadding='4'>"]
    for row in table.rows:
        cells = []
        for cell in row.cells:
            cell_text = " ".join(p.text for p in cell.paragraphs)
            cells.append(f"<td>{_html.escape(cell_text)}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    rows.append("</table>")
    return "".join(rows)


def docx_to_html(docx_path: str) -> str:
    """Convert a .docx to an HTML body fragment (no <html> wrapper)."""
    from docx import Document

    document = Document(docx_path)
    parts: list[str] = []
    list_stack: list[str] = []

    def close_lists():
        while list_stack:
            parts.append(f"</{list_stack.pop()}>")

    for block in _iter_blocks(document):
        if hasattr(block, "runs"):  # paragraph
            style_name = block.style.name if block.style is not None else "Normal"
            if style_name == "List Bullet":
                if not list_stack or list_stack[-1] != "ul":
                    if list_stack and list_stack[-1] == "ol":
                        parts.append("</ol>")
                        list_stack.pop()
                    parts.append("<ul>")
                    list_stack.append("ul")
            elif style_name == "List Number":
                if not list_stack or list_stack[-1] != "ol":
                    if list_stack and list_stack[-1] == "ul":
                        parts.append("</ul>")
                        list_stack.pop()
                    parts.append("<ol>")
                    list_stack.append("ol")
            else:
                close_lists()
            parts.append(_paragraph_html(block))
        else:  # table
            close_lists()
            parts.append(_table_html(block))
    close_lists()
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Windows clipboard (CF_HTML)
# --------------------------------------------------------------------------- #

def _require_clipboard():
    try:
        import win32clipboard
        return win32clipboard
    except ImportError as exc:
        raise RuntimeError(
            "The Google Docs formatting pass needs pywin32 (pip install pywin32)"
        ) from exc


def backup_clipboard() -> dict:
    """Save the current clipboard text/HTML so it can be restored."""
    win32clipboard = _require_clipboard()
    saved = {}
    try:
        win32clipboard.OpenClipboard()
        cf_html = win32clipboard.RegisterClipboardFormat(_HTML_FORMAT_NAME)
        for fmt in (win32clipboard.CF_UNICODETEXT, cf_html):
            try:
                if win32clipboard.IsClipboardFormatAvailable(fmt):
                    saved[fmt] = win32clipboard.GetClipboardData(fmt)
            except Exception:
                pass
    except Exception:
        pass
    finally:
        try:
            win32clipboard.CloseClipboard()
        except Exception:
            pass
    return saved


def restore_clipboard(saved: dict):
    if not saved:
        return
    win32clipboard = _require_clipboard()
    try:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        for fmt, value in saved.items():
            win32clipboard.SetClipboardData(fmt, value)
    except Exception:
        pass
    finally:
        try:
            win32clipboard.CloseClipboard()
        except Exception:
            pass


def set_clipboard_html(body_html: str, plain_text: str):
    """Put an HTML fragment (plus plain text) on the Windows clipboard."""
    win32clipboard = _require_clipboard()
    cf_html = win32clipboard.RegisterClipboardFormat(_HTML_FORMAT_NAME)

    html_doc = f"<html><body><!--StartFragment-->{body_html}<!--EndFragment--></body></html>"
    placeholder = (
        "Version:0.9\r\n"
        "StartHTML:0000000000\r\n"
        "EndHTML:0000000000\r\n"
        "StartFragment:0000000000\r\n"
        "EndFragment:0000000000\r\n"
    )
    prefix_len = len(placeholder.encode("ascii"))
    html_bytes = html_doc.encode("utf-8")
    start_html = prefix_len
    start_frag = prefix_len + html_bytes.index(b"<!--StartFragment-->") + len(b"<!--StartFragment-->")
    end_frag = prefix_len + html_bytes.index(b"<!--EndFragment-->")
    end_html = prefix_len + len(html_bytes)
    header = (
        f"Version:0.9\r\n"
        f"StartHTML:{start_html:010d}\r\n"
        f"EndHTML:{end_html:010d}\r\n"
        f"StartFragment:{start_frag:010d}\r\n"
        f"EndFragment:{end_frag:010d}\r\n"
    )
    data = header.encode("ascii") + html_bytes

    try:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(cf_html, data)
        win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, plain_text)
    finally:
        try:
            win32clipboard.CloseClipboard()
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# The paste pass
# --------------------------------------------------------------------------- #

def _send_ctrl_key(controller, char: str):
    from pynput.keyboard import Key

    controller.press(Key.ctrl)
    controller.press(char)
    controller.release(char)
    controller.release(Key.ctrl)


def apply_gdocs_formatting(source_path: str, status_cb=None) -> None:
    """Apply source formatting to the focused Google Docs tab.

    The Google Docs tab must stay focused; this sends Ctrl+A then Ctrl+V with
    an HTML clipboard so Google Docs pastes the formatted source.
    """
    from .extract import extract_paragraphs
    from pynput.keyboard import Controller

    fmt_docx = get_formatting_docx(source_path)
    body_html = docx_to_html(fmt_docx)
    paragraphs = extract_paragraphs(fmt_docx)
    plain_text = "\n".join(paragraphs)

    if status_cb:
        status_cb("applying formatting to Google Docs - keep the tab focused...")
    time.sleep(0.5)

    saved = backup_clipboard()
    try:
        set_clipboard_html(body_html, plain_text)
        controller = Controller()
        _send_ctrl_key(controller, "a")
        time.sleep(0.3)
        _send_ctrl_key(controller, "v")
        time.sleep(1.0)
    finally:
        restore_clipboard(saved)

    if status_cb:
        status_cb("Google Docs formatting applied (clipboard restored)")
