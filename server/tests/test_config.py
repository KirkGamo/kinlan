"""Settings accept Neon's connection strings as shown and pick the right one for each job."""

from app.config import Settings

NEON_POOLED = "postgresql://kinlan_owner:pw@ep-cool-name-a1b2-pooler.ap-southeast-1.aws.neon.tech/kinlan?sslmode=require&channel_binding=require"
NEON_DIRECT = NEON_POOLED.replace("-pooler", "")


def test_neon_strings_get_the_psycopg_driver_and_keep_ssl():
    s = Settings(database_url=NEON_POOLED, database_url_unpooled=NEON_DIRECT, _env_file=None)
    assert s.database_url.startswith("postgresql+psycopg://kinlan_owner:pw@ep-cool-name")
    assert s.database_url.endswith("sslmode=require&channel_binding=require")
    assert s.pooled and "-pooler" not in s.migration_url


def test_migrations_fall_back_to_the_main_url_locally():
    local = "postgresql+psycopg://postgres:pw@localhost:5433/kinlan_dev"
    s = Settings(database_url=local, _env_file=None)
    assert s.migration_url == local and not s.pooled


def test_postgres_scheme_alias_is_accepted():
    s = Settings(database_url="postgres://u:p@h/db", _env_file=None)
    assert s.database_url == "postgresql+psycopg://u:p@h/db"
