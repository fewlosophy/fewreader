"""
Unit tests for app/services/converter.py

Covers: Markdown → HTML (with TOC), plain text → HTML
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


# ── Error handling ─────────────────────────────────────────────────────────

def test_unsupported_extension_raises(tmp_path):
    f = tmp_path / "t.json"
    f.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported"):
        convert(f)
