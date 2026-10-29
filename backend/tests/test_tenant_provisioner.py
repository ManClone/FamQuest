"""Provisioning rejects invalid inputs before touching a database."""

import pytest
from sqlalchemy import create_engine

from app.tenant_provisioner import provision_empty_family


def test_provisioning_requires_postgresql():
    engine = create_engine("sqlite://")
    try:
        with pytest.raises(ValueError, match="PostgreSQL"):
            provision_empty_family(engine, "famquest_sertl", "x" * 40)
    finally:
        engine.dispose()


def test_provisioning_rejects_weak_password_before_connecting():
    from unittest.mock import Mock

    engine = Mock()
    engine.dialect.name = "postgresql"
    with pytest.raises(ValueError, match="password"):
        provision_empty_family(engine, "famquest_henning", "short")
    engine.connect.assert_not_called()


def test_provisioning_rejects_unsafe_identifier_before_connecting():
    from unittest.mock import Mock

    engine = Mock()
    engine.dialect.name = "postgresql"
    with pytest.raises(ValueError, match="identifier"):
        provision_empty_family(engine, "famquest_bad;drop", "x" * 40)
    engine.connect.assert_not_called()
