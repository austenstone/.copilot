import contextlib
import importlib.util
import io
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "check_recipes", ROOT / "scripts/check-recipes.py"
)
recipes = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recipes)


class RecipeTests(unittest.TestCase):
    def check(self, command):
        with contextlib.redirect_stdout(io.StringIO()):
            return recipes.check_unguarded(
                ROOT / "skills/example.md", f"```bash\n{command}\n```"
            )

    def test_standalone_native_scanners_are_allowed(self):
        for command in (
            "actionlint -format '{{json .}}' ci.yml",
            "zizmor --format json ci.yml",
        ):
            with self.subTest(command=command):
                self.assertEqual(0, self.check(command))

    def test_unguarded_findings_cannot_skip_later_commands(self):
        for command in (
            "set -euo pipefail\nactionlint ci.yml\necho done",
            "actionlint ci.yml\nzizmor ci.yml",
            "actionlint ci.yml; echo done",
            "actionlint ci.yml && zizmor ci.yml",
        ):
            with self.subTest(command=command):
                self.assertGreater(self.check(command), 0)

    def test_explicit_status_capture_is_allowed(self):
        self.assertEqual(
            0,
            self.check("actionlint ci.yml && rc=0 || rc=$?\nprintf '%s' \"$rc\""),
        )
