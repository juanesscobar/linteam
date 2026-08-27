from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="LINTEAM_", extra="ignore")

    environment: Literal["development", "test", "staging", "production"] = "development"
    database_url: str = "sqlite:///./linteam.db"
    secret_key: str = "development-only-secret-key-change-me"
    bootstrap_token: str = "development-bootstrap-token"
    access_token_minutes: int = Field(default=15, ge=5, le=60)
    refresh_token_days: int = Field(default=14, ge=1, le=90)
    allowed_origins: list[str] = ["http://localhost:3000"]
    trusted_hosts: list[str] = ["localhost", "127.0.0.1", "testserver"]
    rate_limit_per_minute: int = Field(default=120, ge=10, le=10_000)
    file_storage_path: str = "./data/files"
    max_upload_bytes: int = Field(default=10_485_760, ge=1024, le=104_857_600)
    webhook_secret: str = "development-webhook-secret"
    webhook_tolerance_seconds: int = Field(default=300, ge=30, le=3600)

    @model_validator(mode="after")
    def reject_unsafe_production_settings(self) -> "Settings":
        if self.environment in {"staging", "production"}:
            if self.secret_key == "development-only-secret-key-change-me":
                raise ValueError("A unique LINTEAM_SECRET_KEY is required outside development")
            if self.database_url.startswith("sqlite"):
                raise ValueError("PostgreSQL is required outside development")
            if self.bootstrap_token == "development-bootstrap-token":
                raise ValueError("A unique LINTEAM_BOOTSTRAP_TOKEN is required")
            if self.webhook_secret == "development-webhook-secret":
                raise ValueError("A unique LINTEAM_WEBHOOK_SECRET is required")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
