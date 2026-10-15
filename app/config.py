from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Any

class Settings(BaseSettings):
    """
    Application settings and configuration management.

    Attributes:
        CONTENT_DIR (Path | None): The primary directory containing content files.
        BOOKS_DIR (Path | None): Legacy support for the content directory.
        APP_TITLE (str): The display title for the application.
    """
    CONTENT_DIR: Path | None = None
    BOOKS_DIR: Path | None = None
    APP_TITLE: str = "Fewreader"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    def model_post_init(self, __context: Any) -> None:
        """
        Post-initialization hook to resolve the content directory.

        Args:
            __context (Any): Pydantic validation context.
        """
        target = self.CONTENT_DIR or self.BOOKS_DIR
        if target is None:
            target = Path("content") if Path("content").exists() or not Path("books").exists() else Path("books")
        self.CONTENT_DIR = Path(target)
        self.BOOKS_DIR = Path(target)


settings = Settings()
