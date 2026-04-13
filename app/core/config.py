from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    env: str = "local"
    app_name: str = "philosopher-server"
    api_v1_prefix: str = "/api/v1"
    secret_key: str = ""
    database_url: str | None = None
    cors_origins: list[str] = []

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, list):
            return value
        if not value:
            return []
        return [origin.strip() for origin in value.split(",") if origin.strip()]

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
        return cleaned or None

    @model_validator(mode="after")
    def validate_prod_settings(self) -> "Settings":
        if self.env == "prod" and not self.secret_key:
            raise ValueError("SECRET_KEY must be set when ENV=prod")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
