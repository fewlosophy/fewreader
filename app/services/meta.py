from __future__ import annotations

import json
import time
from pathlib import Path

CACHE_TTL_SECONDS = 10.0
META_FILENAME = ".meta.json"
_meta_cache: dict[str, tuple[float, dict | None]] = {}

# Keys the reader understands. Extra keys in .meta.json are silently ignored.
KNOWN_KEYS = ("title", "author", "translator", "year", "source", "source_url", "description")


def clear_meta_cache() -> None:
    _meta_cache.clear()


def load_meta(content_dir: Path | str, folder_path: str) -> dict | None:
    """Read the .meta.json for *folder_path* (relative to *content_dir*).

    Returns a dict restricted to known keys, or None if the folder has no
    .meta.json / it is unreadable / not a dict. Cached by absolute folder path
    for CACHE_TTL_SECONDS.
    """
    base = Path(content_dir).resolve()
    folder = (base / folder_path).resolve()
    if not folder.is_relative_to(base):
        return None
    key = str(folder)
    now = time.time()
    hit = _meta_cache.get(key)
    if hit and now - hit[0] < CACHE_TTL_SECONDS:
        return hit[1]

    result: dict | None = None
    meta_path = folder / META_FILENAME
    try:
        if folder.is_dir() and meta_path.is_file():
            with meta_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                result = {k: data[k] for k in KNOWN_KEYS if k in data} or None
    except (OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError):
        result = None

    _meta_cache[key] = (now, result)
    return result
