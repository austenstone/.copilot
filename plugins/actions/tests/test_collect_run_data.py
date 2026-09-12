#!/usr/bin/env python3
"""Fixture-backed tests for collect-run-data.py."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

TEST_ROOT = Path(__file__).resolve().parent
PLUGIN_ROOT = TEST_ROOT.parent
TOOLKIT_ROOT = PLUGIN_ROOT / "skills/actions-workflow-toolkit"
SCRIPT = TOOLKIT_ROOT / "scripts/collect-run-data.py"
FIXTURES = TEST_ROOT / "fixtures/collect-run-data"
FAKE_BIN = FIXTURES / "bin"


class CollectRunDataTests(unittest.TestCase):
    def run_helper(
        self, fixture: str, run_id: int, *extra: str
    ) -> tuple[subprocess.CompletedProcess[str], dict]:
        env = os.environ.copy()
        env["PATH"] = f"{FAKE_BIN}{os.pathsep}{env.get('PATH', '')}"
        env["GH_FIXTURE_DIR"] = str(FIXTURES / fixture)
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--repository",
                "octo/example",
                "--run-id",
                str(run_id),
                *extra,
            ],
            check=False,
            capture_output=True,
            text=True,
            cwd=TOOLKIT_ROOT,
            env=env,
        )
        return completed, json.loads(completed.stdout)

    def test_paginates_deduplicates_and_excludes_reused_jobs(self) -> None:
        completed, document = self.run_helper(
            "complete",
            9001,
            "--per-page",
            "2",
            "--max-pages",
            "5",
            "--log-job-id",
            "201",
            "--log-job-id",
            "203",
            "--log-job-id",
            "204",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(document["schema_version"], "actions-helper/v1")
        self.assertEqual(document["provenance"]["attempt"]["selected"], 2)
        self.assertEqual(document["result"]["jobs_api"]["total_count"], 4)
        self.assertEqual(document["result"]["jobs_api"]["pages_fetched"], 3)
        self.assertEqual(
            document["result"]["jobs_api"]["duplicate_job_ids_ignored"], [201]
        )
        self.assertEqual(
            document["result"]["summary"]["selected_attempt_job_ids"],
            [201, 203, 204],
        )
        self.assertEqual(document["result"]["summary"]["reused_job_ids"], [202])
        self.assertEqual(
            document["result"]["billing"]["rounded_job_minutes"]["total"], 3
        )
        self.assertEqual(
            document["result"]["billing"]["billed_cost"]["status"], "unavailable"
        )
        groups = document["result"]["billing"]["rounded_job_minutes"][
            "by_exact_runner_labels"
        ]
        mystery = next(group for group in groups if "mystery-pool" in group["labels"])
        self.assertIsNone(mystery["sku"])
        self.assertIsNone(mystery["rate_per_minute"])
        jobs = {job["id"]: job for job in document["result"]["jobs"]}
        self.assertEqual(jobs[203]["lifecycle"], "cancelled")
        self.assertEqual(jobs[203]["log"]["status"], "missing")
        self.assertEqual(jobs[204]["lifecycle"], "skipped")
        self.assertEqual(jobs[204]["log"]["status"], "not_expected")
        self.assertEqual(document["result"]["run"]["lifecycle"], "cancelled")
        self.assertEqual(document["result"]["summary"]["logs"]["missing"], 1)
        self.assertEqual(
            document["result"]["log_requests"]["fulfilled_job_ids"], [201, 203]
        )
        self.assertEqual(
            document["result"]["log_requests"]["selected_but_not_probed_job_ids"],
            [204],
        )
        self.assertEqual(
            document["result"]["log_requests"]["unfulfilled_job_ids"], [204]
        )
        self.assertEqual(document["coverage"]["status"], "partial")
        self.assertIn("WARNING missing_logs", completed.stderr)
        self.assertIn("WARNING inaccessible_input", completed.stderr)

    def test_selects_an_explicit_attempt_and_records_definition_ref(self) -> None:
        completed, document = self.run_helper(
            "complete",
            9001,
            "--attempt",
            "1",
            "--ref",
            "refs/heads/feature",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(document["provenance"]["attempt"]["selection"], "explicit")
        self.assertEqual(document["result"]["run"]["attempt"], 1)
        self.assertEqual(
            document["provenance"]["workflow_definition"]["definition_ref"],
            "refs/heads/main",
        )
        self.assertFalse(
            document["provenance"]["workflow_definition"][
                "head_sha_is_definition_proof"
            ]
        )
        self.assertEqual(
            document["provenance"]["ref"]["relationship"], "matches_head_branch"
        )
        self.assertEqual(
            document["result"]["billing"]["rounded_job_minutes"]["total"], 12
        )
        self.assertEqual(document["result"]["jobs"][0]["log"]["status"], "not_requested")
        self.assertEqual(completed.stderr, "")

    def test_reports_unfinished_and_null_evidence_explicitly(self) -> None:
        completed, document = self.run_helper(
            "unfinished", 9002, "--log-job-id", "301"
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        job = document["result"]["jobs"][0]
        self.assertEqual(document["result"]["run"]["lifecycle"], "unfinished")
        self.assertEqual(job["lifecycle"], "unfinished")
        self.assertIsNone(job["conclusion"])
        self.assertEqual(job["log"]["status"], "not_yet_available")
        self.assertIsNone(job["rounded_job_minutes"])
        self.assertEqual(
            document["result"]["timing"]["critical_path_wall_clock"]["status"],
            "unavailable",
        )
        self.assertEqual(
            document["result"]["summary"]["conclusions"]["null"], 1
        )
        self.assertEqual(
            document["result"]["log_requests"]["selected_but_not_probed_job_ids"],
            [301],
        )
        self.assertEqual(
            document["result"]["log_requests"]["unfulfilled_job_ids"], [301]
        )
        self.assertEqual(document["coverage"]["status"], "partial")
        self.assertIn("WARNING inaccessible_input", completed.stderr)

    def test_reports_page_bound_as_partial_coverage(self) -> None:
        completed, document = self.run_helper(
            "complete",
            9001,
            "--per-page",
            "2",
            "--max-pages",
            "1",
            "--skip-log-checks",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(document["coverage"]["requested"], 4)
        self.assertEqual(document["coverage"]["examined"], 2)
        self.assertEqual(document["coverage"]["status"], "partial")
        self.assertFalse(document["result"]["jobs_api"]["complete"])
        rounded = document["result"]["billing"]["rounded_job_minutes"]
        self.assertEqual(rounded["status"], "partial")
        self.assertEqual(
            rounded["interpretation"], "observed_subtotal_not_complete_run_total"
        )
        wall_clock = document["result"]["timing"]["critical_path_wall_clock"]
        self.assertEqual(wall_clock["status"], "partial")
        self.assertEqual(wall_clock["interpretation"], "observed_partial_span")
        self.assertEqual(document["result"]["timing"]["job_waiting"]["status"], "partial")
        self.assertIn("WARNING degraded_analysis", completed.stderr)

    def test_collects_all_attempts_without_reused_job_double_counting(self) -> None:
        completed, document = self.run_helper(
            "complete",
            9001,
            "--all-attempts",
            "--per-page",
            "2",
            "--max-pages",
            "5",
            "--log-job-id",
            "202",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(document["provenance"]["attempt"]["selection"], "all")
        self.assertEqual(document["provenance"]["attempt"]["selected"], [1, 2])
        self.assertEqual(len(document["result"]["attempts"]), 2)
        self.assertEqual(
            document["result"]["summary"]["cross_attempt_duplicate_job_ids_ignored"],
            [202],
        )
        self.assertEqual(
            document["result"]["billing"]["rounded_job_minutes"]["total"], 15
        )
        self.assertEqual(
            document["result"]["billing"]["rounded_job_minutes"]["interpretation"],
            "all_collected_attempts_total",
        )
        self.assertEqual(
            document["result"]["timing"]["aggregate_wall_clock"]["status"],
            "unavailable",
        )
        self.assertEqual(
            [item["coverage"]["requested"] for item in document["result"]["attempts"]],
            [2, 4],
        )
        self.assertEqual(
            document["result"]["log_requests"]["fulfilled_job_ids"], [202]
        )
        self.assertEqual(
            document["result"]["log_requests"]["unfulfilled_job_ids"], []
        )
        reused = {
            job["id"]: job
            for job in document["result"]["reused_jobs_excluded_from_totals"]
        }
        self.assertEqual(reused[202]["log"]["status"], "not_selected_attempt")
        self.assertNotIn("WARNING inaccessible_input", completed.stderr)

    def test_all_attempts_respects_explicit_attempt_bound(self) -> None:
        completed, document = self.run_helper(
            "complete",
            9001,
            "--all-attempts",
            "--max-attempts",
            "1",
            "--per-page",
            "2",
            "--max-pages",
            "5",
            "--log-job-id",
            "202",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        attempt = document["provenance"]["attempt"]
        self.assertEqual(attempt["selection"], "bounded_all")
        self.assertEqual(attempt["selected"], [2])
        self.assertEqual(
            attempt["range"],
            {"start": 2, "end": 2, "max_attempts": 1, "complete": False},
        )
        self.assertEqual(document["coverage"]["status"], "partial")
        self.assertEqual(document["coverage"]["attempts_requested"], 2)
        self.assertEqual(document["coverage"]["attempts_examined"], 1)
        self.assertFalse(document["coverage"]["attempt_range_complete"])
        self.assertFalse(document["result"]["jobs_api"]["complete"])
        self.assertFalse(document["result"]["jobs_api"]["attempt_range_complete"])
        rounded = document["result"]["billing"]["rounded_job_minutes"]
        self.assertEqual(rounded["status"], "partial")
        self.assertEqual(
            rounded["interpretation"], "observed_subtotal_not_complete_run_total"
        )
        log_requests = document["result"]["log_requests"]
        self.assertEqual(log_requests["fulfilled_job_ids"], [])
        self.assertEqual(log_requests["unfulfilled_job_ids"], [202])
        self.assertEqual(log_requests["out_of_selected_attempt_job_ids"], [202])
        self.assertIn("WARNING inaccessible_input", completed.stderr)
        self.assertIn("WARNING degraded_analysis", completed.stderr)

    def test_single_attempt_reused_log_request_is_unfulfilled(self) -> None:
        completed, document = self.run_helper(
            "complete",
            9001,
            "--attempt",
            "2",
            "--per-page",
            "2",
            "--max-pages",
            "5",
            "--log-job-id",
            "202",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        reused = document["result"]["reused_jobs_excluded_from_totals"][0]
        self.assertEqual(reused["id"], 202)
        self.assertEqual(reused["log"]["status"], "not_selected_attempt")
        log_requests = document["result"]["log_requests"]
        self.assertEqual(log_requests["probed_job_ids"], [])
        self.assertEqual(log_requests["fulfilled_job_ids"], [])
        self.assertEqual(log_requests["unfulfilled_job_ids"], [202])
        self.assertEqual(log_requests["out_of_selected_attempt_job_ids"], [202])
        self.assertEqual(document["coverage"]["status"], "partial")
        self.assertIn("WARNING inaccessible_input", completed.stderr)

    def test_invalid_invocation_is_structured(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--repository",
                "https://github.com/octo/example",
                "--run-id",
                "9001",
            ],
            check=False,
            capture_output=True,
            text=True,
            cwd=TOOLKIT_ROOT,
        )
        document = json.loads(completed.stdout)

        self.assertEqual(completed.returncode, 2)
        self.assertEqual(document["diagnostics"][0]["code"], "invalid_input")
        self.assertEqual(document["coverage"]["status"], "unavailable")
        self.assertIn("ERROR invalid_input", completed.stderr)

    def test_rejects_output_outside_current_directory_before_calling_gh(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--repository",
                "octo/example",
                "--run-id",
                "9001",
                "--output",
                "../run.json",
            ],
            check=False,
            capture_output=True,
            text=True,
            cwd=TOOLKIT_ROOT,
            env={"PATH": os.environ.get("PATH", "")},
        )
        document = json.loads(completed.stdout)

        self.assertEqual(completed.returncode, 2)
        self.assertEqual(document["diagnostics"][0]["code"], "invalid_input")


if __name__ == "__main__":
    unittest.main()
