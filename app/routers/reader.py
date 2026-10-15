"""Reader router module for handling document reading endpoints."""
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.services.converter import convert
from app.services.scanner import get_sibling_files, human_title, resolve_file, scan_tree

router = APIRouter()


def _get_templates(request: Request) -> Jinja2Templates:
    return request.app.state.templates


def _breadcrumb(file_path: str) -> list[dict]:
    """Build breadcrumb segments from a relative file path string."""
    parts = file_path.split("/")
    crumbs = []
    accumulated = ""
    for i, part in enumerate(parts):
        accumulated = f"{accumulated}/{part}" if accumulated else part
        is_last = i == len(parts) - 1
        # Strip extension on the final file name crumb
        raw_label = Path(part).stem if is_last else part
        crumbs.append(
            {
                "label": human_title(raw_label),
                "path": accumulated,
                "is_last": is_last,
            }
        )
    return crumbs


@router.get("/read/{file_path:path}", response_class=HTMLResponse)
def read_file(request: Request, file_path: str):
    """Endpoint for reading a specific document file."""
    content_dir = settings.CONTENT_DIR or settings.BOOKS_DIR

    # Resolve and guard against path traversal
    try:
        abs_path = resolve_file(file_path, content_dir)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Convert content
    try:
        html_content, toc_html = convert(abs_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Conversion error: {exc}") from exc

    # Derive title from filename stem
    title = human_title(abs_path.stem)

    tree = scan_tree(content_dir)
    prev_file, next_file = get_sibling_files(file_path, content_dir, tree=tree)
    templates = _get_templates(request)

    return templates.TemplateResponse(
        request,
        "reader.html",
        {
            "content": html_content,
            "toc": toc_html,
            "has_toc": bool(toc_html and "<li>" in toc_html),
            "title": title,
            "file_path": file_path,
            "breadcrumb": _breadcrumb(file_path),
            "tree": tree,
            "prev_file": prev_file,
            "next_file": next_file,
            "app_title": settings.APP_TITLE,
        },
    )
