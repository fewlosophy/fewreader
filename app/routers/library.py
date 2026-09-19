from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.services.scanner import scan_tree, find_subtree

router = APIRouter()


def _get_templates(request: Request) -> Jinja2Templates:
    """
    Retrieve the Jinja2Templates instance from the application state.

    Args:
        request (Request): The incoming FastAPI request.

    Returns:
        Jinja2Templates: The template engine instance.
    """
    return request.app.state.templates


@router.get("/", response_class=HTMLResponse)
def library_root(request: Request) -> HTMLResponse:
    """
    Render the root library view showing all top-level content.

    Args:
        request (Request): The incoming FastAPI request.

    Returns:
        HTMLResponse: The rendered library HTML page.
    """
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
def library_category(request: Request, cat_path: str) -> HTMLResponse:
    """
    Render the library view for a specific category sub-path.

    Args:
        request (Request): The incoming FastAPI request.
        cat_path (str): The relative path of the category to display.

    Returns:
        HTMLResponse: The rendered library HTML page for the category.
    """
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
