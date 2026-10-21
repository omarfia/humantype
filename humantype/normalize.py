"""Text normalization and Markdown stripping."""

from __future__ import annotations

import re

# Smart quotes, dashes, ellipses and friends -> characters that can be typed
# reliably on a US keyboard.
SMART_MAP = {
    "\u2018": "'",  # left single quote
    "\u2019": "'",  # right single quote
    "\u201a": "'",  # single low-9 quote
    "\u201b": "'",  # single high-reversed-9 quote
    "\u201c": '"',  # left double quote
    "\u201d": '"',  # right double quote
    "\u201e": '"',  # double low-9 quote
    "\u201f": '"',  # double high-reversed-9 quote
    "\u2013": "-",  # en dash
    "\u2014": "-",  # em dash
    "\u2015": "-",  # horizontal bar
    "\u2212": "-",  # minus sign
    "\u2026": "...",  # ellipsis
    "\u00a0": " ",  # non-breaking space
    "\u202f": " ",  # narrow no-break space
    "\u2009": " ",  # thin space
    "\u200a": " ",  # hair space
    "\u200b": "",  # zero-width space
    "\ufeff": "",  # BOM / zero-width no-break space
    "\u00ad": "",  # soft hyphen
    "\u2122": "(tm)",
    "\u00ae": "(R)",
    "\u00a9": "(c)",
    "\u2010": "-",
    "\u2011": "-",
    "\u2012": "-",
}

_HEADING_RE = re.compile(r"^[ \t]{0,3}#{1,6}\s*", re.MULTILINE)
_HR_RE = re.compile(r"^[ \t]{0,3}([-*_])(\s*\1){2,}\s*$", re.MULTILINE)
_BLOCKQUOTE_RE = re.compile(r"^[ \t]{0,3}>\s?", re.MULTILINE)
_LIST_RE = re.compile(r"^[ \t]{0,3}(?:[-*+]|\d{1,3}[.)])\s+", re.MULTILINE)
_CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_CODE_FENCE_TILDE_RE = re.compile(r"~~~.*?~~~", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`([^`]*)`")
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_BOLD_ITALIC_RE = re.compile(r"(\*\*\*|___)(.+?)\1")
_BOLD_RE = re.compile(r"(\*\*|__)(.+?)\1")
_ITALIC_RE = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)|(?<!_)_([^_\n]+)_(?!_)")
_HTML_RE = re.compile(r"<[^>]+>")


def normalize_char(ch: str, keep_originals: bool = False) -> str:
    """Normalize a single character."""
    if keep_originals:
        return ch
    return SMART_MAP.get(ch, ch)


def normalize_paragraph(text: str, keep_originals: bool = False) -> str:
    """Normalize one paragraph of text.

    Collapses stray whitespace and converts smart punctuation unless
    `keep_originals` is true.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\t", " ")
    if not keep_originals:
        for src, dst in SMART_MAP.items():
            text = text.replace(src, dst)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_text(text: str, keep_originals: bool = False) -> str:
    """Normalize a whole document and split it into paragraphs."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not keep_originals:
        for src, dst in SMART_MAP.items():
            text = text.replace(src, dst)
    # Collapse whitespace per line, then join lines into paragraphs on
    # blank lines.
    lines = []
    for line in text.split("\n"):
        line = re.sub(r"[ \t\f\v]+", " ", line).strip()
        lines.append(line)
    paragraphs = []
    current = []
    for line in lines:
        if line:
            current.append(line)
        else:
            if current:
                paragraphs.append(" ".join(current))
                current = []
    if current:
        paragraphs.append(" ".join(current))
    return "\n\n".join(paragraphs)


def text_to_paragraphs(text: str, keep_originals: bool = False) -> list[str]:
    """Split normalized text into a list of paragraph strings."""
    normalized = normalize_text(text, keep_originals=keep_originals)
    if not normalized.strip():
        return []
    return [p for p in normalized.split("\n\n") if p.strip()]


def strip_markdown(text: str) -> str:
    """Strip Markdown syntax down to plain prose, keeping paragraph breaks."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Code fences: keep the content but drop the fence markers.
    text = _CODE_FENCE_RE.sub(lambda m: m.group(0).strip("`").strip(), text)
    text = _CODE_FENCE_TILDE_RE.sub(lambda m: m.group(0).strip("~").strip(), text)
    # Images and links -> their text.
    text = _IMAGE_RE.sub(r"\1", text)
    text = _LINK_RE.sub(r"\1", text)
    # Inline code -> its content.
    text = _INLINE_CODE_RE.sub(r"\1", text)
    # Headings, blockquotes, list markers, horizontal rules.
    text = _HEADING_RE.sub("", text)
    text = _BLOCKQUOTE_RE.sub("", text)
    text = _LIST_RE.sub("", text)
    text = _HR_RE.sub("", text)
    # Bold / italic / strikethrough markers.
    text = _BOLD_ITALIC_RE.sub(r"\2", text)
    text = _BOLD_RE.sub(r"\2", text)
    text = _ITALIC_RE.sub(r"\1\2", text)
    text = re.sub(r"~~(.+?)~~", r"\1", text)
    # Raw HTML.
    text = _HTML_RE.sub("", text)
    return text
