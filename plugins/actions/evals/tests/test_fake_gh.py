import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


EVAL_ROOT = Path(__file__).resolve().parents[1]
SCRATCH_ROOT = EVAL_ROOT / ".test-work-fake-gh"
FAKE_GH = EVAL_ROOT / "harness" / "fake_gh.py"


class FakeGhTests(unittest.TestCase):
    def setUp(self) -> None:
        shutil.rmtree(SCRATCH_ROOT, ignore_errors=True)
        SCRATCH_ROOT.mkdir()
        self.fixture = SCRATCH_ROOT / "fixture.json"
        self.fixture.write_text(
            json.dumps(
                {
                    "rules": [
                        {
                            "argv": ["api", "repos/octo/synthetic/actions/runs/1"],
                            "stdout": "{\"id\":1}",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        self.environment = {
            **os.environ,
            "ACTIONS_EVAL_GH_FIXTURE": str(self.fixture),
        }

    def tearDown(self) -> None:
        shutil.rmtree(SCRATCH_ROOT, ignore_errors=True)

    def run_fake(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(FAKE_GH), *arguments],
            env=self.environment,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_returns_exact_fixture(self) -> None:
        result = self.run_fake("api", "repos/octo/synthetic/actions/runs/1")
        self.assertEqual(0, result.returncode)
        self.assertEqual('{"id":1}\n', result.stdout)

    def test_optional_trace_records_exact_matches_without_copying_responses(self) -> None:
        trace = SCRATCH_ROOT / "trace.jsonl"
        self.environment["ACTIONS_EVAL_GH_TRACE"] = str(trace)
        self.run_fake("api", "repos/octo/synthetic/actions/runs/1")
        self.run_fake("api", "repos/octo/synthetic/actions/runs/2")
        records = [json.loads(line) for line in trace.read_text().splitlines()]
        self.assertEqual([True, False], [record["matched"] for record in records])
        self.assertEqual(["api", "repos/octo/synthetic/actions/runs/1"], records[0]["argv"])
        self.assertNotIn("stdout", records[0])

    def test_rejects_unsupported_call(self) -> None:
        result = self.run_fake("api", "repos/octo/synthetic/actions/runs/2")
        self.assertEqual(64, result.returncode)
        self.assertIn("unsupported call rejected", result.stderr)

    def test_rejects_workflow_execution_even_if_fixture_listed(self) -> None:
        self.fixture.write_text(
            json.dumps(
                {
                    "rules": [
                        {
                            "argv": ["workflow", "run", "deploy.yml"],
                            "stdout": "should never happen",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        result = self.run_fake("workflow", "run", "deploy.yml")
        self.assertEqual(64, result.returncode)
        self.assertNotIn("should never happen", result.stdout)

    def test_rejects_mutating_api_method(self) -> None:
        result = self.run_fake(
            "api",
            "--method",
            "POST",
            "repos/octo/synthetic/actions/workflows/deploy.yml/dispatches",
        )
        self.assertEqual(64, result.returncode)


if __name__ == "__main__":
    unittest.main()
