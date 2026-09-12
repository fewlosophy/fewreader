from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    BOOKS_DIR: Path = Path("books")
    APP_TITLE: str = "ReadLite"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
