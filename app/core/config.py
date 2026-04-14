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
    tts_openai_model: str = "gpt-4o-mini-tts"
    tts_timeout_seconds: float = 8.0
    tts_retry_count: int = 1
    tts_max_chars: int = 2000
    tts_chunk_chars: int = 500
    tts_rate_limit_per_minute: int = 20
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

    @field_validator("tts_openai_model", mode="before")
    @classmethod
    def normalize_tts_openai_model(cls, value: str) -> str:
        return value.strip() if value else "gpt-4o-mini-tts"

    @model_validator(mode="after")
    def validate_prod_settings(self) -> "Settings":
        if self.env == "prod" and not self.secret_key:
            raise ValueError("SECRET_KEY must be set when ENV=prod")
        if self.tts_timeout_seconds <= 0:
            raise ValueError("TTS_TIMEOUT_SECONDS must be greater than 0")
        if self.tts_retry_count < 0:
            raise ValueError("TTS_RETRY_COUNT must be greater than or equal to 0")
        if self.tts_max_chars <= 0:
            raise ValueError("TTS_MAX_CHARS must be greater than 0")
        if self.tts_chunk_chars <= 0:
            raise ValueError("TTS_CHUNK_CHARS must be greater than 0")
        if self.tts_chunk_chars > self.tts_max_chars:
            raise ValueError("TTS_CHUNK_CHARS must be less than or equal to TTS_MAX_CHARS")
        if self.tts_rate_limit_per_minute <= 0:
            raise ValueError("TTS_RATE_LIMIT_PER_MINUTE must be greater than 0")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
