from __future__ import annotations

import os
from pathlib import Path
import re
import time
from typing import TypedDict, Literal


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
    type: Literal["file"]
    name: str       # human-readable title
    path: str       # URL-safe relative path from BOOKS_DIR
    ext: str        # ".md" or ".txt"


class BookCategory(TypedDict):
    type: Literal["category"]
    name: str       # human-readable folder name
    path: str       # relative path from BOOKS_DIR
    children: list  # list of BookFile | BookCategory


def _parse_chinese_numeral(s: str) -> int | None:
    """
    Parse Chinese numerals like '一', '二十', '七十五', '一百零二' into an integer.
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


def _natural_sort_key(s: str) -> list:
    """
    Sort key supporting both Arabic numerals (natural sort) and Chinese chapter numerals.
    E.g. 'Chapter 2' before 'Chapter 10', and '第一回' before '第七回' before '第一百回'.
    """
    cn_match = CN_NUMERAL_RE.search(s)
    if cn_match:
        cn_val = _parse_chinese_numeral(cn_match.group(1))
        if cn_val is not None:
            prefix = s[:cn_match.start()].lower()
            return [prefix, 0, cn_val, s.lower()]

    parts: list = []
    for token in DIGIT_SPLIT_RE.split(s.lower()):
        if token.isdigit():
            parts.append(int(token))
        else:
            parts.append(token)
    return parts


def human_title(stem: str) -> str:
    """Convert a filename stem or URL slug to a readable title."""
    return stem.replace("-", " ").replace("_", " ").title()


_human_name = human_title


def clear_scanner_cache() -> None:
    """Clear in-memory directory tree cache."""
    _tree_cache.clear()


def scan_tree(base: Path, use_cache: bool = True) -> list[BookFile | BookCategory]:
    """
    Recursively walk *base* and return a nested tree of categories and files.
    Directories come first (alphabetically), then files (alphabetically).
    Hidden entries (starting with '.') are skipped.
    Results are cached in memory for CACHE_TTL_SECONDS.
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
    entries: list[BookFile | BookCategory] = []
    dir_entries: list[os.DirEntry] = []
    file_entries: list[os.DirEntry] = []

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


def find_subtree(tree: list, cat_path: str) -> list:
    """
    Walk *tree* to find the category matching *cat_path* and return its children.
    Returns the root tree if cat_path is empty, or [] if not found.
    """
    if not cat_path:
        return tree

    parts = cat_path.strip("/").split("/")

    def _search(nodes: list, parts: list) -> list:
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
    Resolve *rel_path* relative to *base* and verify it stays within *base*
    (path-traversal guard). Returns the resolved absolute Path.
    Raises ValueError if the path escapes the content directory.
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
    Returns (prev_file, next_file).
    """
    normalized = rel_path.strip("/")
    parent_path = Path(normalized).parent.as_posix()
    if parent_path == ".":
        parent_path = ""

    if tree is None:
        tree = scan_tree(base)
    siblings = find_subtree(tree, parent_path)
    file_siblings = [item for item in siblings if item["type"] == "file"]

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


class SearchResult(TypedDict):
    name: str
    path: str
    snippet: str


def search_files(base: Path, query: str, limit: int = 20) -> list[SearchResult]:
    """
    Search for `query` in file contents lazily.
    Reads files in chunks to avoid memory spikes.
    """
    if not query:
        return []

    q = query.lower()
    tree = scan_tree(base)

    files = []
    def _flatten(nodes):
        for node in nodes:
            if node["type"] == "file":
                files.append(node)
            elif node["type"] == "category":
                _flatten(node["children"])
    _flatten(tree)

    results: list[SearchResult] = []

    for f in files:
        if len(results) >= limit:
            break

        f_path = resolve_file(f["path"], base)

        # Check name first
        if q in f["name"].lower():
            results.append({
                "name": f["name"],
                "path": f["path"],
                "snippet": f"Title match: {f['name']}"
            })
            continue

        # Check content lazily in chunks
        chunk_size = 8192
        overlap = len(q) * 2

        try:
            with open(f_path, "rb") as file_obj:
                prev_chunk = b""
                matched = False

                while not matched:
                    chunk = file_obj.read(chunk_size)
                    if not chunk:
                        break

                    # Decode chunk
                    try:
                        text_chunk = chunk.decode("utf-8")
                    except UnicodeDecodeError:
                        text_chunk = chunk.decode("utf-8", errors="replace")

                    # Also decode previous overlap
                    try:
                        text_prev = prev_chunk.decode("utf-8")
                    except UnicodeDecodeError:
                        text_prev = prev_chunk.decode("utf-8", errors="replace")

                    combined = text_prev + text_chunk
                    lower_combined = combined.lower()

                    idx = lower_combined.find(q)
                    if idx != -1:
                        # Match found, create snippet
                        start = max(0, idx - 40)
                        end = min(len(combined), idx + len(q) + 40)
                        snippet = combined[start:end].replace("\n", " ")
                        if start > 0: snippet = "..." + snippet
                        if end < len(combined): snippet = snippet + "..."

                        results.append({
                            "name": f["name"],
                            "path": f["path"],
                            "snippet": snippet
                        })
                        matched = True

                    prev_chunk = chunk[-overlap:] if len(chunk) > overlap else chunk

        except Exception:
            pass

    return results
