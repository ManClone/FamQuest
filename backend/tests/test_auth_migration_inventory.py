"""Check identity migration prerequisites against a restored legacy database."""

from app.auth_migration_inventory import LegacyInventory, assert_single_family_migration_ready


def test_one_family_with_assigned_users_is_ready():
    inventory = LegacyInventory(1, 2, 1, 3, 0, 2)
    assert_single_family_migration_ready(inventory)


def test_missing_family_rejected():
    import pytest

    with pytest.raises(ValueError, match="exactly one"):
        assert_single_family_migration_ready(LegacyInventory(0, 0, 0, 0, 0, 0))


def test_unassigned_accounts_rejected():
    import pytest

    with pytest.raises(ValueError, match="without family"):
        assert_single_family_migration_ready(LegacyInventory(1, 2, 0, 2, 1, 1))
