from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.services.scanner import scan_tree, find_subtree

router = APIRouter()


def _get_templates(request: Request) -> Jinja2Templates:
    return request.app.state.templates


@router.get("/", response_class=HTMLResponse)
async def library_root(request: Request):
    tree = scan_tree(settings.BOOKS_DIR)
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
async def library_category(request: Request, cat_path: str):
    tree = scan_tree(settings.BOOKS_DIR)
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
