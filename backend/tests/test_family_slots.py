import json

import pytest

from app.config import FamilyDatabaseCredentials
from app.family_slots import private_copy, replace_settings
from app.staging_bootstrap import (
    DATABASES,
    OWNER,
    SPARE_DATABASES,
    inspect_cluster,
    validated_inputs,
)
from tests.test_staging_bootstrap import Inventory, inputs


def test_private_configuration_backups_are_exclusive_and_preserve_other_values(tmp_path):
    path = tmp_path / "private.env"
    private_copy(path, b"EXISTING=keep\n")
    with pytest.raises(FileExistsError):
        private_copy(path, b"replacement")
    assert path.read_bytes() == b"EXISTING=keep\n"
    changed = replace_settings(
        "EXISTING=keep\nFAMILY_CREATION_DATABASES=[]\n",
        {"FAMILY_CREATION_DATABASES": json.dumps(list(SPARE_DATABASES))},
    )
    assert "EXISTING=keep" in changed and '"famquest_stage_c"' in changed
    with pytest.raises(ValueError):
        replace_settings("KEY=a\nKEY=b\n", {"KEY": "new"})


def test_only_explicit_fixed_spare_databases_extend_staging_inventory():
    settings, env = inputs()
    credentials = dict(settings.family_database_credentials)
    for part, name in zip(("c", "d"), SPARE_DATABASES, strict=True):
        credentials[name] = FamilyDatabaseCredentials(username=f"{name}_app", password=part * 48)
    settings = settings.model_copy(
        update={
            "family_database_credentials": credentials,
            "family_creation_databases": list(SPARE_DATABASES),
        }
    )
    assert len(validated_inputs(settings, env)) == 4
    databases = (*DATABASES, *SPARE_DATABASES)
    inventory = Inventory(
        {"postgres", "famquest_auth", *databases},
        {OWNER, "famquest_auth_app", *(f"{name}_app" for name in databases)},
        marker=True,
    )
    assert inspect_cluster(inventory, "https://famtest.example.test", databases) == "ready"
    with pytest.raises(RuntimeError):
        inspect_cluster(inventory, "https://famtest.example.test")
    with pytest.raises(ValueError):
        validated_inputs(
            settings.model_copy(update={"family_creation_databases": ["production"]}), env
        )
