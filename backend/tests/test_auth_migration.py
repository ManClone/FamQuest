"""Validate the independent auth schema without touching the legacy DB."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.auth_registry import AuthBase


def test_auth_migration_on_isolated_sqlite_database(tmp_path: Path):
    database_path = tmp_path / "auth_registry.sqlite"
    url = f"sqlite:///{database_path}"
    config = Config(Path(__file__).resolve().parents[1] / "auth_alembic.ini")
    config.attributes["database_url"] = url
    command.upgrade(config, "head")
    engine = create_engine(url)
    try:
        tables = set(inspect(engine).get_table_names())
        assert tables == set(AuthBase.metadata.tables) | {"alembic_version"}
        assert "users" not in tables
        assert "tasks" not in tables
        command.downgrade(config, "base")
        assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    finally:
        engine.dispose()
