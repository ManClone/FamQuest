"""QNAP ACL regression tests without changing the host's application files."""
import importlib.util
import os
from pathlib import Path
import stat
import struct
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[2] / 'backend/docker-normalize-permissions.py'
spec = importlib.util.spec_from_file_location('image_permissions', SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ImagePermissionsTest(unittest.TestCase):
    def test_removes_named_access_and_default_acls(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / 'app'
            package.mkdir()
            source = package / 'deployment_check.py'
            source.write_text('pass\n')
            # A named user denial survives ordinary chmod; ACL removal must erase it.
            acl = struct.pack('<I', 2) + b''.join(
                struct.pack('<HHI', tag, permission, identity)
                for tag, permission, identity in [
                    (1, 7, 0xffffffff), (2, 0, os.getuid()), (4, 5, 0xffffffff),
                    (16, 5, 0xffffffff), (32, 5, 0xffffffff),
                ]
            )
            os.setxattr(package, 'system.posix_acl_access', acl)
            os.setxattr(package, 'system.posix_acl_default', acl)
            os.setxattr(source, 'system.posix_acl_access', acl)
            source.chmod(0o644)
            self.assertIn('system.posix_acl_access', os.listxattr(source))
            module.normalize(root)
            for path in (package, source):
                self.assertFalse(any('posix_acl' in a for a in os.listxattr(path)))
            self.assertEqual(stat.S_IMODE(package.stat().st_mode), 0o755)
            self.assertEqual(stat.S_IMODE(source.stat().st_mode), 0o644)

    def test_keeps_virtual_environment_and_symlink_targets_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / 'app'
            root.mkdir()
            venv = root / '.venv'
            venv.mkdir(mode=0o700)
            dependency = venv / 'dependency'
            dependency.write_text('private')
            dependency.chmod(0o600)
            external = parent / 'outside'
            external.mkdir(mode=0o700)
            (root / 'linked').symlink_to(external, target_is_directory=True)
            entrypoint = root / 'docker-entrypoint.sh'
            entrypoint.write_text('#!/bin/sh\n')
            module.normalize(root)
            self.assertEqual(stat.S_IMODE(venv.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(dependency.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(external.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(entrypoint.stat().st_mode), 0o755)


if __name__ == '__main__':
    unittest.main()
