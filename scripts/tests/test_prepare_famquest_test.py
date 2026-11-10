import importlib.util
import json
import tempfile
import shutil
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    'prepare_test', Path(__file__).parents[1] / 'prepare-famquest-test.py'
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PermanentTestPackage(unittest.TestCase):
    def test_own_project_volumes_image_anchor_and_credentials(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / 'private'
            image = 'ghcr.io/manclone/famquest:test-' + 'a' * 40
            MODULE.prepare(output, 'https://famtest.example.test', image,
                           '/share/Container/famquest-test', '192.168.1.2')
            compose = (output / 'compose.yml').read_text()
            self.assertIn('name: famquest-test\n', compose)
            self.assertIn('famquest-test-db-v1', compose)
            self.assertIn('famquest-test-uploads-v1', compose)
            self.assertNotIn('famquest-release', compose)
            self.assertNotIn('famquest-live-config', compose)
            self.assertNotIn('famquest-central-stage-db-v1', compose)
            self.assertEqual(compose.count('image: *app-image'), 2)
            self.assertEqual(compose.count(image), 1)
            self.assertIn('192.168.1.2:11902:8080', compose)
            self.assertIn('central-stage-mcp', (output / 'gateway.conf').read_text())
            runtime = (output / 'runtime.env').read_text()
            bootstrap = (output / 'bootstrap.env').read_text()
            self.assertIn('POSTGRES_USER=unused_in_central_mode', runtime)
            self.assertNotIn('STAGE_A_PARENT_PASSWORD', runtime)
            self.assertIn('OAUTH_DYNAMIC_REGISTRATION=true', runtime)
            self.assertNotEqual(runtime, bootstrap)
            self.assertEqual((output / 'runtime.env').stat().st_mode & 0o777, 0o600)
            metadata = json.loads((output / 'images.json').read_text())
            self.assertEqual(metadata['app'], image)
            self.assertEqual(metadata['project'], 'famquest-test')
            old = (output / 'postgres.env').read_bytes()
            with self.assertRaises(ValueError):
                MODULE.prepare(output, 'https://famtest.example.test', image,
                               '/share/Container/famquest-test')
            self.assertEqual(old, (output / 'postgres.env').read_bytes())

    def test_reuse_keeps_copied_credentials_and_refuses_second_render(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / 'source'
            target = Path(root) / 'target'
            target.mkdir()
            MODULE.prepare(source, 'https://famtest.example.test', MODULE.DEFAULT_APP,
                           '/share/Container/famquest-test')
            private = ['postgres.env', 'runtime.env', 'bootstrap.env', 'TESTZUGAENGE-PRIVAT.txt']
            for name in private:
                shutil.copy2(source / name, target / name)
            before = {name: (target / name).read_bytes() for name in private}
            MODULE.configure_existing(target, 'https://famtest.example.test', MODULE.DEFAULT_APP,
                                      '/share/Container/famquest-test', '192.168.1.2')
            self.assertIn('test-db: {external: true, name: famquest-test-db-v1}', (target / 'compose.yml').read_text())
            self.assertIn('test-uploads: {external: true, name: famquest-test-uploads-v1}', (target / 'compose.yml').read_text())
            for name in ['postgres.env', 'TESTZUGAENGE-PRIVAT.txt']:
                self.assertEqual(before[name], (target / name).read_bytes())
            for name in ['runtime.env', 'bootstrap.env']:
                self.assertTrue((target / name).read_bytes().startswith(before[name]))
            with self.assertRaises(ValueError):
                MODULE.configure_existing(target, 'https://famtest.example.test', MODULE.DEFAULT_APP,
                                          '/share/Container/famquest-test')

    def test_reuse_rejects_another_origin_before_writing_any_public_config(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / 'source'
            target = Path(root) / 'target'
            target.mkdir()
            MODULE.prepare(source, 'https://famtest.example.test', MODULE.DEFAULT_APP,
                           '/share/Container/famquest-test')
            for name in ['postgres.env', 'runtime.env', 'bootstrap.env', 'TESTZUGAENGE-PRIVAT.txt']:
                shutil.copy2(source / name, target / name)
            before = (target / 'runtime.env').read_bytes()
            with self.assertRaises(ValueError):
                MODULE.configure_existing(target, 'https://other.example.test', MODULE.DEFAULT_APP,
                                          '/share/Container/famquest-test')
            self.assertFalse((target / 'compose.yml').exists())
            self.assertEqual(before, (target / 'runtime.env').read_bytes())

    def test_rolling_test_channels_use_always_and_keep_live_out(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / 'private'
            MODULE.prepare(output, 'https://famtest.example.test', MODULE.DEFAULT_APP,
                           '/share/Container/famquest-test')
            compose = (output / 'compose.yml').read_text()
            self.assertIn('"ghcr.io/manclone/famquest:test"', compose)
            self.assertIn('"ghcr.io/manclone/famquest-mcp:test"', compose)
            self.assertEqual(compose.count('pull_policy: always'), 3)
            self.assertNotIn(':latest', compose)

    def test_rejects_wrong_images_directory_host_and_origin_before_generation(self):
        image = 'famquest:sternchen-review-20261109-aclfix'
        cases = [
            ('https://famtest.example.test', 'ghcr.io/manclone/famquest:latest', '/share/Container/famquest-test', '127.0.0.1'),
            ('https://famtest.example.test', image, '/share/Container/famquest-live', '127.0.0.1'),
            ('https://famtest.example.test', image, '/share/Container/famquest-test', '0.0.0.0;echo bad'),
            ('http://famtest.example.test', image, '/share/Container/famquest-test', '127.0.0.1'),
        ]
        with tempfile.TemporaryDirectory() as root:
            for args in cases:
                with self.subTest(args=args):
                    output = Path(root) / 'private'
                    with self.assertRaises(ValueError):
                        MODULE.prepare(output, *args)
                    self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
