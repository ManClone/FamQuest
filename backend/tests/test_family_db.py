"""Unit tests for the opt-in family database router; no database server needed."""

from unittest.mock import MagicMock, patch

import pytest

from app.config import Settings
from app.family_db import FamilyDatabase, FamilyDatabaseRouter


def test_router_reuses_engine_for_same_registered_family():
    router = FamilyDatabaseRouter(Settings())
    engine = MagicMock()
    with patch("app.family_db.create_engine", return_value=engine) as create:
        assert router._engine(FamilyDatabase(1, "famquest_grasser")) is engine
        assert router._engine(FamilyDatabase(1, "famquest_grasser")) is engine
    create.assert_called_once()
    router.close()
    engine.dispose.assert_called_once()


def test_router_rejects_changed_mapping_until_evicted():
    router = FamilyDatabaseRouter(Settings())
    with patch("app.family_db.create_engine", return_value=MagicMock()):
        router._engine(FamilyDatabase(1, "famquest_grasser"))
        with pytest.raises(ValueError, match="mapping changed"):
            router._engine(FamilyDatabase(1, "famquest_sertl"))
    router.close()


@pytest.mark.parametrize(
    "name",
    ["postgres", "famquest_;drop", "famquest_../x", "famquest_UPPER", "famquest_ä"],
)
def test_router_rejects_invalid_database_names(name):
    router = FamilyDatabaseRouter(Settings())
    with pytest.raises(ValueError, match="database name"):
        router._engine(FamilyDatabase(1, name))


def test_router_evict_disposes_engine():
    router = FamilyDatabaseRouter(Settings())
    engine = MagicMock()
    with patch("app.family_db.create_engine", return_value=engine) as create:
        router._engine(FamilyDatabase(2, "famquest_sertl"))
        router.evict(2)
        router._engine(FamilyDatabase(2, "famquest_sertl"))
        assert create.call_count == 2
    assert engine.dispose.call_count == 1
    router.close()
