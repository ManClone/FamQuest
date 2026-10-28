"""Opt-in database routing primitives for the future per-family deployment.

This module does not modify the legacy single-family SessionLocal or its
Alembic history. Never derive a database name from untrusted request input.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from threading import RLock

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings


@dataclass(frozen=True)
class FamilyDatabase:
    """Database registry record loaded from the authenticated control plane."""

    family_id: int
    database_name: str


class FamilyDatabaseRouter:
    """Bounded lifecycle for connections to explicitly registered family DBs.

    Registry lookups and authorization are intentionally outside this class.
    The caller must obtain FamilyDatabase from the trusted auth database.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._lock = RLock()
        self._engines: dict[int, tuple[str, Engine]] = {}

    def _engine(self, family: FamilyDatabase) -> Engine:
        if family.family_id <= 0:
            raise ValueError("Invalid family identifier")
        if not family.database_name.startswith("famquest_") or not all(
            c.isascii() and (c.islower() or c.isdigit() or c == "_")
            for c in family.database_name
        ):
            raise ValueError("Invalid registered database name")
        with self._lock:
            existing = self._engines.get(family.family_id)
            if existing is not None:
                if existing[0] != family.database_name:
                    raise ValueError("Family database mapping changed; evict first")
                return existing[1]
            engine = create_engine(
                self._settings.database_url(family.database_name),
                pool_pre_ping=True,
                pool_size=2,
                max_overflow=0,
            )
            self._engines[family.family_id] = (family.database_name, engine)
            return engine

    @contextmanager
    def session(self, family: FamilyDatabase) -> Iterator[Session]:
        factory = sessionmaker(bind=self._engine(family), expire_on_commit=False)
        with factory() as session:
            yield session

    def evict(self, family_id: int) -> None:
        """Close idle connections when a family is disabled or offboarded."""
        with self._lock:
            cached = self._engines.pop(family_id, None)
            if cached is not None:
                cached[1].dispose()

    def close(self) -> None:
        with self._lock:
            for _, engine in self._engines.values():
                engine.dispose()
            self._engines.clear()
