"""
Shared fixtures for all test modules.
"""
import pytest
from pathlib import Path
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def app():
    """Import the FastAPI app once per session."""
    from app.main import app as fastapi_app
    return fastapi_app


@pytest.fixture(autouse=True)
def reset_caches():
    """Clear in-memory caches before and after each test."""
    from app.services.scanner import clear_scanner_cache
    from app.services.converter import clear_converter_cache
    clear_scanner_cache()
    clear_converter_cache()
    yield
    clear_scanner_cache()
    clear_converter_cache()


@pytest.fixture
def books_dir(tmp_path: Path) -> Path:
    """
    A self-contained temp books directory with a known structure:

        tmp/
        ├── welcome.md          (has headings → TOC)
        ├── notes.txt           (plain text, two paragraphs)
        ├── fiction/
        │   └── story.txt
        ├── .hidden.md          (must be ignored)
        ├── .hidden_dir/
        │   └── file.md         (must be ignored)
        └── data.json           (unsupported extension, must be ignored)
    """
    (tmp_path / "welcome.md").write_text(
        "# Welcome\n\n## Section One\n\nHello world.\n\n## Section Two\n\nGoodbye.\n",
        encoding="utf-8",
    )
    (tmp_path / "notes.txt").write_text(
        "First paragraph here.\n\nSecond paragraph here.",
        encoding="utf-8",
    )

    fiction = tmp_path / "fiction"
    fiction.mkdir()
    (fiction / "story.txt").write_text(
        "Once upon a time.\n\nThe end.",
        encoding="utf-8",
    )

    # Should be ignored
    (tmp_path / ".hidden.md").write_text("# Hidden", encoding="utf-8")
    hidden_dir = tmp_path / ".hidden_dir"
    hidden_dir.mkdir()
    (hidden_dir / "file.md").write_text("# In hidden dir", encoding="utf-8")
    (tmp_path / "data.json").write_text("{}", encoding="utf-8")

    return tmp_path


@pytest.fixture
def client(app, books_dir: Path, monkeypatch) -> TestClient:
    """
    A test HTTP client with BOOKS_DIR monkeypatched to *books_dir*.
    Route handlers read settings.BOOKS_DIR at request time, so patching
    before the first request is sufficient.
    """
    from app.config import settings
    monkeypatch.setattr(settings, "BOOKS_DIR", books_dir)
    with TestClient(app) as c:
        yield c
