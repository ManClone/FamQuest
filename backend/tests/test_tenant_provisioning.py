"""Ensure planned family SQL is isolated and identifier-safe."""

import pytest

from app.tenant_provisioning import planned_provisioning_sql, provisioning_sql


def test_two_family_databases_get_distinct_roles():
    plans = planned_provisioning_sql()
    assert set(plans) == {"Sertl", "Henning"}
    for name, database in (("Sertl", "famquest_sertl"), ("Henning", "famquest_henning")):
        sql = plans[name]
        assert f'CREATE DATABASE "{database}"' in sql[1]
        assert f'REVOKE CONNECT ON DATABASE "{database}" FROM PUBLIC' in sql[2]
        assert f'"{database}_app"' in sql[0]


@pytest.mark.parametrize("database", ["other", "famquest_bad;DROP", "famquest_ä"])
def test_unsafe_database_names_rejected(database):
    with pytest.raises(ValueError):
        provisioning_sql(database, f"{database}_app")
