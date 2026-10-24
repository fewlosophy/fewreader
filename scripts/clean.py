"""Shared text-cleaning utilities for the fewreader ingest pipeline.

Pure stdlib helpers that turn raw Project-Gutenberg / Wikisource text into
clean, flowing reading typography matching the existing content/ convention
(four-space indented paragraphs, unwrapped hard-wraps, typographic dashes
and ellipses). CJK-safe: no word-level wrapping is applied to CJK runs.

A "chapter" is one boundary-marker line (e.g. ``BOOK I``, ``第001回``) plus
the text up to the next marker. Non-critical formatting helpers live in
:func:`normalize_paragraphs`.
"""
from __future__ import annotations

import re

# Matches the Gutenberg START/END banners so we can slice out the body.
PG_START_RE = re.compile(r"^\*\*\*\s*START\b.*$", re.IGNORECASE)
PG_END_RE = re.compile(r"^\*\*\*\s*END\b.*$", re.IGNORECASE)

# A short mostly-uppercase line is treated as a heading (bare in output, no
# indent): "BOOK I", "PART II", "SOCRATES - GLAUCON", "THE INTRODUCTION", etc.
HEADING_RE = re.compile(r"^\s*[A-Z][A-Z0-9 \-.,'()/:]{0,44}\s*$")


def _is_blank(s: str) -> bool:
    return not s.strip()


def is_heading(paragraph: str) -> bool:
    return bool(HEADING_RE.match(paragraph))


def strip_pg_boilerplate(text: str) -> str:
    """Return the region between the Gutenberg START and END markers.

    Falls back to the whole text when the markers are absent.
    """
    lines = text.splitlines()
    start = [i for i, l in enumerate(lines) if PG_START_RE.match(l.strip())]
    end = [i for i, l in enumerate(lines) if PG_END_RE.match(l.strip())]
    if not start or not end:
        return text
    return "\n".join(lines[max(start) + 1 : min(end)])


def normalize_typography(text: str) -> str:
    """Apply typographic cleanup, CJK-safe (no word-level wrapping)."""
    text = text.replace("\r", "")
    text = text.replace("\u00a0", " ").replace("\u2013", "—")     # nbsp, en-dash
    text = text.replace("\u3000", " ").replace("--", "—")         # ideographic space, type dash
    text = re.sub(r"\.{3,}", "…", text)                            # ellipsis
    text = re.sub(r"(?<!\w)_([^_\n]+?)_(?!\w)", r"\1", text)      # _italic_ -> plain
    text = re.sub(r"[ \t]{2,}", " ", text)                         # collapse runs of space/tab
    return text


def unwrap_paragraph(lines: list[str]) -> str:
    """Join hard-wrapped physical lines into one flowing logical paragraph."""
    parts = [l.strip() for l in lines if l.strip()]
    return " ".join(parts)


def split_blocks(text: str) -> list[list[str]]:
    """Split *text* into paragraph blocks on blank lines (lists of physical lines)."""
    return [block.splitlines() for block in re.split(r"\n\s*\n+", text) if block.strip()]


def _indent_for(para: str) -> str:
    """CJK paragraphs get two full-width spaces (hlm convention); Latin keeps 4 SP."""
    return "\u3000\u3000" if re.search(r"[\u3400-\u9fff\uf900-\ufaff]", para) else "    "


def _format_blocks(blocks: list[list[str]]) -> str:
    """Render paragraph-blocks: heading blocks bare, body blocks indented."""
    out: list[str] = []
    for block in blocks:
        para = normalize_typography(unwrap_paragraph(block)).strip()
        if not para:
            continue
        out.append(para if is_heading(para) else _indent_for(para) + para)
    return "\n\n".join(out)


def clean_paragraphs(text: str) -> str:
    """Clean a single text span (no chapter split) into the content/ convention."""
    blocks = split_blocks(text)
    if not blocks:
        return ""
    return _format_blocks(blocks) + "\n"


def clean_to_chapters(text: str, boundary_re: re.Pattern) -> tuple[str, list[tuple[str, str]]]:
    """Split *text* into chapters on *boundary_re* marker lines.

    Returns ``(preamble_text, [(heading, body_text)])`` where the preamble is
    everything before the first marker and each body is already formatted
    (unwrapped, normalized, indented). The preamble is returned verbatim
    (already stripped) so the caller can decide how to present front matter.
    """
    lines = text.splitlines()
    marker_idx = [i for i, ln in enumerate(lines) if boundary_re.match(ln.strip())]

    preamble = "\n".join(lines[: marker_idx[0]]).strip() if marker_idx else text.strip()

    chapters: list[tuple[str, str]] = []
    for k, marker_line in enumerate(marker_idx):
        heading = lines[marker_line].strip()
        end = marker_idx[k + 1] if k + 1 < len(marker_idx) else len(lines)
        span = "\n".join(lines[marker_line + 1 : end])
        body = _format_blocks(split_blocks(span)).strip()
        chapters.append((heading, (body + "\n") if body else ""))

    return preamble, chapters
