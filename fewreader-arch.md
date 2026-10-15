# Fewreader Architecture

Fewreader is a self-hosted reading app built with FastAPI, Jinja2, and Tailwind CSS.
It follows a simple and minimalist design for rendering local Markdown and Text files.

## Routing Architecture

- **`app/routers/library.py`**:
  - `GET /`: Renders the root library view.
  - `GET /library/{cat_path}`: Renders a specific category sub-path view.
- **`app/routers/reader.py`**:
  - `GET /read/{file_path}`: Reads, converts, and renders text/markdown content. Handles breadcrumb generation and sibling navigation.

## Service Layers

- **`app/services/scanner.py`**:
  - Handles reading the filesystem tree, parsing Chinese chapter numerals, and generating sort keys.
  - Generates navigation structures and finds siblings.
  - Uses an in-memory cache to speed up filesystem traversal.
- **`app/services/converter.py`**:
  - Converts plain text and markdown to HTML.
  - Handles markdown extensions (TOC, tables, footnotes, etc.).
  - Incorporates automatic encoding fallbacks.
  - Uses `functools.lru_cache` for fast repetitive file reads.

## Configuration

- **`app/config.py`**:
  - Loads settings from environment variables or `.env` files using Pydantic `BaseSettings`.
  - Dynamically selects content directories (e.g., `content/` or `books/`).
