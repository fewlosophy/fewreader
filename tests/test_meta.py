"""
Tests for app/services/meta.py and the .meta.json rendering in library/reader
routes.
"""
import json
from pathlib import Path

from app.services.meta import load_meta, clear_meta_cache, META_FILENAME


# ── load_meta ──────────────────────────────────────────────────────────────

def test_load_meta_missing(tmp_path):
    (tmp_path / "book").mkdir()
    assert load_meta(tmp_path, "book") is None


def test_load_meta_valid(tmp_path):
    folder = tmp_path / "book"
    folder.mkdir()
    (folder / META_FILENAME).write_text(
        json.dumps({
            "title": "The Republic",
            "author": "Plato",
            "translator": "B. Jowett",
            "year": 380,
            "source": "Gutenberg #150",
            "source_url": "https://www.gutenberg.org/cache/epub/150/pg150.txt",
            "description": "Justice and the state.",
        }),
        encoding="utf-8",
    )
    meta = load_meta(tmp_path, "book")
    assert meta is not None
    assert meta["title"] == "The Republic"
    assert meta["author"] == "Plato"
    assert meta["year"] == 380


def test_load_meta_strips_unknown_keys(tmp_path):
    folder = tmp_path / "book"
    folder.mkdir()
    (folder / META_FILENAME).write_text(
        json.dumps({"title": "X", "weird_key": "ignored", "author": "Y"}),
        encoding="utf-8",
    )
    meta = load_meta(tmp_path, "book")
    assert set(meta.keys()) == {"title", "author"}


def test_load_meta_invalid_json_returns_none(tmp_path):
    folder = tmp_path / "book"
    folder.mkdir()
    (folder / META_FILENAME).write_text("not json", encoding="utf-8")
    assert load_meta(tmp_path, "book") is None


def test_load_meta_non_dict_returns_none(tmp_path):
    folder = tmp_path / "book"
    folder.mkdir()
    (folder / META_FILENAME).write_text("[1,2,3]", encoding="utf-8")
    assert load_meta(tmp_path, "book") is None


def test_load_meta_path_traversal_return_none(tmp_path):
    (tmp_path / ".secret").write_text('{"title":"x"}', encoding="utf-8")
    assert load_meta(tmp_path, "../.secret") is None
    assert load_meta(tmp_path, "..") is None


def test_load_meta_empty_folder_no_meta(tmp_path):
    (tmp_path / "book").mkdir()
    # .meta.json must be a dict, not e.g. a file or a list
    assert load_meta(tmp_path, "book") is None


def test_load_meta_cache_respected(tmp_path, monkeypatch):
    folder = tmp_path / "book"
    folder.mkdir()
    meta_file = folder / META_FILENAME
    meta_file.write_text(json.dumps({"title": "First"}), encoding="utf-8")

    first = load_meta(tmp_path, "book")
    assert first and first["title"] == "First"

    # Rewrite the file; cache should still serve "First"
    meta_file.write_text(json.dumps({"title": "Second"}), encoding="utf-8")
    cached = load_meta(tmp_path, "book")
    assert cached and cached["title"] == "First"

    clear_meta_cache()
    fresh = load_meta(tmp_path, "book")
    assert fresh and fresh["title"] == "Second"


# ── Route rendering ────────────────────────────────────────────────────────

def _seed_book_meta(tmp_path: Path, folder="fiction"):
    (tmp_path / folder).mkdir(exist_ok=True)
    (tmp_path / folder / ".meta.json").write_text(
        json.dumps({
            "title": "Demo Novel", "author": "A. Writer",
            "source": "Gutenberg", "source_url": "https://example.org/novel",
        }),
        encoding="utf-8",
    )
    (tmp_path / folder / "ch1.txt").write_text("Body of ch1.", encoding="utf-8")


def test_library_category_shows_meta_panel(client, books_dir):
    _seed_book_meta(books_dir, "fiction")
    clear_meta_cache()
    resp = client.get("/library/fiction")
    assert resp.status_code == 200
    assert "Demo Novel" in resp.text
    assert "A. Writer" in resp.text
    assert "https://example.org/novel" in resp.text


def test_library_root_without_meta_shows_no_panel(client, books_dir):
    # Root has no .meta.json, no 'fiction' folder meta either → no panel
    clear_meta_cache()
    resp = client.get("/")
    assert resp.status_code == 200
    # The provenance panel is only shown under a folder that has .meta.json
    assert "Book provenance panel" not in resp.text


def test_reader_shows_meta_strip(client, books_dir):
    _seed_book_meta(books_dir, "fiction")
    clear_meta_cache()
    resp = client.get("/read/fiction/ch1.txt")
    assert resp.status_code == 200
    assert "Demo Novel" in resp.text
    assert "A. Writer" in resp.text
    assert "Gutenberg" in resp.text
    assert "https://example.org/novel" in resp.text
