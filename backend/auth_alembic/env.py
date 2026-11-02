"""Independent Alembic history for the central auth database."""

from alembic import context
from sqlalchemy import create_engine

from app.auth_registry import AuthBase
from app.config import get_settings

config = context.config
target_metadata = AuthBase.metadata


def database_url():
    return config.attributes.get("database_url") or get_settings().database_url("famquest_auth")


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(database_url())
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
