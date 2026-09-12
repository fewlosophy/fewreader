from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
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
app.add_middleware(GZipMiddleware, minimum_size=500)

# Static files
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Jinja2 templates — store on app.state so routers can access via request
app.state.templates = Jinja2Templates(directory=str(BASE_DIR / "app/templates"))


# PWA Root Routes
@app.get("/sw.js", include_in_schema=False)
def service_worker():
    return FileResponse(
        BASE_DIR / "static/sw.js",
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/"},
    )


@app.get("/manifest.webmanifest", include_in_schema=False)
@app.get("/manifest.json", include_in_schema=False)
def web_manifest():
    return FileResponse(
        BASE_DIR / "static/manifest.webmanifest",
        media_type="application/manifest+json",
    )


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(
        BASE_DIR / "static/icons/icon-192.png",
        media_type="image/png",
    )


# Routers
app.include_router(library.router)
app.include_router(reader.router)

