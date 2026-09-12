# ReadLite

A clean, self-hosted web app for reading `.md` and `.txt` files in your browser.

## Quick Start (Docker)

Run with Docker Compose:

```bash
docker compose up -d
```

Or build and run with Docker directly:

```bash
docker build -t readlite .
docker run -d -p 8000:8000 -v $(pwd)/books:/app/books:ro --name readlite readlite
```

Then open **http://localhost:8000** in your browser.

## Local Setup (Python)

```bash
# Install dependencies
pip install -r requirements.txt

# Run the development server
uvicorn app.main:app --reload --port 8000
```

## Adding Books

Drop `.md` or `.txt` files into the `books/` directory. Sub-folders become categories:

```
books/
├── fiction/
│   └── my_story.txt
├── notes/
│   └── ideas.md
└── welcome.md
```

Changes are picked up automatically — no restart needed.

## Configuration

| Environment variable | Default | Description |
|---|---|---|
| `BOOKS_DIR` | `books` | Path to the books directory |
| `APP_TITLE` | `ReadLite` | Site title shown in the nav |

## Stack

- **FastAPI** — routing
- **Jinja2** — server-side rendering
- **python-markdown** — CommonMark conversion
- **Tailwind CSS** — styling (CDN)
