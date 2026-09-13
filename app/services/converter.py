import functools
import html
from pathlib import Path
import re

import markdown as md_lib


def _read_file_text(file_path: Path) -> str:
    """
    Read file text with automatic encoding fallback.
    Tries UTF-8, then GB18030 (covers GBK/GB2312), CP1252, Latin-1,
    and finally falls back to UTF-8 with character replacement to prevent crashes.
    """
    raw_bytes = file_path.read_bytes()
    encodings = ("utf-8", "gb18030", "cp1252", "latin-1")
    for enc in encodings:
        try:
            return raw_bytes.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw_bytes.decode("utf-8", errors="replace")


@functools.lru_cache(maxsize=128)
def _cached_convert_markdown(file_str: str, mtime: float, size: int) -> tuple[str, str]:
    file_path = Path(file_str)
    text = _read_file_text(file_path)
    converter = md_lib.Markdown(
        extensions=["toc", "fenced_code", "tables", "meta", "footnotes"],
        extension_configs={
            "toc": {
                "title": "Contents",
                "toc_depth": "2-4",
            }
        },
    )
    html_out = converter.convert(text)
    toc_out = getattr(converter, "toc", "")
    return html_out, toc_out


BLANK_PARAGRAPHS_RE = re.compile(r"\n\s*\n+")


def _format_plaintext_line(line: str) -> str:
    """
    Format a single line of plain text.
    Preserves leading indentation (spaces and tabs) by converting them to &nbsp;
    so HTML rendering engines don't collapse them, while escaping all other content.
    """
    stripped_leading = line.lstrip(" \t")
    leading_len = len(line) - len(stripped_leading)
    if leading_len > 0:
        leading = line[:leading_len]
        leading_html = leading.replace("\t", "    ").replace(" ", "&nbsp;")
        return leading_html + html.escape(stripped_leading)
    return html.escape(line)


@functools.lru_cache(maxsize=128)
def _cached_convert_plaintext(file_str: str, mtime: float, size: int) -> str:
    file_path = Path(file_str)
    text = _read_file_text(file_path)
    paragraphs = BLANK_PARAGRAPHS_RE.split(text)
    parts = []
    for para in paragraphs:
        if not para.strip():
            continue
        lines = para.splitlines()
        start = 0
        while start < len(lines) and not lines[start].strip():
            start += 1
        end = len(lines)
        while end > start and not lines[end - 1].strip():
            end -= 1
        trimmed_lines = lines[start:end]
        if not trimmed_lines:
            continue
        formatted_lines = [_format_plaintext_line(l) for l in trimmed_lines]
        inner = "<br>\n".join(formatted_lines)
        parts.append(f"<p>{inner}</p>")
    return "\n".join(parts)


def clear_converter_cache() -> None:
    """Clear LRU cache for converted files."""
    _cached_convert_markdown.cache_clear()
    _cached_convert_plaintext.cache_clear()


def convert(file_path: Path) -> tuple[str, str]:
    """
    Convert a .md or .txt file to HTML with LRU caching.

    Returns:
        (html_content, toc_html)  — toc_html is empty string for .txt files.
    """
    ext = file_path.suffix.lower()

    if ext == ".md":
        stat = file_path.stat()
        return _cached_convert_markdown(str(file_path.resolve()), stat.st_mtime, stat.st_size)
    elif ext == ".txt":
        stat = file_path.stat()
        return _cached_convert_plaintext(str(file_path.resolve()), stat.st_mtime, stat.st_size), ""
    else:
        raise ValueError(f"Unsupported extension: {ext}")
