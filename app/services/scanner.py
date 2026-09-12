from __future__ import annotations

from pathlib import Path
from typing import TypedDict, Literal


ALLOWED_EXTENSIONS = {".md", ".txt"}


class BookFile(TypedDict):
    type: Literal["file"]
    name: str       # human-readable title
    path: str       # URL-safe relative path from BOOKS_DIR
    ext: str        # ".md" or ".txt"


class BookCategory(TypedDict):
    type: Literal["category"]
    name: str       # human-readable folder name
    path: str       # relative path from BOOKS_DIR
    children: list  # list of BookFile | BookCategory


def _human_name(stem: str) -> str:
    """Convert a filename stem to a readable title."""
    return stem.replace("-", " ").replace("_", " ").title()


def scan_tree(base: Path) -> list[BookFile | BookCategory]:
    """
    Recursively walk *base* and return a nested tree of categories and files.
    Directories come first (alphabetically), then files (alphabetically).
    Hidden entries (starting with '.') are skipped.
    """
    return _walk(base, base)


def _walk(current: Path, base: Path) -> list[BookFile | BookCategory]:
    entries: list[BookFile | BookCategory] = []
    dirs = []
    files = []

    try:
        children = list(current.iterdir())
    except PermissionError:
        return []

    for entry in children:
        if entry.name.startswith("."):
            continue
        if entry.is_dir():
            dirs.append(entry)
        elif entry.is_file() and entry.suffix.lower() in ALLOWED_EXTENSIONS:
            files.append(entry)

    dirs.sort(key=lambda p: p.name.lower())
    files.sort(key=lambda p: p.name.lower())

    for d in dirs:
        rel = d.relative_to(base).as_posix()
        subtree = _walk(d, base)
        entries.append(
            BookCategory(
                type="category",
                name=_human_name(d.name),
                path=rel,
                children=subtree,
            )
        )

    for f in files:
        rel = f.relative_to(base).as_posix()
        entries.append(
            BookFile(
                type="file",
                name=_human_name(f.stem),
                path=rel,
                ext=f.suffix.lower(),
            )
        )

    return entries


def resolve_file(rel_path: str, base: Path) -> Path:
    """
    Resolve *rel_path* relative to *base* and verify it stays within *base*
    (path-traversal guard). Returns the resolved absolute Path.
    Raises ValueError if the path escapes the books directory.
    """
    resolved_base = base.resolve()
    candidate = (resolved_base / rel_path).resolve()

    if not candidate.is_relative_to(resolved_base):
        raise ValueError(f"Path '{rel_path}' is outside the books directory.")
    if not candidate.is_file():
        raise FileNotFoundError(f"'{rel_path}' does not exist.")
    if candidate.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Extension '{candidate.suffix}' is not allowed.")

    return candidate
