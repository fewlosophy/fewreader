from __future__ import annotations

import os
from pathlib import Path
import re
import time
from typing import TypedDict, Literal, Any


ALLOWED_EXTENSIONS = {".md", ".txt"}
CACHE_TTL_SECONDS = 10.0

CN_NUMERAL_RE = re.compile(r"第([一二三四五六七八九十百千万\d]+)[回章节卷集]")
DIGIT_SPLIT_RE = re.compile(r"(\d+)")

_tree_cache: dict[str, tuple[float, list[BookFile | BookCategory]]] = {}

CN_NUM = {
    "零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    "百": 100, "千": 1000, "万": 10000,
}


class BookFile(TypedDict):
    """
    Represents a readable file in the library tree.
    """
    type: Literal["file"]
    name: str       # human-readable title
    path: str       # URL-safe relative path from BOOKS_DIR
    ext: str        # ".md" or ".txt"


class BookCategory(TypedDict):
    """
    Represents a directory containing files or other categories.
    """
    type: Literal["category"]
    name: str       # human-readable folder name
    path: str       # relative path from BOOKS_DIR
    children: list[BookFile | BookCategory]  # list of BookFile | BookCategory


def _parse_chinese_numeral(s: str) -> int | None:
    """
    Parse Chinese numerals like '一', '二十', '七十五', '一百零二' into an integer.

    Args:
        s (str): The Chinese numeral string to parse.

    Returns:
        int | None: The parsed integer, or None if parsing fails.
    """
    if not s:
        return None
    if s.isdigit():
        return int(s)
    num = 0
    temp = 0
    for char in s:
        if char not in CN_NUM:
            return None
        v = CN_NUM[char]
        if v in (10, 100, 1000, 10000):
            if temp == 0:
                temp = 1
            num += temp * v
            temp = 0
        else:
            temp = v
    num += temp
    return num if (num > 0 or s in ("零", "〇")) else None


def _natural_sort_key(s: str) -> list[Any]:
    """
    Generate a sort key supporting Arabic numerals and Chinese chapter numerals.

    E.g. 'Chapter 2' before 'Chapter 10', and '第一回' before '第七回' before '第一百回'.

    Args:
        s (str): The string to generate a sort key for.

    Returns:
        list[Any]: A list of sortable components.
    """
    cn_match = CN_NUMERAL_RE.search(s)
    if cn_match:
        cn_val = _parse_chinese_numeral(cn_match.group(1))
        if cn_val is not None:
            prefix = s[:cn_match.start()].lower()
            return [prefix, 0, cn_val, s.lower()]

    parts: list[Any] = []
    for token in DIGIT_SPLIT_RE.split(s.lower()):
        if token.isdigit():
            parts.append(int(token))
        else:
            parts.append(token)
    return parts


def human_title(stem: str) -> str:
    """
    Convert a filename stem or URL slug to a readable title.

    Args:
        stem (str): The raw stem or slug string.

    Returns:
        str: The human-readable title.
    """
    return stem.replace("-", " ").replace("_", " ").title()


_human_name = human_title


def clear_scanner_cache() -> None:
    """Clear the in-memory directory tree cache."""
    _tree_cache.clear()


def scan_tree(base: Path, use_cache: bool = True) -> list[BookFile | BookCategory]:
    """
    Recursively walk `base` and return a nested tree of categories and files.

    Directories come first (alphabetically), then files (alphabetically).
    Hidden entries (starting with '.') are skipped.
    Results are cached in memory for CACHE_TTL_SECONDS.

    Args:
        base (Path): The root path to start scanning from.
        use_cache (bool): Whether to return a cached tree if available.

    Returns:
        list[BookFile | BookCategory]: The list representing the directory tree.
    """
    resolved_base = base.resolve()
    cache_key = str(resolved_base)
    now = time.time()

    if use_cache and cache_key in _tree_cache:
        ts, cached_tree = _tree_cache[cache_key]
        if now - ts < CACHE_TTL_SECONDS:
            return cached_tree

    tree = _walk(resolved_base, resolved_base)
    _tree_cache[cache_key] = (now, tree)
    return tree


