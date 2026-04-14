import json
from functools import lru_cache
from typing import Annotated

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    env: str = "local"
    app_name: str = "philosopher-server"
    api_v1_prefix: str = "/api/v1"
    secret_key: str = ""
    database_url: str | None = None
    supabase_url: str | None = None
    supabase_jwt_audience: str = "authenticated"
    supabase_jwt_secret: str | None = None
    openai_api_key: str | None = None
    cors_origins: Annotated[list[str], NoDecode] = []

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str] | None) -> list[str]:
        if isinstance(value, list):
            return value
        if not value:
            return []
        cleaned = value.strip()
        if not cleaned:
            return []
        if cleaned.startswith("["):
            try:
                parsed = json.loads(cleaned)
                if isinstance(parsed, list):
                    return [str(origin).strip() for origin in parsed if str(origin).strip()]
            except json.JSONDecodeError:
                # Fallback to CSV parsing below for malformed JSON-like input.
                pass
        return [origin.strip() for origin in cleaned.split(",") if origin.strip()]

    @field_validator("secret_key", mode="before")
    @classmethod
    def normalize_secret_key(cls, value: str) -> str:
        return value.strip() if value else ""

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if cleaned.startswith("postgresql://"):
            cleaned = cleaned.replace("postgresql://", "postgresql+psycopg://", 1)
        return cleaned or None

    @field_validator("supabase_url", mode="before")
    @classmethod
    def normalize_supabase_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().rstrip("/")
        return cleaned or None

    @field_validator("supabase_jwt_secret", mode="before")
    @classmethod
    def normalize_supabase_jwt_secret(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("openai_api_key", mode="before")
    @classmethod
    def normalize_openai_api_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @model_validator(mode="after")
    def validate_prod_settings(self) -> "Settings":
        if self.env == "prod" and not self.secret_key:
            raise ValueError("SECRET_KEY must be set when ENV=prod")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
