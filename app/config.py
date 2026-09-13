from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    CONTENT_DIR: Path | None = None
    BOOKS_DIR: Path | None = None
    APP_TITLE: str = "ReadLite"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    def model_post_init(self, __context, /) -> None:
        target = self.CONTENT_DIR or self.BOOKS_DIR
        if target is None:
            target = Path("content") if Path("content").exists() or not Path("books").exists() else Path("books")
        self.CONTENT_DIR = Path(target)
        self.BOOKS_DIR = Path(target)


settings = Settings()
