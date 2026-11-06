"""Server settings, read from environment variables (or a local .env file)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from the environment; see server/.env.example."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"
    database_url: str = "postgresql+psycopg://postgres@localhost:5433/kinlan_dev"
    jwt_secret: str = "change-me-in-.env"
    cors_origins: list[str] = ["http://localhost:8081"]
    expo_access_token: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Return the settings, loaded once per process."""
    return Settings()
