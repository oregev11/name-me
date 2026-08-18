"""Application configuration, read from environment variables / .env."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Comma-separated list of allowed CORS origins, e.g.
    # "http://localhost:5173,https://name-me.vercel.app"
    # Both localhost and 127.0.0.1 are included by default since Vite's dev
    # server is commonly reached via either, and browsers treat them as
    # distinct origins.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


def get_settings() -> Settings:
    return Settings()
