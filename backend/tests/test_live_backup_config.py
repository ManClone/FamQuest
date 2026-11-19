import importlib.util
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "prepare_live_backup", ROOT / "scripts/prepare-live-backup.py"
)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def test_backup_update_preserves_all_other_compose_settings(tmp_path):
    original = yaml.safe_load((ROOT / "docker-compose.qnap-live-final.yml").read_text())
    original["services"]["backup"]["command"] = ["old command"]
    path = tmp_path / "compose.yml"
    path.write_text(yaml.safe_dump(original))
    before = path.read_bytes()
    script = (ROOT / "scripts/qnap-live-multitenant-backup.sh").read_text()
    helper.update(path, script)
    changed = yaml.safe_load(path.read_text())
    command = changed["services"]["backup"]["command"]
    assert command == [script.replace("$", "$$")]
    changed["services"]["backup"]["command"] = ["old command"]
    assert changed == original
    assert path.with_name("compose.yml.before-multitenant-backup").read_bytes() == before
    helper.update(path, script)  # Identical command is a read-only no-op.
    with pytest.raises(ValueError, match="Previous update"):
        helper.update(path, script + "\n")


def test_checked_in_backup_command_matches_source():
    compose = yaml.safe_load((ROOT / "docker-compose.qnap-live-final.yml").read_text())
    script = (ROOT / "scripts/qnap-live-multitenant-backup.sh").read_text()
    assert compose["services"]["backup"]["command"] == [script.replace("$", "$$")]
