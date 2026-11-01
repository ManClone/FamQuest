from types import SimpleNamespace

import pytest

from app.config import FamilyDatabaseCredentials, Settings
from app.staging_bootstrap import DATABASES, OWNER, inspect_cluster, validated_inputs


def inputs():
    settings = Settings(
        _env_file=None,
        postgres_host="central-stage-db",
        postgres_user=OWNER,
        postgres_password="o" * 48,
        public_url="https://famtest.example.test",
        auth_database_credentials=FamilyDatabaseCredentials(
            username="famquest_auth_app", password="r" * 48
        ),
        family_database_credentials={
            name: FamilyDatabaseCredentials(username=f"{name}_app", password=part * 48)
            for name, part in zip(DATABASES, ("a", "b"), strict=True)
        },
    )
    env = {"FAMQUEST_STAGE_BOOTSTRAP": "new-isolated-cluster-v1"}
    for family in ("A", "B"):
        for role in ("PARENT", "CHILD"):
            env[f"STAGE_{family}_{role}_PASSWORD"] = f"separate-{family}-{role}-password-123"
    return settings, env


def test_staging_requires_explicit_host_origin_roles_and_independent_credentials():
    settings, env = inputs()
    assert len(validated_inputs(settings, env)) == 4
    for changed in (
        {"postgres_host": "production"},
        {"postgres_user": "postgres"},
        {"public_url": "http://famtest.example.test"},
        {"central_background_jobs": True},
        {"family_database_credentials": {}},
    ):
        with pytest.raises(ValueError):
            validated_inputs(settings.model_copy(update=changed), env)
    with pytest.raises(ValueError):
        validated_inputs(settings, {})
    env["STAGE_B_CHILD_PASSWORD"] = env["STAGE_A_CHILD_PASSWORD"]
    with pytest.raises(ValueError):
        validated_inputs(settings, env)


class Inventory:
    def __init__(
        self, databases, roles, marker=None, origin="https://famtest.example.test", tables=0
    ):
        self.databases, self.roles = databases, roles
        self.marker, self.origin, self.tables = marker, origin, tables

    def scalar(self, statement):
        return self.marker if "to_regclass" in str(statement) else self.tables

    def scalars(self, statement):
        if "pg_database" in str(statement):
            return self.databases
        if "pg_roles" in str(statement):
            return self.roles
        return SimpleNamespace(all=lambda: [self.origin])


def test_fresh_cluster_inspection_refuses_foreign_or_partial_inventory():
    origin = "https://famtest.example.test"
    assert inspect_cluster(Inventory({"postgres"}, {OWNER}), origin) == "fresh"
    for inventory in (
        Inventory({"postgres", "famquest"}, {OWNER}),
        Inventory({"postgres"}, {OWNER, "famquest_stage_a_app"}),
        Inventory({"postgres"}, {OWNER}, tables=1),
    ):
        with pytest.raises(RuntimeError):
            inspect_cluster(inventory, origin)


def test_ready_cluster_must_match_marker_origin_and_complete_inventory():
    dbs = {"postgres", "famquest_auth", *DATABASES}
    roles = {OWNER, "famquest_auth_app", *(f"{name}_app" for name in DATABASES)}
    assert (
        inspect_cluster(Inventory(dbs, roles, marker=True), "https://famtest.example.test")
        == "ready"
    )
    for inventory in (
        Inventory(dbs | {"extra"}, roles, marker=True),
        Inventory(dbs, roles, marker=True, origin="https://elsewhere.example.test"),
    ):
        with pytest.raises(RuntimeError):
            inspect_cluster(inventory, "https://famtest.example.test")
