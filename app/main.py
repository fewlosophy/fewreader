from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.routers import library, reader

BASE_DIR = Path(__file__).resolve().parent.parent

# Resolve BOOKS_DIR relative to BASE_DIR if not absolute
if not Path(settings.BOOKS_DIR).is_absolute():
    settings.BOOKS_DIR = (BASE_DIR / settings.BOOKS_DIR).resolve()
else:
    settings.BOOKS_DIR = Path(settings.BOOKS_DIR).resolve()

app = FastAPI(title=settings.APP_TITLE)

# Static files
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Jinja2 templates — store on app.state so routers can access via request
app.state.templates = Jinja2Templates(directory=str(BASE_DIR / "app/templates"))

# Routers
app.include_router(library.router)
app.include_router(reader.router)
