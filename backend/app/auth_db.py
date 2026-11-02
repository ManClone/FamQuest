"""Central auth DB engine (opt-in, no legacy routing changes)."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings


class AuthDatabase:
    def __init__(self, settings: Settings | None = None) -> None:
        settings = settings or get_settings()
        # Fail closed: central identities must not use the legacy database login.
        credentials = settings.auth_database_credentials
        if credentials is None or credentials.username != "famquest_auth_app":
            raise PermissionError("Dedicated auth database credentials are required")
        self.engine: Engine = create_engine(
            settings.database_url("famquest_auth").set(
                username=credentials.username, password=credentials.password
            ),
            pool_pre_ping=True,
        )
        self._sessions = sessionmaker(bind=self.engine, expire_on_commit=False)

    @contextmanager
    def session(self) -> Iterator[Session]:
        with self._sessions() as session:
            yield session

    def close(self) -> None:
        self.engine.dispose()
