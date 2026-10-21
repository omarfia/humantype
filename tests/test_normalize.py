"""Tests for normalization."""

from humantype.normalize import (
    normalize_char,
    normalize_paragraph,
    normalize_text,
    strip_markdown,
    text_to_paragraphs,
)


def test_smart_punctuation_is_normalized_by_default():
    assert normalize_paragraph("\u201cHello\u201d \u2014 world \u2026") == '"Hello" - world ...'


def test_keep_originals_preserves_smart_punctuation():
    text = "\u201cHello\u201d \u2014 world"
    assert normalize_paragraph(text, keep_originals=True) == text


def test_whitespace_collapsed_and_stripped():
    assert normalize_paragraph("  hello\t world   again  ") == "hello world again"


def test_normalize_text_splits_paragraphs_on_blank_lines():
    text = "first line\nsecond line\n\nsecond paragraph\nwrapped"
    assert text_to_paragraphs(text) == ["first line second line", "second paragraph wrapped"]


def test_normalize_char_maps_em_dash():
    assert normalize_char("\u2014") == "-"
    assert normalize_char("\u2014", keep_originals=True) == "\u2014"


def test_strip_markdown_headings_bold_links_code():
    md = "# Title\n\nSome **bold** and [a link](http://example.com) with `code`.\n"
    out = strip_markdown(md)
    assert "Title" in out
    assert "#" not in out
    assert "**" not in out
    assert "http://example.com" not in out
    assert "a link" in out
    assert "`code`" not in out
    assert "code." in out


def test_strip_markdown_lists_and_fences():
    md = "- item one\n- item two\n\n```\nprint('x')\n```\n"
    out = strip_markdown(md)
    assert "-" not in out
    assert "item one" in out
    assert "```" not in out
    assert "print('x')" in out


def test_strip_markdown_images_and_quotes():
    md = "> quoted text\n\n![alt text](img.png)\n"
    out = strip_markdown(md)
    assert ">" not in out
    assert "quoted text" in out
    assert "alt text" in out
    assert "img.png" not in out


def test_normalize_text_removes_zero_width_and_bom():
    assert normalize_text("a\u200bb\ufeffc") == "abc"
