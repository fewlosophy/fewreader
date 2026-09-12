"""
Integration tests for HTTP routes.

Uses a TestClient with BOOKS_DIR patched to a known temp directory
(defined in conftest.py).
"""
import pytest


# ── Library routes ─────────────────────────────────────────────────────────

def test_library_root_returns_200(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_library_root_is_html(client):
    resp = client.get("/")
    assert "text/html" in resp.headers["content-type"]


def test_library_root_lists_books(client):
    resp = client.get("/")
    assert "Welcome" in resp.text or "welcome" in resp.text


def test_library_root_lists_categories(client):
    resp = client.get("/")
    assert "fiction" in resp.text.lower()


def test_library_category_returns_200(client):
    resp = client.get("/library/fiction")
    assert resp.status_code == 200


def test_library_category_nonexistent_still_200(client):
    # Non-existent categories render an empty library view — not a 404
    resp = client.get("/library/does_not_exist")
    assert resp.status_code == 200


# ── Reader routes ──────────────────────────────────────────────────────────

def test_read_markdown_returns_200(client):
    resp = client.get("/read/welcome.md")
    assert resp.status_code == 200


def test_read_markdown_contains_rendered_html(client):
    resp = client.get("/read/welcome.md")
    assert "<h1" in resp.text or "<h2" in resp.text
    assert "Welcome" in resp.text


def test_read_markdown_contains_toc(client):
    # welcome.md has headings, so the TOC sidebar should appear
    resp = client.get("/read/welcome.md")
    assert "toc" in resp.text.lower() or "contents" in resp.text.lower()


def test_read_txt_returns_200(client):
    resp = client.get("/read/notes.txt")
    assert resp.status_code == 200


def test_read_txt_contains_paragraphs(client):
    resp = client.get("/read/notes.txt")
    assert "<p>" in resp.text
    assert "First paragraph" in resp.text


def test_read_nested_file_returns_200(client):
    resp = client.get("/read/fiction/story.txt")
    assert resp.status_code == 200


def test_read_nested_file_contains_content(client):
    resp = client.get("/read/fiction/story.txt")
    assert "Once upon a time" in resp.text


def test_read_nonexistent_file_returns_404(client):
    resp = client.get("/read/ghost.md")
    assert resp.status_code == 404


def test_read_path_traversal_returns_404(client):
    resp = client.get("/read/../../etc/passwd")
    assert resp.status_code == 404


def test_read_unsupported_extension_returns_404(client):
    resp = client.get("/read/data.json")
    assert resp.status_code == 404


# ── Static assets ──────────────────────────────────────────────────────────

def test_static_css_returns_200(client):
    resp = client.get("/static/custom.css")
    assert resp.status_code == 200


def test_static_css_is_css(client):
    resp = client.get("/static/custom.css")
    assert "text/css" in resp.headers["content-type"]
