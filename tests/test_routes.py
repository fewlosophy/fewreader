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


def test_read_breadcrumb_strips_file_extension(client):
    resp = client.get("/read/welcome.md")
    assert resp.status_code == 200
    # Last breadcrumb should display 'Welcome', not 'Welcome.Md'
    assert "Welcome.Md" not in resp.text
    assert "Welcome.md" not in resp.text


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


def test_static_tailwind_css_returns_200(client):
    resp = client.get("/static/tailwind.min.css")
    assert resp.status_code == 200
    assert "text/css" in resp.headers["content-type"]


def test_no_external_render_blocking_cdns(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "cdn.tailwindcss.com" not in resp.text
    assert "fonts.googleapis.com" not in resp.text
    assert "fonts.gstatic.com" not in resp.text


def test_gzip_compression_enabled(client):
    resp = client.get("/", headers={"Accept-Encoding": "gzip"})
    assert resp.status_code == 200
    assert resp.headers.get("content-encoding") == "gzip"


def test_html_head_structure_and_no_leaked_js(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "</head>" in resp.text
    head_content = resp.text.split("</head>")[0]
    assert '<link rel="stylesheet" href="/static/tailwind.min.css"' in head_content
    assert '<link rel="stylesheet" href="/static/custom.css"' in head_content
    assert "/static/base.js" in head_content


def test_code_block_theme_styling_in_custom_css(client):
    resp = client.get("/static/custom.css")
    assert resp.status_code == 200
    # Must not contain hardcoded dark background for light mode
    assert "background: #16181d !important;" not in resp.text
    # Must use design tokens for light and dark modes
    assert ".prose pre" in resp.text
    assert "var(--color-surface)" in resp.text
    assert "var(--color-text-primary)" in resp.text


def test_reader_font_size_uses_rem(client):
    resp = client.get("/static/base.js")
    assert resp.status_code == 200
    assert "'1rem', '1.0625rem', '1.125rem'" in resp.text
    css_resp = client.get("/static/custom.css")
    assert "--reader-font-size: 1.125rem;" in css_resp.text





# ── PWA routes ─────────────────────────────────────────────────────────────

def test_service_worker_route(client):
    resp = client.get("/sw.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers["content-type"]
    assert resp.headers.get("service-worker-allowed") == "/"
    assert "fewreader-pwa" in resp.text


def test_manifest_webmanifest_route(client):
    resp = client.get("/manifest.webmanifest")
    assert resp.status_code == 200
    assert "json" in resp.headers["content-type"]
    data = resp.json()
    assert data["name"] == "Fewreader"
    assert data["display"] == "standalone"
    assert data["start_url"] == "/"
    assert len(data["icons"]) >= 2


def test_manifest_json_alias(client):
    resp = client.get("/manifest.json")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Fewreader"


def test_favicon_route(client):
    resp = client.get("/favicon.ico")
    assert resp.status_code == 200
    assert "image/png" in resp.headers["content-type"]


def test_pwa_head_tags_rendered_in_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert '<link rel="manifest" href="/manifest.webmanifest"' in resp.text
    assert '<meta name="theme-color"' in resp.text
    assert "navigator.serviceWorker.register('/sw.js'" in resp.text


def test_reader_mobile_layout_and_anchor_guards(client):
    resp = client.get("/read/welcome.md")
    assert resp.status_code == 200
    assert 'id="main-wrapper"' in resp.text
    assert 'id="toc-drawer"' in resp.text

    # Check external js inclusions
    js_resp = client.get("/static/reader.js")
    assert "initAnchorNavigation" in js_resp.text
    base_js_resp = client.get("/static/base.js")
    assert "preventViewportScroll" in base_js_resp.text


def test_chapter_navigation_svg_dimensions(client):
    # Ensure chapter nav SVG icons don't use uncompiled classes like w-4.5
    resp = client.get("/read/welcome.md")
    assert resp.status_code == 200
    assert "w-4.5" not in resp.text
    assert "h-4.5" not in resp.text



