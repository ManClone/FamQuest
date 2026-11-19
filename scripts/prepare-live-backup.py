"""Replace only the backup command in an existing private live Compose file."""

import argparse
import os
from pathlib import Path

import yaml


def update(path, script):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("Compose must be a regular file")
    original = path.read_bytes()
    compose = yaml.safe_load(original)
    service = compose["services"]["backup"]
    if (
        service["entrypoint"] != ["/bin/sh", "-ec"]
        or "backup" not in service["profiles"]
    ):
        raise ValueError("Unexpected backup service")
    command = script.replace("$", "$$")
    if service["command"] == [command]:
        return
    backup = path.with_name(path.name + ".before-multitenant-backup")
    pending = path.with_name(path.name + ".multitenant-pending")
    if backup.exists() or pending.exists():
        raise ValueError("Previous update exists; inspect manually")
    service["command"] = [command]
    for target, content in (
        (backup, original),
        (pending, yaml.safe_dump(compose, sort_keys=False).encode()),
    ):
        with target.open("xb") as output:
            os.chmod(target, 0o600)
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.chown(target, path.stat().st_uid, path.stat().st_gid)
    if path.read_bytes() != original:
        raise ValueError("Compose changed concurrently")
    os.replace(pending, path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compose", required=True)
    parser.add_argument("--script", required=True)
    args = parser.parse_args()
    update(args.compose, Path(args.script).read_text())
    print("PASS: only backup command updated; original Compose retained privately.")
