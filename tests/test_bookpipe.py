"""Tests for scripts/bookpipe.py — the registry-driven ingest pipeline."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import bookpipe  # noqa: E402

BOOK = {
    "slug": "demo",
    "title": "Demo",
    "category": "fiction",
    "source": "wikisource",
    "source_id": "Demo",
    "chapter_total": 3,
    "profile": "wikisource-header",
    "lang": "zh",
    "min_chars": 10,
    "max_chars": 100000,
}

BODY = "\u3000\u3000第一章的正文內容，用來測試驗證器。" * 3


def make_tree(tmp_path: Path, bodies: list[str], headings: list[str] | None = None,
              total: int | None = None, index_links: int | None = None) -> Path:
    root = tmp_path / "demo"
    root.mkdir()
    headings = headings or [f"回目{i}" for i in range(1, len(bodies) + 1)]
    names = []
    for i, (body, head) in enumerate(zip(bodies, headings), 1):
        name = f"第{i:03d}回 {head}.txt"
        (root / name).write_text(body, encoding="utf-8")
        names.append(name)
    n_links = len(names) if index_links is None else index_links
    (root / "Demo.md").write_text(
        "# Demo\n\n## 目錄\n\n" + "\n".join(
            f"{i:03d}. [x](./{n})" for i, n in enumerate(names[:n_links], 1)) + "\n",
        encoding="utf-8")
    (root / ".meta.json").write_text(
        json.dumps({"chapters": {n: "x" for n in names}}, ensure_ascii=False), encoding="utf-8")
    return root


def test_clean_book_passes(tmp_path):
    root = make_tree(tmp_path, [BODY, BODY + "二", BODY + "三"])
    assert bookpipe.validate(BOOK, root) == []


def test_chapter_count_mismatch(tmp_path):
    root = make_tree(tmp_path, [BODY, BODY + "二"])
    issues = bookpipe.validate(BOOK, root)
    assert any(i.startswith("#1") for i in issues)


def test_residual_wikitext_is_caught(tmp_path):
    root = make_tree(tmp_path, [BODY + " {{残}}", BODY + "二", BODY + "三"])
    issues = bookpipe.validate(BOOK, root)
    assert any("#3" in i for i in issues)


def test_verse_colon_leftover_is_caught(tmp_path):
    root = make_tree(tmp_path, [BODY + "\n:詩句未清", BODY + "二", BODY + "三"])
    issues = bookpipe.validate(BOOK, root)
    assert any("starts with ':'" in i for i in issues)


def test_duplicate_bodies_are_caught(tmp_path):
    root = make_tree(tmp_path, [BODY, BODY, BODY + "三"])
    issues = bookpipe.validate(BOOK, root)
    assert any("#8" in i for i in issues)


def test_empty_heading_is_caught(tmp_path):
    root = make_tree(tmp_path, [BODY, BODY + "二", BODY + "三"], headings=["", "b", "c"])
    issues = bookpipe.validate(BOOK, root)
    assert any("#2" in i for i in issues)


def test_index_links_must_resolve(tmp_path):
    root = make_tree(tmp_path, [BODY, BODY + "二", BODY + "三"], index_links=2)
    issues = bookpipe.validate(BOOK, root)
    assert any("#10" in i for i in issues)


def test_doubled_chapter_prefix_is_caught(tmp_path):
    root = make_tree(tmp_path, [BODY, BODY + "二", BODY + "三"],
                     headings=["第001回 楔子", "b", "c"])
    issues = bookpipe.validate(BOOK, root)
    assert any("repeats the chapter number" in i for i in issues)


def test_short_chapter_is_caught(tmp_path):
    root = make_tree(tmp_path, ["短", BODY + "二", BODY + "三"])
    issues = bookpipe.validate(BOOK, root)
    assert any("#4" in i for i in issues)


def test_missing_meta_is_caught(tmp_path):
    root = make_tree(tmp_path, [BODY, BODY + "二", BODY + "三"])
    (root / ".meta.json").unlink()
    issues = bookpipe.validate(BOOK, root)
    assert any("#9" in i for i in issues)


def test_promote_replaces_target(tmp_path, monkeypatch):
    monkeypatch.setattr(bookpipe, "CONTENT", tmp_path)
    monkeypatch.setattr(bookpipe, "STAGING", tmp_path / ".staging")
    staging = tmp_path / ".staging" / "demo"
    staging.mkdir(parents=True)
    (staging / "new.txt").write_text("new", encoding="utf-8")
    target = tmp_path / "fiction" / "demo"
    target.mkdir(parents=True)
    (target / "old.txt").write_text("old", encoding="utf-8")

    out = bookpipe.promote(BOOK, staging)
    assert out == target
    assert (target / "new.txt").exists()
    assert not (target / "old.txt").exists()
    assert not staging.exists()


def test_limit_never_promotes(tmp_path, monkeypatch):
    monkeypatch.setattr(bookpipe, "CONTENT", tmp_path)
    monkeypatch.setattr(bookpipe, "STAGING", tmp_path / ".staging")
    monkeypatch.setattr(bookpipe, "fetch", lambda book, limit=0: [
        (1, "第一回 甲", BODY), (2, "第二回 乙", BODY + "二")][: limit or 2])
    rc = bookpipe.cmd_ingest(BOOK, dry_run=False, limit=2)
    assert rc == 0
    assert (tmp_path / ".staging" / "demo").exists()
    assert not (tmp_path / "fiction" / "demo").exists()


def test_failed_validation_writes_report_and_keeps_content(tmp_path, monkeypatch):
    monkeypatch.setattr(bookpipe, "CONTENT", tmp_path)
    monkeypatch.setattr(bookpipe, "STAGING", tmp_path / ".staging")
    monkeypatch.setattr(bookpipe, "fetch", lambda book, limit=0: [(1, "只一回", BODY)])
    rc = bookpipe.cmd_ingest(BOOK, dry_run=False, limit=0)
    assert rc == 1
    assert (tmp_path / ".staging" / "demo" / "REPORT.md").exists()
    assert not (tmp_path / "fiction" / "demo").exists()


def test_registry_parses_shipped_books():
    books = bookpipe.load_registry()
    assert {"xiyouji", "republic"}.issubset(books)
    assert books["xiyouji"]["chapter_total"] == 100
    assert books["republic"]["source"] == "gutenberg"


@pytest.mark.parametrize("raw,profile,expected", [
    ("{{header\n| title = X\n| section = 第七十五回<br>心猿鑽透陰陽體\u3000魔{{另|主|王}}還歸大道真\n| author = 吳\n}}",
     "wikisource-header", "心猿鑽透陰陽體 魔主還歸大道真"),
    ("{{Novel|書名|第一回 回目示例|}}", "wikisource-novel", "回目示例"),
])
def test_title_extraction(raw, profile, expected):
    assert bookpipe.wikisource_title(raw, profile) == expected


def test_unknown_profile_is_a_hard_error():
    with pytest.raises(SystemExit):
        bookpipe.wikisource_title("{{header|x}}", "nope")


def test_verse_block_keeps_line_breaks():
    body = bookpipe.wikitext_body("{{header|x}}\n詩曰：\n:一句詩。\n:二句詩。\n\n正文段落。")
    assert "\u3000\u3000詩曰：" in body
    assert "\u3000\u3000一句詩。" in body
    assert ":" not in body
