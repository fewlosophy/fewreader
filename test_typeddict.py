from __future__ import annotations
from typing import TypedDict, Literal

class BookFile(TypedDict):
    type: Literal["file"]

class BookCategory(TypedDict):
    type: Literal["category"]
    children: list[BookFile | BookCategory]
