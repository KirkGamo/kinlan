"""Server settings, read from environment variables (or a local .env file)."""

from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "change-me-in-.env"
MIN_SECRET_LENGTH = 32


class Settings(BaseSettings):
    """All configuration comes from the environment; see server/.env.example."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"
    database_url: str = "postgresql+psycopg://postgres@localhost:5433/kinlan_dev"
    # Neon: DATABASE_URL is the pooled string (host has "-pooler") for the app; migrations use
    # the direct string, because PgBouncer's transaction mode breaks session-level work.
    database_url_unpooled: str | None = None
    jwt_secret: str = DEV_JWT_SECRET
    cors_origins: list[str] = ["http://localhost:8081"]
    expo_access_token: str | None = None
    run_jobs: bool = True  # scheduled jobs; set RUN_JOBS=false on extra instances

    @field_validator("database_url", "database_url_unpooled")
    @classmethod
    def _psycopg_driver(cls, v: str | None) -> str | None:
        """Accept connection strings exactly as Neon shows them (postgresql://…?sslmode=…)."""
        if v is None:
            return None
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix) :]
        return v

    @model_validator(mode="after")
    def _real_secret_in_production(self) -> "Settings":
        """JWT_SECRET signs every token and keys the code hashes: refuse to run on the default."""
        weak = self.jwt_secret == DEV_JWT_SECRET or len(self.jwt_secret) < MIN_SECRET_LENGTH
        if self.env == "production" and weak:
            raise ValueError(
                f"Set JWT_SECRET to a random value of at least {MIN_SECRET_LENGTH} characters."
            )
        return self

    @property
    def migration_url(self) -> str:
        return self.database_url_unpooled or self.database_url

    @property
    def pooled(self) -> bool:
        return "-pooler" in self.database_url


@lru_cache
def get_settings() -> Settings:
    """Return the settings, loaded once per process."""
    return Settings()
