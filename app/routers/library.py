from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.services.scanner import scan_tree, find_subtree

router = APIRouter()


def _get_templates(request: Request) -> Jinja2Templates:
    return request.app.state.templates


@router.get("/", response_class=HTMLResponse)
def library_root(request: Request):
    content_dir = settings.CONTENT_DIR or settings.BOOKS_DIR
    tree = scan_tree(content_dir)
    templates = _get_templates(request)
    return templates.TemplateResponse(
        request,
        "library.html",
        {
            "tree": tree,
            "visible_items": tree,
            "current_path": "",
            "app_title": settings.APP_TITLE,
        },
    )


@router.get("/library/{cat_path:path}", response_class=HTMLResponse)
def library_category(request: Request, cat_path: str):
    content_dir = settings.CONTENT_DIR or settings.BOOKS_DIR
    tree = scan_tree(content_dir)
    visible = find_subtree(tree, cat_path)
    templates = _get_templates(request)
    return templates.TemplateResponse(
        request,
        "library.html",
        {
            "tree": tree,
            "visible_items": visible,
            "current_path": cat_path,
            "app_title": settings.APP_TITLE,
        },
    )