def _walk(current: Path, base: Path) -> list[BookFile | BookCategory]:
    """
    Internal recursive function to walk the directory tree.

    Args:
        current (Path): The current directory being walked.
        base (Path): The root base path used for calculating relative paths.

    Returns:
        list[BookFile | BookCategory]: The nested contents of the current directory.
    """
    entries: list[BookFile | BookCategory] = []
    dir_entries: list[os.DirEntry[str]] = []
    file_entries: list[os.DirEntry[str]] = []

    try:
        with os.scandir(current) as it:
            for entry in it:
                if entry.name.startswith("."):
                    continue
                try:
                    if entry.is_dir(follow_symlinks=False):
                        dir_entries.append(entry)
                    elif entry.is_file(follow_symlinks=False):
                        if Path(entry.name).suffix.lower() in ALLOWED_EXTENSIONS:
                            file_entries.append(entry)
                except OSError:
                    continue
    except (PermissionError, FileNotFoundError):
        return []

    dir_entries.sort(key=lambda e: _natural_sort_key(e.name))
    file_entries.sort(key=lambda e: _natural_sort_key(e.name))

    for d in dir_entries:
        d_path = Path(d.path)
        rel = d_path.relative_to(base).as_posix()
        subtree = _walk(d_path, base)
        entries.append(
            BookCategory(
                type="category",
                name=human_title(d.name),
                path=rel,
                children=subtree,
            )
        )

    for f in file_entries:
        f_path = Path(f.path)
        rel = f_path.relative_to(base).as_posix()
        entries.append(
            BookFile(
                type="file",
                name=human_title(f_path.stem),
                path=rel,
                ext=f_path.suffix.lower(),
            )
        )

    return entries


def find_subtree(tree: list[BookFile | BookCategory], cat_path: str) -> list[BookFile | BookCategory]:
    """
    Walk `tree` to find the category matching `cat_path` and return its children.

    Returns the root tree if cat_path is empty, or [] if not found.

    Args:
        tree (list[BookFile | BookCategory]): The directory tree to search.
        cat_path (str): The relative category path to find.

    Returns:
        list[BookFile | BookCategory]: The children of the matched category, or the entire tree.
    """
    if not cat_path:
        return tree

    parts = cat_path.strip("/").split("/")

    def _search(nodes: list[BookFile | BookCategory], parts: list[str]) -> list[BookFile | BookCategory]:
        target = parts[0]
        rest = parts[1:]
        for node in nodes:
            if node["type"] == "category" and node["path"].split("/")[-1] == target:
                if not rest:
                    return node["children"]
                return _search(node["children"], rest)
        return []

    return _search(tree, parts)


def resolve_file(rel_path: str, base: Path) -> Path:
    """
    Resolve `rel_path` relative to `base` and verify it stays within `base`.

    Acts as a path-traversal guard.

    Args:
        rel_path (str): The relative path of the file to resolve.
        base (Path): The base content directory.

    Raises:
        ValueError: If the path escapes the content directory or has an invalid extension.
        FileNotFoundError: If the resolved path does not exist.

    Returns:
        Path: The resolved absolute Path object.
    """
    resolved_base = base.resolve()
    candidate = (resolved_base / rel_path).resolve()

    if not candidate.is_relative_to(resolved_base):
        raise ValueError(f"Path '{rel_path}' is outside the content directory.")
    if not candidate.is_file():
        raise FileNotFoundError(f"'{rel_path}' does not exist.")
    if candidate.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Extension '{candidate.suffix}' is not allowed.")

    return candidate


def get_sibling_files(
    rel_path: str,
    base: Path,
    tree: list[BookFile | BookCategory] | None = None,
) -> tuple[BookFile | None, BookFile | None]:
    """
    Find previous and next sibling files relative to current file within its parent directory.

    Args:
        rel_path (str): The relative path of the current file.
        base (Path): The base content directory.
        tree (list[BookFile | BookCategory] | None): Optional cached directory tree.

    Returns:
        tuple[BookFile | None, BookFile | None]: A tuple containing the previous and next BookFile items, if they exist.
    """
    normalized = rel_path.strip("/")
    parent_path = Path(normalized).parent.as_posix()
    if parent_path == ".":
        parent_path = ""

    if tree is None:
        tree = scan_tree(base)
    siblings = find_subtree(tree, parent_path)
    file_siblings = [item for item in siblings if item["type"] == "file"]  # type: ignore

    idx = -1
    for i, f in enumerate(file_siblings):
        if f["path"] == normalized:
            idx = i
            break

    if idx == -1:
        return (None, None)

    prev_file = file_siblings[idx - 1] if idx > 0 else None
    next_file = file_siblings[idx + 1] if idx < len(file_siblings) - 1 else None
    return (prev_file, next_file)
