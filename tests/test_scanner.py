"""
Unit tests for app/services/scanner.py

Covers: scan_tree, find_subtree, resolve_file, natural sorting, Chinese chapter sorting, sibling navigation
"""
import pytest
from pathlib import Path

from app.services.scanner import scan_tree, find_subtree, resolve_file, get_sibling_files


# ── scan_tree ──────────────────────────────────────────────────────────────

def test_scan_empty_dir(tmp_path):
    assert scan_tree(tmp_path) == []


def test_scan_returns_root_files(books_dir):
    tree = scan_tree(books_dir)
    paths = [n["path"] for n in tree if n["type"] == "file"]
    assert "welcome.md" in paths
    assert "notes.txt" in paths


def test_scan_skips_hidden_files(books_dir):
    tree = scan_tree(books_dir)
    all_paths = [n["path"] for n in tree if n["type"] == "file"]
    assert not any(p.startswith(".") for p in all_paths)


def test_scan_skips_hidden_dirs(books_dir):
    tree = scan_tree(books_dir)
    cat_names = [n["name"] for n in tree if n["type"] == "category"]
    assert not any(n.startswith(".") for n in cat_names)


def test_scan_skips_unsupported_extensions(books_dir):
    tree = scan_tree(books_dir)
    all_paths = [n["path"] for n in tree if n["type"] == "file"]
    assert not any(p.endswith(".json") for p in all_paths)


def test_scan_dirs_come_before_files(books_dir):
    tree = scan_tree(books_dir)
    # All categories must appear before any file at the same level
    types = [n["type"] for n in tree]
    last_cat = max((i for i, t in enumerate(types) if t == "category"), default=-1)
    first_file = min((i for i, t in enumerate(types) if t == "file"), default=len(types))
    assert last_cat < first_file


def test_scan_nested_category(books_dir):
    tree = scan_tree(books_dir)
    cats = [n for n in tree if n["type"] == "category"]
    assert len(cats) == 1
    fiction = cats[0]
    assert fiction["name"] == "Fiction"
    assert len(fiction["children"]) == 1
    assert fiction["children"][0]["path"] == "fiction/story.txt"


def test_scan_human_readable_name(books_dir):
    tree = scan_tree(books_dir)
    name_by_path = {n["path"]: n["name"] for n in tree if n["type"] == "file"}
    assert name_by_path["welcome.md"] == "Welcome"
    assert name_by_path["notes.txt"] == "Notes"


def test_scan_file_has_ext_field(books_dir):
    tree = scan_tree(books_dir)
    files = [n for n in tree if n["type"] == "file"]
    for f in files:
        assert f["ext"] in {".md", ".txt"}


def test_natural_sorting_arabic_numerals(tmp_path):
    (tmp_path / "chapter-10.md").write_text("# Ch 10", encoding="utf-8")
    (tmp_path / "chapter-2.md").write_text("# Ch 2", encoding="utf-8")
    (tmp_path / "chapter-1.md").write_text("# Ch 1", encoding="utf-8")

    tree = scan_tree(tmp_path, use_cache=False)
    paths = [n["path"] for n in tree if n["type"] == "file"]
    assert paths == ["chapter-1.md", "chapter-2.md", "chapter-10.md"]


def test_chinese_chapter_sorting(tmp_path):
    chapters = [
        "第一百二十回.txt",
        "第一回.txt",
        "第七回.txt",
        "第三十回.txt",
        "第七十回.txt",
        "第一百回.txt",
    ]
    for ch in chapters:
        (tmp_path / ch).write_text("content", encoding="utf-8")

    tree = scan_tree(tmp_path, use_cache=False)
    paths = [n["path"] for n in tree if n["type"] == "file"]
    expected = [
        "第一回.txt",
        "第七回.txt",
        "第三十回.txt",
        "第七十回.txt",
        "第一百回.txt",
        "第一百二十回.txt",
    ]
    assert paths == expected


# ── find_subtree ───────────────────────────────────────────────────────────

def test_find_subtree_empty_path_returns_root(books_dir):
    tree = scan_tree(books_dir)
    assert find_subtree(tree, "") == tree


def test_find_subtree_existing_category(books_dir):
    tree = scan_tree(books_dir)
    result = find_subtree(tree, "fiction")
    assert len(result) == 1
    assert result[0]["path"] == "fiction/story.txt"


def test_find_subtree_nonexistent_returns_empty(books_dir):
    tree = scan_tree(books_dir)
    assert find_subtree(tree, "no_such_folder") == []


def test_find_subtree_with_trailing_slash(books_dir):
    tree = scan_tree(books_dir)
    result = find_subtree(tree, "fiction/")
    assert len(result) == 1


# ── resolve_file ───────────────────────────────────────────────────────────

def test_resolve_valid_markdown(books_dir):
    path = resolve_file("welcome.md", books_dir)
    assert path.is_file()
    assert path.name == "welcome.md"


def test_resolve_valid_nested_txt(books_dir):
    path = resolve_file("fiction/story.txt", books_dir)
    assert path.is_file()
    assert path.name == "story.txt"


def test_resolve_path_traversal_raises(books_dir):
    with pytest.raises(ValueError, match="outside"):
        resolve_file("../../etc/passwd", books_dir)


def test_resolve_missing_file_raises(books_dir):
    with pytest.raises(FileNotFoundError):
        resolve_file("ghost.md", books_dir)


def test_resolve_bad_extension_raises(books_dir):
    # data.json exists in books_dir but is not an allowed extension
    with pytest.raises(ValueError, match="not allowed"):
        resolve_file("data.json", books_dir)


# ── get_sibling_files ──────────────────────────────────────────────────────

def test_get_sibling_files(tmp_path):
    (tmp_path / "1.txt").write_text("1", encoding="utf-8")
    (tmp_path / "2.txt").write_text("2", encoding="utf-8")
    (tmp_path / "3.txt").write_text("3", encoding="utf-8")

    prev_f, next_f = get_sibling_files("2.txt", tmp_path)
    assert prev_f is not None and prev_f["path"] == "1.txt"
    assert next_f is not None and next_f["path"] == "3.txt"

    prev_first, next_first = get_sibling_files("1.txt", tmp_path)
    assert prev_first is None
    assert next_first is not None and next_first["path"] == "2.txt"

    prev_last, next_last = get_sibling_files("3.txt", tmp_path)
    assert prev_last is not None and prev_last["path"] == "2.txt"
    assert next_last is None


def test_get_sibling_files_with_passed_tree(tmp_path):
    (tmp_path / "1.txt").write_text("1", encoding="utf-8")
    (tmp_path / "2.txt").write_text("2", encoding="utf-8")
    tree = scan_tree(tmp_path)
    prev_f, next_f = get_sibling_files("2.txt", tmp_path, tree=tree)
    assert prev_f is not None and prev_f["path"] == "1.txt"
    assert next_f is None

