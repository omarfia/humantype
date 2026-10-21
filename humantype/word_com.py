"""Microsoft Word automation helpers (Windows only, requires pywin32).

Used for:
- listing the user's open Word documents so the GUI can target one
- activating the chosen document before typing
- converting .doc / .pdf sources to .docx
- applying a source document's exact formatting to the typed document
"""

from __future__ import annotations

import os
import tempfile

try:
    import win32com.client
    HAVE_COM = True
except ImportError:  # pragma: no cover
    HAVE_COM = False


class WordComError(Exception):
    """Raised when Word automation is unavailable or fails."""


def _friendly(exc: Exception, action: str) -> WordComError:
    message = str(exc)
    if "rejected by callee" in message.lower() or "-2147418111" in message:
        return WordComError(
            f"Word is busy or running with different privileges, so {action} "
            f"failed ({message}).  Close any Word dialog boxes, make sure Word "
            "is not running as Administrator (or run humantype as the same "
            "user), then try again."
        )
    return WordComError(f"{action} failed: {message}")


# Word constants
WD_FORMAT_ORIGINAL = 16  # wdFormatOriginalFormatting
WD_FORMAT_DOCX = 16  # wdFormatDocumentDefault (.docx)
WD_FORMAT_XML = 12  # wdFormatXMLDocument


def available() -> bool:
    return HAVE_COM


def require_com():
    if not HAVE_COM:
        raise WordComError(
            "Word automation requires pywin32; install it with: pip install pywin32"
        )


def get_word(attach: bool = True):
    """Return a Word.Application object.

    With `attach=True` we try to reuse the user's already-running Word so we
    can see and control their open documents.  Falls back to a new hidden
    instance when Word is not running.
    """
    require_com()
    if attach:
        try:
            return win32com.client.GetActiveObject("Word.Application")
        except Exception:
            pass
    word = win32com.client.Dispatch("Word.Application")
    try:
        word.Visible = False
    except Exception:
        pass
    return word


def list_open_documents(word=None):
    """Return [(index, name, path), ...] for documents open in Word."""
    require_com()
    own_word = word is None
    word = word or get_word(attach=True)
    docs = []
    try:
        count = word.Documents.Count
    except Exception as exc:
        raise _friendly(exc, "reading the list of open Word documents") from exc
    for i in range(1, count + 1):
        try:
            doc = word.Documents(i)
            name = doc.Name
            path = ""
            try:
                path = doc.Path or ""
            except Exception:
                path = ""
            docs.append((i, name, path))
        except Exception:
            continue
    return docs


def activate_document(word, index: int):
    """Bring a document to the front so keystrokes land in it."""
    require_com()
    try:
        word.Documents(index).Activate()
        try:
            word.WindowState = 1  # wdWindowStateNormal
        except Exception:
            pass
    except Exception as exc:
        raise _friendly(exc, "activating the chosen Word document") from exc


def get_active_document(word):
    require_com()
    return word.ActiveDocument


def document_text(doc) -> str:
    """Plain text of a Word document (for verification)."""
    try:
        return str(doc.Content.Text)
    except Exception as exc:
        raise _friendly(exc, "reading the Word document text") from exc


def convert_to_docx(path: str, workdir: str | None = None) -> str:
    """Convert a .doc or .pdf to a temporary .docx using Word.

    Returns the path of the new .docx file.
    """
    require_com()
    workdir = workdir or tempfile.mkdtemp(prefix="humantype_conv_")
    base = os.path.splitext(os.path.basename(path))[0]
    out_path = os.path.join(workdir, base + "_converted.docx")

    word = get_word(attach=False)  # hidden instance; don't disturb the user's Word
    word.Visible = False
    try:
        word.DisplayAlerts = 0
    except Exception:
        pass

    doc = None
    try:
        doc = word.Documents.Open(
            FileName=os.path.abspath(path),
            ConfirmConversions=False,
            ReadOnly=True,
            AddToRecentFiles=False,
            Visible=False,
        )
        doc.SaveAs2(out_path, FileFormat=WD_FORMAT_DOCX)
        doc.Close(False)
        doc = None
    except Exception as exc:
        raise _friendly(exc, f"converting {os.path.basename(path)} to .docx") from exc
    finally:
        if doc is not None:
            try:
                doc.Close(False)
            except Exception:
                pass
        try:
            word.Quit()
        except Exception:
            pass
    return out_path


def apply_exact_formatting(source_docx_path: str, target_doc) -> None:
    """Replace the target document's content with the source's exact content.

    The target document ends up an exact formatted copy of the source
    (text, fonts, styles, tables, images).  This is the post-typing pass of
    the hybrid mode: the text was already typed by hand, and now formatting
    is applied with one Word paste operation.
    """
    require_com()
    word = target_doc.Application
    try:
        word.DisplayAlerts = 0
    except Exception:
        pass

    src = None
    try:
        src = word.Documents.Open(
            FileName=os.path.abspath(source_docx_path),
            ConfirmConversions=False,
            ReadOnly=True,
            AddToRecentFiles=False,
            Visible=False,
        )
        src.Content.Copy()
        target_doc.Content.Select()
        word.Selection.PasteAndFormat(WD_FORMAT_ORIGINAL)
        src.Close(False)
        src = None
    except Exception as exc:
        raise _friendly(exc, "applying the source formatting") from exc
    finally:
        if src is not None:
            try:
                src.Close(False)
            except Exception:
                pass
