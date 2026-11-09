"""Normalize copied source metadata, including QNAP ACLs, during an image build."""

import os
from pathlib import Path


def normalize(root: Path = Path("/app")) -> None:
    count = 0
    for directory, children, files in os.walk(root, followlinks=False):
        # uv creates its own environment; never rewrite it or follow symlinks.
        children[:] = [
            name
            for name in children
            if name != ".venv" and not (Path(directory) / name).is_symlink()
        ]
        for path in [Path(directory), *(Path(directory) / name for name in files)]:
            if path.is_symlink():
                continue
            for attribute in os.listxattr(path):
                if attribute in ("system.posix_acl_access", "system.posix_acl_default"):
                    os.removexattr(path, attribute)
                    count += 1
            path.chmod(0o755 if path.is_dir() or path.name == "docker-entrypoint.sh" else 0o644)
    print(f"Normalized source permissions; removed {count} POSIX ACL attributes.")


if __name__ == "__main__":
    normalize()
