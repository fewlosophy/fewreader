"""
Unit tests for app/services/converter.py

Covers: Markdown → HTML (with TOC), plain text → HTML, XSS escaping, encoding fallbacks
"""
import pytest
from pathlib import Path

from app.services.converter import convert


# ── Markdown ───────────────────────────────────────────────────────────────

def test_md_converts_heading(tmp_path):
    f = tmp_path / "t.md"
    f.write_text("# Hello World\n\nParagraph.\n", encoding="utf-8")
    html, _ = convert(f)
    assert "<h1" in html
    assert "Hello World" in html


def test_md_converts_paragraph(tmp_path):
    f = tmp_path / "t.md"
    f.write_text("Just a paragraph.\n", encoding="utf-8")
    html, _ = convert(f)
    assert "<p>" in html
    assert "Just a paragraph" in html


def test_md_converts_bold_and_italic(tmp_path):
    f = tmp_path / "t.md"
    f.write_text("**bold** and *italic*\n", encoding="utf-8")
    html, _ = convert(f)
    assert "<strong>" in html
    assert "<em>" in html


def test_md_converts_fenced_code(tmp_path):
    f = tmp_path / "t.md"
    f.write_text("```python\nprint('hi')\n```\n", encoding="utf-8")
    html, _ = convert(f)
    assert "<code" in html


def test_md_converts_table(tmp_path):
    f = tmp_path / "t.md"
    f.write_text("| A | B |\n|---|---|\n| 1 | 2 |\n", encoding="utf-8")
    html, _ = convert(f)
    assert "<table" in html
    assert "<td" in html


def test_md_toc_present_when_headings_exist(tmp_path):
    f = tmp_path / "t.md"
    f.write_text(
        "# Title\n\n## Section A\n\nContent.\n\n## Section B\n\nMore.\n",
        encoding="utf-8",
    )
    _, toc = convert(f)
    assert "<li>" in toc


def test_md_toc_empty_when_no_headings(tmp_path):
    f = tmp_path / "t.md"
    f.write_text("Just text, no headings.\n", encoding="utf-8")
    _, toc = convert(f)
    assert "<li>" not in toc


def test_md_returns_tuple(tmp_path):
    f = tmp_path / "t.md"
    f.write_text("# Hi\n", encoding="utf-8")
    result = convert(f)
    assert isinstance(result, tuple) and len(result) == 2


def test_md_converts_footnotes(tmp_path):
    f = tmp_path / "t.md"
    f.write_text("Text with footnote[^1].\n\n[^1]: Note content.\n", encoding="utf-8")
    html, _ = convert(f)
    assert "footnote" in html.lower()


def test_md_escapes_xss_payload(tmp_path):
    f = tmp_path / "t.md"
    f.write_text("<script>alert('xss')</script>\n\n<img src=x onerror=alert(1)>", encoding="utf-8")
    html, _ = convert(f)
    assert "<script>" not in html
    assert "alert('xss')" not in html
    assert "onerror" not in html
    assert "<img" in html


# ── Plain text ─────────────────────────────────────────────────────────────

def test_txt_double_newline_creates_paragraphs(tmp_path):
    f = tmp_path / "t.txt"
    f.write_text("Para one.\n\nPara two.\n\nPara three.", encoding="utf-8")
    html, _ = convert(f)
    assert html.count("<p>") == 3


def test_txt_single_newline_creates_br(tmp_path):
    f = tmp_path / "t.txt"
    f.write_text("Line one.\nLine two.", encoding="utf-8")
    html, _ = convert(f)
    assert "<br>" in html


def test_txt_toc_is_empty_string(tmp_path):
    f = tmp_path / "t.txt"
    f.write_text("Some text.", encoding="utf-8")
    _, toc = convert(f)
    assert toc == ""


def test_txt_empty_lines_ignored(tmp_path):
    f = tmp_path / "t.txt"
    # Multiple blank lines between paragraphs — should still give 2 <p> tags
    f.write_text("Para one.\n\n\n\nPara two.", encoding="utf-8")
    html, _ = convert(f)
    assert html.count("<p>") == 2


def test_txt_escapes_xss_payload(tmp_path):
    f = tmp_path / "t.txt"
    f.write_text("<script>alert('xss')</script>\n\n<img src=x onerror=alert(1)>", encoding="utf-8")
    html, _ = convert(f)
    assert "<script>" not in html
    assert "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;" in html or "&lt;script&gt;" in html
    assert "<img" not in html
    assert "&lt;img" in html


def test_txt_decodes_gbk_encoding(tmp_path):
    f = tmp_path / "t.txt"
    text = "第一回 甄士隐梦幻识通灵\n\n红楼梦经典章节。"
    f.write_bytes(text.encode("gb18030"))
    html, _ = convert(f)
    assert "甄士隐梦幻识通灵" in html
    assert "红楼梦经典章节" in html


def test_txt_preserves_first_paragraph_indentation(tmp_path):
    f = tmp_path / "t.txt"
    f.write_text("        第一段有八个空格。\n\n        第二段也有八个空格。", encoding="utf-8")
    html, _ = convert(f)
    # The first paragraph must retain its leading indentation via &nbsp;
    assert "<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;第一段有八个空格。</p>" in html
    assert "<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;第二段也有八个空格。</p>" in html


def test_txt_preserves_cjk_fullwidth_indentation(tmp_path):
    f = tmp_path / "t.txt"
    f.write_text("　　全角空格段落一。\n\n　　全角空格段落二。", encoding="utf-8")
    html, _ = convert(f)
    assert "<p>　　全角空格段落一。</p>" in html
    assert "<p>　　全角空格段落二。</p>" in html


# ── Error handling ─────────────────────────────────────────────────────────

def test_unsupported_extension_raises(tmp_path):
    f = tmp_path / "t.json"
    f.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported"):
        convert(f)
