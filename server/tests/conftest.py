"""Test setup: every run rebuilds kinlan_test from the Alembic migrations, so they're tested too.

Locally the test URL is the DATABASE_URL from server/.env with the database name swapped to
kinlan_test. In CI, ENV=test and DATABASE_URL already points at the kinlan_test service.
"""

import os
from pathlib import Path

os.environ.setdefault("ENV", "test")  # before app imports: turns off rate limiting

import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from alembic import command  # noqa: E402
from app.config import Settings, get_settings  # noqa: E402

SERVER_DIR = Path(__file__).resolve().parents[1]


def _test_url() -> str:
    if url := os.environ.get("TEST_DATABASE_URL"):
        return url
    url = Settings().database_url
    if url.rstrip("/").endswith("/kinlan_test"):
        return url
    if "/kinlan_dev" not in url:
        pytest.exit("Set TEST_DATABASE_URL, or point DATABASE_URL at kinlan_dev in server/.env.")
    return url.replace("/kinlan_dev", "/kinlan_test")


TEST_URL = _test_url()
os.environ["DATABASE_URL"] = TEST_URL
get_settings.cache_clear()


@pytest.fixture(scope="session", autouse=True)
def _schema() -> None:
    """Drop everything, then build the schema the way production does: alembic upgrade head."""
    engine = create_engine(TEST_URL)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()
    cfg = Config(str(SERVER_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(SERVER_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", TEST_URL.replace("%", "%%"))
    command.upgrade(cfg, "head")


@pytest.fixture(autouse=True)
def _clean_tables():
    """Each test starts with empty tables."""
    yield
    from app.db import Base, get_engine

    names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with get_engine().begin() as conn:
        conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c
