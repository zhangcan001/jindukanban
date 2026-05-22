from functools import lru_cache
import json
from typing import Annotated, Any

from pydantic import Field, field_validator
from pydantic.aliases import AliasChoices
from pydantic_settings import NoDecode
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "progress-dashboard"
    app_env: str = "development"
    api_prefix: str = "/api"
    database_url: str = "sqlite:///./progress_dashboard.db"
    upload_dir: str = "uploads"
    export_dir: str = "reports"
    backup_dir: str = "backups"
    max_upload_size_mb: int = 20
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5193",
            "http://127.0.0.1:5193",
            "http://localhost:5194",
            "http://127.0.0.1:5194",
        ],
        validation_alias=AliasChoices("BACKEND_CORS_ORIGINS", "CORS_ORIGINS"),
    )
    log_level: str = "INFO"
    log_format: str = "json"
    """日志格式:"json" 每条一行结构化 JSON(带 request_id,便于排查),"text" 传统可读格式。"""

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        text = str(value).strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = [part.strip() for part in text.split(",")]
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
        return [str(parsed).strip()]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
