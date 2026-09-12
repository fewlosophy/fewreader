from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.services.scanner import scan_tree, resolve_file
from app.services.converter import convert

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
        crumbs.append(
            {
                "label": part.replace("-", " ").replace("_", " ").title(),
                "path": accumulated,
                "is_last": is_last,
            }
        )
    return crumbs


@router.get("/read/{file_path:path}", response_class=HTMLResponse)
async def read_file(request: Request, file_path: str):
    # Resolve and guard against path traversal
    try:
        abs_path = resolve_file(file_path, settings.BOOKS_DIR)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    # Convert content
    try:
        html_content, toc_html = convert(abs_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Conversion error: {exc}")

    # Derive title from filename stem
    title = (
        abs_path.stem.replace("-", " ").replace("_", " ").title()
    )

    tree = scan_tree(settings.BOOKS_DIR)
    templates = _get_templates(request)

    return templates.TemplateResponse(
        "reader.html",
        {
            "request": request,
            "content": html_content,
            "toc": toc_html,
            "title": title,
            "file_path": file_path,
            "breadcrumb": _breadcrumb(file_path),
            "tree": tree,
            "app_title": settings.APP_TITLE,
        },
    )
