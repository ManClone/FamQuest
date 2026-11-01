import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "prepare_stage", Path(__file__).parents[1] / "prepare-central-stage.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class StagePackageTest(unittest.TestCase):
    def test_private_package_separates_owner_and_runtime_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "new"
            MODULE.prepare(
                target,
                "https://famtest.example.test",
                "famquest:central-ci",
                "/isolated/stage",
            )

            def read_env(name):
                return dict(
                    line.split("=", 1)
                    for line in (target / name).read_text().splitlines()
                )

            bootstrap = read_env("bootstrap.env")
            runtime = read_env("runtime.env")
            self.assertNotIn("FAMQUEST_STAGE_BOOTSTRAP", runtime)
            self.assertEqual(runtime["POSTGRES_PASSWORD"], "")
            self.assertNotEqual(runtime["POSTGRES_USER"], bootstrap["POSTGRES_USER"])
            self.assertNotIn("STAGE_A_PARENT_PASSWORD", runtime)
            credentials = json.loads(runtime["FAMILY_DATABASE_CREDENTIALS"])
            self.assertEqual(set(credentials), {"famquest_stage_a", "famquest_stage_b"})
            passwords = [
                bootstrap["POSTGRES_PASSWORD"],
                json.loads(runtime["AUTH_DATABASE_CREDENTIALS"])["password"],
                *(entry["password"] for entry in credentials.values()),
                *(
                    value
                    for key, value in bootstrap.items()
                    if key.startswith("STAGE_")
                ),
            ]
            self.assertEqual(len(set(passwords)), 8)
            original = (target / "postgres.env").read_bytes()
            with self.assertRaises(ValueError):
                MODULE.prepare(
                    target,
                    "https://famtest.example.test",
                    "famquest:central-ci",
                    "/isolated/stage",
                )
            self.assertEqual((target / "postgres.env").read_bytes(), original)
            compose = (target / "compose.yml").read_text()
            self.assertIn("127.0.0.1:11902:8080", compose)
            self.assertNotIn("11901", compose)
            self.assertNotIn("19014a7", compose)

    def test_plain_http_and_mutable_application_images_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            for origin, image in (
                ("http://famtest.example.test", "famquest:central-ci"),
                ("https://famtest.example.test", "ghcr.io/manclone/famquest:latest"),
            ):
                with self.assertRaises(ValueError):
                    MODULE.prepare(
                        Path(directory) / "new", origin, image, "/isolated/stage"
                    )


if __name__ == "__main__":
    unittest.main()
