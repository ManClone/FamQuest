"""The central registry never silently reuses legacy PostgreSQL credentials."""

from unittest.mock import MagicMock, patch

import pytest

from app.auth_db import AuthDatabase
from app.config import FamilyDatabaseCredentials, Settings


def test_auth_database_requires_dedicated_login():
    with patch("app.auth_db.create_engine") as create:
        with pytest.raises(PermissionError, match="Dedicated auth"):
            AuthDatabase(Settings(auth_database_credentials=None))
        create.assert_not_called()


def test_auth_database_rejects_wrong_login():
    credentials = FamilyDatabaseCredentials(username="famquest", password="x" * 40)
    with patch("app.auth_db.create_engine") as create:
        with pytest.raises(PermissionError, match="Dedicated auth"):
            AuthDatabase(Settings(auth_database_credentials=credentials))
        create.assert_not_called()


def test_auth_database_uses_auth_only_login():
    credentials = FamilyDatabaseCredentials(username="famquest_auth_app", password="x" * 40)
    engine = MagicMock()
    with patch("app.auth_db.create_engine", return_value=engine) as create:
        database = AuthDatabase(Settings(auth_database_credentials=credentials))
        url = create.call_args.args[0]
        assert url.database == "famquest_auth"
        assert url.username == "famquest_auth_app"
        assert url.password == "x" * 40
        database.close()
    engine.dispose.assert_called_once()
