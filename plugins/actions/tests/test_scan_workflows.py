from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import unittest
import uuid
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills/actions-workflow-toolkit/scripts/scan-workflows.py"
)
SPEC = importlib.util.spec_from_file_location("scan_workflows", SCRIPT)
assert SPEC and SPEC.loader
SCAN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCAN)


class ScanWorkflowsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scratch = Path(__file__).parent / f".scratch-{uuid.uuid4().hex}"
        self.bin = self.scratch / "bin"
        self.repo = self.scratch / "repo"
        (self.repo / ".github/workflows").mkdir(parents=True)
        self.bin.mkdir(parents=True)
        (self.repo / ".github/workflows/ci.yml").write_text(
            "name: CI\non: push\njobs: {}\n", encoding="utf-8"
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.scratch, ignore_errors=True)

    def tool(self, name: str, body: str) -> None:
        path = self.bin / name
        path.write_text(f"#!{sys.executable}\n{body}\n", encoding="utf-8")
        path.chmod(0o755)

    def create_workflows(self, total: int) -> None:
        workflow_root = self.repo / ".github/workflows"
        for index in range(1, total):
            (workflow_root / f"workflow-{index:04d}.yml").write_text(
                f"name: Workflow {index}\non: push\njobs: {{}}\n",
                encoding="utf-8",
            )

    def standard_tools(
        self,
        actionlint_body: str = (
            "import json, sys\n"
            "if '-version' in sys.argv: print('actionlint 1.7.7')\n"
            "else: print('[]')"
        ),
        zizmor_body: str = (
            "import sys\n"
            "if '--version' in sys.argv: print('zizmor 1.29.0')\n"
            "else: print('[]')"
        ),
    ) -> None:
        self.tool("actionlint", actionlint_body)
        self.tool("zizmor", zizmor_body)
        self.tool(
            "shellcheck",
            "import sys\nprint('ShellCheck 0.10.0')",
        )

    def run_scan(self, *arguments: str, path: str | None = None) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["PATH"] = str(self.bin)
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--path",
                path or str(self.repo),
                *arguments,
            ],
            cwd=self.scratch,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_preserves_finding_exit_codes_and_json(self) -> None:
        actionlint_finding = {
            "message": "undefined value",
            "filepath": ".github/workflows/ci.yml",
            "line": 3,
            "kind": "expression",
        }
        zizmor_finding = {
            "ident": "template-injection",
            "determinations": {"severity": "High", "confidence": "High"},
            "locations": [],
        }
        self.standard_tools(
            "import json, sys\n"
            "if '-version' in sys.argv: print('actionlint 1.7.7'); raise SystemExit\n"
            f"print(json.dumps([{actionlint_finding!r}]))\n"
            "raise SystemExit(1)",
            "import json, sys\n"
            "if '--version' in sys.argv: print('zizmor 1.29.0'); raise SystemExit\n"
            f"print(json.dumps([{zizmor_finding!r}]))\n"
            "raise SystemExit(14)",
        )

        completed = self.run_scan()
        document = json.loads(completed.stdout)

        self.assertEqual(completed.returncode, 0)
        self.assertEqual(document["result"]["actionlint"]["exit_code"], 1)
        self.assertEqual(document["result"]["zizmor"]["exit_code"], 14)
        self.assertEqual(len(document["result"]["actionlint"]["findings"]), 1)
        self.assertEqual(len(document["result"]["zizmor"]["findings"]), 1)

    def test_actionlint_timeout_recovers_without_shellcheck(self) -> None:
        workflow = self.repo / ".github/workflows/ci.yml"
        envelope = SCAN.empty_envelope()
        attempts = [
            {
                "command": ["actionlint", "-format", "{{json .}}", ".github/workflows/ci.yml"],
                "exit_code": None,
                "stdout": "",
                "stderr": "simulated bounded timeout",
                "timed_out": True,
            },
            {
                "command": [
                    "actionlint",
                    "-shellcheck=",
                    "-format",
                    "{{json .}}",
                    ".github/workflows/ci.yml",
                ],
                "exit_code": 0,
                "stdout": "[]\n",
                "stderr": "",
                "timed_out": False,
            },
        ]

        with mock.patch.object(SCAN, "run_command", side_effect=attempts) as run:
            result, failed, examined = SCAN.run_actionlint(
                envelope,
                {"available": True, "executable": str(self.bin / "actionlint")},
                self.repo,
                [workflow],
                0.05,
            )

        codes = [item["code"] for item in envelope["diagnostics"]]
        self.assertFalse(failed, json.dumps(envelope, indent=2))
        self.assertEqual(result["status"], "degraded", json.dumps(result, indent=2))
        self.assertEqual(examined, {".github/workflows/ci.yml"})
        self.assertIn("timeout", codes, json.dumps(envelope, indent=2))
        self.assertIn("degraded_analysis", codes, json.dumps(envelope, indent=2))
        self.assertIn(
            "-shellcheck=",
            run.call_args_list[1].args[0],
            json.dumps(result["attempts"], indent=2),
        )

    def test_run_command_classifies_subprocess_timeout(self) -> None:
        attempt = SCAN.run_command(
            [sys.executable, "-c", "import time; time.sleep(1)"],
            cwd=self.scratch,
            timeout=0.05,
        )

        self.assertTrue(attempt["timed_out"], attempt["stderr"])
        self.assertIsNone(attempt["exit_code"], attempt["stderr"])

    def test_large_scope_with_only_actionlint_reports_bounded_coverage(self) -> None:
        self.create_workflows(SCAN.MAX_WORKFLOWS + 1)
        self.tool(
            "actionlint",
            "import sys\n"
            "if '-version' in sys.argv: print('actionlint 1.7.7')\n"
            "else: print('[]')",
        )
        self.tool("shellcheck", "print('ShellCheck 0.10.0')")

        completed = self.run_scan()
        document = json.loads(completed.stdout)

        self.assertEqual(completed.returncode, 0)
        self.assertEqual(document["coverage"]["requested"], 501)
        self.assertEqual(document["coverage"]["examined"], 500)
        self.assertEqual(document["coverage"]["status"], "partial")
        self.assertEqual(document["result"]["actionlint"]["requested"], 501)
        self.assertEqual(document["result"]["actionlint"]["examined"], 500)
        self.assertEqual(document["result"]["zizmor"]["requested"], 501)
        self.assertEqual(document["result"]["zizmor"]["examined"], 0)
        self.assertTrue(document["coverage"]["limitations"])

    def test_large_scope_union_counts_degraded_zizmor_coverage(self) -> None:
        self.create_workflows(SCAN.MAX_WORKFLOWS + 1)
        self.standard_tools(
            zizmor_body=(
                "import sys\n"
                "if '--version' in sys.argv: print('zizmor 1.29.0'); raise SystemExit\n"
                "if '--no-online-audits' in sys.argv: print('[]'); raise SystemExit\n"
                "print('fatal: no audit was performed', file=sys.stderr)\n"
                "raise SystemExit(1)"
            )
        )

        completed = self.run_scan()
        document = json.loads(completed.stdout)

        self.assertEqual(completed.returncode, 0)
        self.assertEqual(document["coverage"]["requested"], 501)
        self.assertEqual(document["coverage"]["examined"], 501)
        self.assertEqual(document["coverage"]["status"], "partial")
        self.assertEqual(document["result"]["actionlint"]["examined"], 500)
        self.assertEqual(document["result"]["zizmor"]["requested"], 501)
        self.assertEqual(document["result"]["zizmor"]["examined"], 501)
        self.assertEqual(document["result"]["zizmor"]["status"], "degraded")

    def test_local_zizmor_online_failure_recovers_and_records_skips(self) -> None:
        self.standard_tools(
            zizmor_body=(
                "import sys\n"
                "if '--version' in sys.argv: print('zizmor 1.29.0'); raise SystemExit\n"
                "if '--no-online-audits' in sys.argv: print('[]'); raise SystemExit\n"
                "print('fatal: no audit was performed', file=sys.stderr)\n"
                "raise SystemExit(1)"
            )
        )

        completed = self.run_scan()
        document = json.loads(completed.stdout)

        self.assertEqual(completed.returncode, 0)
        self.assertEqual(document["result"]["zizmor"]["status"], "degraded")
        self.assertEqual(
            document["result"]["skipped_network_audits"],
            SCAN.SKIPPED_NETWORK_AUDITS,
        )

    def test_local_zizmor_uses_offline_as_final_recovery(self) -> None:
        self.standard_tools(
            zizmor_body=(
                "import sys\n"
                "if '--version' in sys.argv: print('zizmor 1.29.0'); raise SystemExit\n"
                "if '--offline' in sys.argv: print('[]'); raise SystemExit\n"
                "print('fatal: no audit was performed', file=sys.stderr)\n"
                "raise SystemExit(1)"
            )
        )

        completed = self.run_scan()
        document = json.loads(completed.stdout)
        attempts = [
            attempt["name"] for attempt in document["result"]["zizmor"]["attempts"]
        ]

        self.assertEqual(completed.returncode, 0)
        self.assertEqual(
            attempts, ["online", "no-online-audits", "offline"]
        )
        self.assertEqual(document["result"]["zizmor"]["status"], "degraded")

    def test_no_inputs_is_unavailable_not_clean(self) -> None:
        self.standard_tools()
        empty = self.scratch / "empty"
        empty.mkdir()

        completed = self.run_scan(path=str(empty))
        document = json.loads(completed.stdout)

        self.assertEqual(completed.returncode, 3)
        self.assertEqual(document["coverage"]["status"], "unavailable")
        self.assertIn("no_inputs", [item["code"] for item in document["diagnostics"]])

    def test_missing_scanners_exit_four(self) -> None:
        completed = self.run_scan()
        document = json.loads(completed.stdout)

        self.assertEqual(completed.returncode, 4)
        self.assertEqual(document["coverage"]["status"], "unavailable")
        self.assertEqual(
            [item["code"] for item in document["diagnostics"]].count(
                "missing_executable"
            ),
            2,
        )

    def test_actionlint_interpretation_separates_configuration_and_shell_hygiene(self) -> None:
        findings = [
            {"kind": "runner-label", "message": "label is unknown"},
            {
                "kind": "shellcheck",
                "message": "SC2006:style:1:1: Use $(...) notation",
            },
            {
                "kind": "shellcheck",
                "message": "SC2086:info:1:1: Double quote to prevent globbing",
            },
        ]
        self.standard_tools(
            "import json, sys\n"
            "if '-version' in sys.argv: print('actionlint 1.7.7'); raise SystemExit\n"
            f"print(json.dumps({findings!r}))\n"
            "raise SystemExit(1)"
        )

        completed = self.run_scan()
        document = json.loads(completed.stdout)
        classifications = [
            finding["interpretation"]["classification"]
            for finding in document["result"]["actionlint"]["findings"]
        ]

        self.assertEqual(
            classifications,
            ["configuration-dependent", "shell-hygiene", "shell-correctness"],
        )

    def test_remote_recovery_never_attempts_offline_mode(self) -> None:
        self.assertEqual(
            SCAN.zizmor_attempt_plan("remote"),
            [
                ("online", []),
                ("no-online-audits", ["--no-online-audits"]),
            ],
        )

    def test_remote_no_inputs_recovers_from_exact_repository_archive(self) -> None:
        self.standard_tools(
            zizmor_body=(
                "import sys\n"
                "if '--version' in sys.argv: print('zizmor 1.29.0'); raise SystemExit\n"
                "if any(arg == 'octo/repo' for arg in sys.argv):\n"
                "    print('no inputs collected', file=sys.stderr); raise SystemExit(3)\n"
                "print('[]')"
            )
        )
        fetched = self.scratch / "fetched"
        (fetched / ".github/workflows").mkdir(parents=True)
        (fetched / ".github/workflows/ci.yml").write_text(
            "name: CI\non: push\njobs: {}\n", encoding="utf-8"
        )
        environment = os.environ.copy()
        environment["PATH"] = str(self.bin)
        stdout = io.StringIO()
        stderr = io.StringIO()
        previous_cwd = Path.cwd()
        try:
            os.chdir(self.scratch)
            with (
                mock.patch.dict(os.environ, environment, clear=True),
                mock.patch.object(
                    SCAN,
                    "fetch_remote_archive",
                    return_value=(fetched, fetched, None),
                ),
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                exit_code = SCAN.main(["--repository", "octo/repo"])
        finally:
            os.chdir(previous_cwd)

        document = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(
            document["result"]["zizmor"]["recovery"],
            "local archive after remote no inputs",
        )
        self.assertEqual(document["coverage"]["status"], "partial")

    def test_local_file_scope_does_not_expand_to_unrelated_actions(self) -> None:
        action = self.repo / "unrelated/action.yml"
        action.parent.mkdir()
        action.write_text("runs:\n  using: composite\n  steps: []\n", encoding="utf-8")
        workflow = self.repo / ".github/workflows/ci.yml"
        envelope = SCAN.empty_envelope()

        local_inputs = SCAN.zizmor_local_inputs(
            envelope, self.repo, [workflow], include_actions=False
        )
        remote_recovery_inputs = SCAN.zizmor_local_inputs(
            envelope, self.repo, [workflow], include_actions=True
        )

        self.assertEqual(local_inputs, [".github/workflows/ci.yml"])
        self.assertIn("unrelated/action.yml", remote_recovery_inputs)

    def test_invalid_selector_returns_structured_exit_two(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=self.scratch,
            capture_output=True,
            text=True,
            check=False,
        )
        document = json.loads(completed.stdout)

        self.assertEqual(completed.returncode, 2)
        self.assertEqual(document["diagnostics"][0]["code"], "invalid_input")

    def test_invalid_tool_output_is_a_crash_not_a_clean_result(self) -> None:
        self.standard_tools(
            actionlint_body=(
                "import sys\n"
                "if '-version' in sys.argv: print('actionlint 1.7.7'); raise SystemExit\n"
                "print('not-json')"
            )
        )

        completed = self.run_scan()
        document = json.loads(completed.stdout)

        self.assertEqual(completed.returncode, 5)
        self.assertEqual(document["result"]["actionlint"]["status"], "failed")
        self.assertIn(
            "tool_crash", [item["code"] for item in document["diagnostics"]]
        )


if __name__ == "__main__":
    unittest.main()
