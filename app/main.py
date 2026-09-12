from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.routers import library, reader

# Resolve BOOKS_DIR relative to repo root (where uvicorn is launched from)
settings.BOOKS_DIR = Path(settings.BOOKS_DIR).resolve()

app = FastAPI(title=settings.APP_TITLE)

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Jinja2 templates — store on app.state so routers can access via request
app.state.templates = Jinja2Templates(directory="app/templates")

# Routers
app.include_router(library.router)
app.include_router(reader.router)
