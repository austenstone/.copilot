#!/usr/bin/env python3
"""Collect bounded GitHub Actions evidence for one or all run attempts."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "actions-helper/v1"
TOOL_NAME = "collect-run-data"
API_VERSION = "2022-11-28"
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
TERMINAL_STATUSES = {"completed"}
NO_LOG_CONCLUSIONS = {"skipped"}


class InvocationError(Exception):
    pass


class CollectionError(Exception):
    def __init__(self, exit_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.code = code
        self.message = message


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise InvocationError(message)


def diagnostic(
    level: str, code: str, message: str, metadata: dict[str, Any] | None = None
) -> dict[str, Any]:
    value: dict[str, Any] = {"level": level, "code": code, "message": message}
    if metadata:
        value["metadata"] = metadata
    return value


def envelope(
    scope: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
    coverage: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    diagnostics: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "scope": scope or {},
        "provenance": provenance or {},
        "coverage": coverage
        or {
            "status": "unavailable",
            "requested": 0,
            "examined": 0,
            "limitations": [],
        },
        "result": result or {},
        "diagnostics": diagnostics or [],
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = JsonArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, help="Exact OWNER/REPO")
    parser.add_argument("--run-id", required=True, type=int)
    attempt = parser.add_mutually_exclusive_group()
    attempt.add_argument("--attempt", type=int)
    attempt.add_argument(
        "--all-attempts",
        action="store_true",
        help="Collect the latest bounded range of attempts",
    )
    parser.add_argument("--max-attempts", type=int, default=20)
    parser.add_argument(
        "--ref",
        help="Optional expected execution ref; never treated as workflow-definition proof",
    )
    parser.add_argument("--per-page", type=int, default=100)
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument(
        "--skip-log-checks",
        action="store_true",
        help="Compatibility flag; logs are not requested by default",
    )
    parser.add_argument(
        "--log-job-id",
        action="append",
        type=int,
        default=[],
        help="Probe log availability for this selected job ID; repeat as needed",
    )
    parser.add_argument("--max-log-checks", type=int, default=10)
    parser.add_argument("--output")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)

    if not REPOSITORY.fullmatch(args.repository):
        raise InvocationError("--repository must be an exact OWNER/REPO slug")
    if args.run_id <= 0:
        raise InvocationError("--run-id must be a positive integer")
    if args.attempt is not None and args.attempt <= 0:
        raise InvocationError("--attempt must be a positive integer")
    if not 1 <= args.per_page <= 100:
        raise InvocationError("--per-page must be between 1 and 100")
    if not 1 <= args.max_pages <= 100:
        raise InvocationError("--max-pages must be between 1 and 100")
    if not 1 <= args.max_attempts <= 100:
        raise InvocationError("--max-attempts must be between 1 and 100")
    if not 1 <= args.timeout_seconds <= 300:
        raise InvocationError("--timeout-seconds must be between 1 and 300")
    if not 1 <= args.max_log_checks <= 25:
        raise InvocationError("--max-log-checks must be between 1 and 25")
    if any(job_id <= 0 for job_id in args.log_job_id):
        raise InvocationError("--log-job-id values must be positive integers")
    args.log_job_id = list(dict.fromkeys(args.log_job_id))
    if len(args.log_job_id) > args.max_log_checks:
        raise InvocationError(
            "--log-job-id count exceeds the explicit --max-log-checks bound"
        )
    if args.skip_log_checks and args.log_job_id:
        raise InvocationError("--skip-log-checks cannot be combined with --log-job-id")
    if args.output:
        safe_output_path(args.output)
    return args


def safe_output_path(value: str) -> Path:
    cwd = Path.cwd().resolve()
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = cwd / candidate
    candidate = candidate.resolve()
    try:
        candidate.relative_to(cwd)
    except ValueError as exc:
        raise InvocationError("--output must remain below the current directory") from exc
    if candidate == cwd:
        raise InvocationError("--output must name a file below the current directory")
    return candidate


def emit(document: dict[str, Any], pretty: bool, output: str | None = None) -> None:
    text = json.dumps(
        document,
        indent=2 if pretty else None,
        sort_keys=pretty,
        separators=None if pretty else (",", ":"),
    )
    if output:
        destination = safe_output_path(output)
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(f"{text}\n", encoding="utf-8")
        except OSError as exc:
            raise CollectionError(
                3,
                "inaccessible_input",
                "The requested output destination could not be written",
            ) from exc
    else:
        print(text)


def emit_diagnostics(document: dict[str, Any]) -> None:
    for item in document.get("diagnostics", []):
        if item.get("level") not in {"warning", "error"}:
            continue
        level = str(item.get("level", "error")).upper()
        code = str(item.get("code", "unknown"))
        message = str(item.get("message", "No diagnostic message"))
        print(f"{level} {code}: {message}", file=sys.stderr)


def run_command(
    command: list[str], timeout_seconds: int
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=os.environ.copy(),
        )
    except FileNotFoundError as exc:
        raise CollectionError(
            4, "missing_executable", "gh is required but was not found"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise CollectionError(
            3, "timeout", "A bounded gh command timed out"
        ) from exc


def gh_version(timeout_seconds: int) -> str:
    completed = run_command(["gh", "--version"], timeout_seconds)
    if completed.returncode != 0:
        raise CollectionError(
            4, "missing_executable", "gh could not report its version"
        )
    first_line = completed.stdout.splitlines()
    return first_line[0].strip() if first_line else "unknown"


def classify_api_failure(returncode: int, stderr: str) -> CollectionError:
    lowered = stderr.lower()
    if "rate limit" in lowered or "secondary rate" in lowered:
        return CollectionError(
            4, "rate_limiting", "GitHub API rate limiting prevented collection"
        )
    if any(value in lowered for value in ("401", "403", "authentication", "oauth")):
        return CollectionError(
            4,
            "online_failure",
            "Authenticated GitHub.com access was unavailable or insufficient",
        )
    if "404" in lowered or "not found" in lowered:
        return CollectionError(
            3, "inaccessible_input", "The requested GitHub.com input was not found"
        )
    return CollectionError(
        3,
        "online_failure",
        f"GitHub.com API collection failed with gh exit {returncode}",
    )


def gh_api_json(endpoint: str, timeout_seconds: int) -> Any:
    command = [
        "gh",
        "api",
        "--hostname",
        "github.com",
        "--method",
        "GET",
        "-H",
        "Accept: application/vnd.github+json",
        "-H",
        f"X-GitHub-Api-Version: {API_VERSION}",
        endpoint,
    ]
    completed = run_command(command, timeout_seconds)
    if completed.returncode != 0:
        raise classify_api_failure(completed.returncode, completed.stderr)
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise CollectionError(
            5, "tool_crash", "gh returned invalid JSON for a GitHub.com API response"
        ) from exc


def probe_job_log(endpoint: str, timeout_seconds: int) -> tuple[str, str | None]:
    command = [
        "gh",
        "api",
        "--hostname",
        "github.com",
        "--method",
        "GET",
        "--silent",
        "-H",
        "Accept: application/vnd.github+json",
        "-H",
        f"X-GitHub-Api-Version: {API_VERSION}",
        endpoint,
    ]
    try:
        completed = run_command(command, timeout_seconds)
    except CollectionError as exc:
        return "unavailable", exc.code
    if completed.returncode == 0:
        return "available", None
    lowered = completed.stderr.lower()
    if "404" in lowered or "not found" in lowered:
        return "missing", "missing_logs"
    if "rate limit" in lowered:
        return "unavailable", "rate_limiting"
    return "inaccessible", "inaccessible_input"


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def seconds_between(start: Any, end: Any) -> int | None:
    parsed_start = parse_timestamp(start)
    parsed_end = parse_timestamp(end)
    if parsed_start is None or parsed_end is None:
        return None
    seconds = int((parsed_end - parsed_start).total_seconds())
    return seconds if seconds >= 0 else None


def full_name(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    name = value.get("full_name")
    return name if isinstance(name, str) else None


def lifecycle(status: Any, conclusion: Any, completed_at: Any) -> str:
    if conclusion == "cancelled":
        return "cancelled"
    if conclusion == "skipped":
        return "skipped"
    if status not in TERMINAL_STATUSES or completed_at is None:
        return "unfinished"
    if conclusion is None:
        return "completed_with_null_conclusion"
    return "finished"


def run_lifecycle(status: Any, conclusion: Any) -> str:
    if conclusion == "cancelled":
        return "cancelled"
    if conclusion == "skipped":
        return "skipped"
    if status not in TERMINAL_STATUSES:
        return "unfinished"
    if conclusion is None:
        return "completed_with_null_conclusion"
    return "finished"


def step_evidence(step: Any) -> dict[str, Any]:
    if not isinstance(step, dict):
        return {
            "number": None,
            "name": None,
            "status": None,
            "conclusion": None,
            "lifecycle": "unavailable",
            "started_at": None,
            "completed_at": None,
            "duration_seconds": None,
        }
    return {
        "number": step.get("number"),
        "name": step.get("name"),
        "status": step.get("status"),
        "conclusion": step.get("conclusion"),
        "lifecycle": lifecycle(
            step.get("status"), step.get("conclusion"), step.get("completed_at")
        ),
        "started_at": step.get("started_at"),
        "completed_at": step.get("completed_at"),
        "duration_seconds": seconds_between(
            step.get("started_at"), step.get("completed_at")
        ),
    }


def collect_jobs(
    repository: str,
    run_id: int,
    attempt: int,
    per_page: int,
    max_pages: int,
    timeout_seconds: int,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[str], list[dict[str, Any]]]:
    unique_jobs: dict[int, dict[str, Any]] = {}
    duplicate_ids: set[int] = set()
    total_count: int | None = None
    pages_fetched = 0
    raw_items = 0
    limitations: list[str] = []
    endpoints: list[dict[str, Any]] = []

    for page in range(1, max_pages + 1):
        endpoint = (
            f"repos/{repository}/actions/runs/{run_id}/attempts/{attempt}/jobs"
            f"?per_page={per_page}&page={page}"
        )
        payload = gh_api_json(endpoint, timeout_seconds)
        endpoints.append({"kind": "jobs", "page": page, "endpoint": endpoint})
        pages_fetched += 1
        if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
            raise CollectionError(
                5, "tool_crash", "The jobs endpoint returned an unexpected JSON shape"
            )
        response_total = payload.get("total_count")
        if not isinstance(response_total, int) or response_total < 0:
            raise CollectionError(
                5, "tool_crash", "The jobs endpoint omitted a valid total_count"
            )
        if total_count is None:
            total_count = response_total
        elif total_count != response_total:
            limitations.append(
                "jobs endpoint total_count changed while pagination was in progress"
            )
            total_count = max(total_count, response_total)

        jobs = payload["jobs"]
        raw_items += len(jobs)
        for job in jobs:
            if not isinstance(job, dict) or not isinstance(job.get("id"), int):
                limitations.append("a jobs endpoint item lacked an integer job ID")
                continue
            job_id = job["id"]
            if job_id in unique_jobs:
                duplicate_ids.add(job_id)
                continue
            unique_jobs[job_id] = job

        if len(unique_jobs) >= total_count or len(jobs) < per_page:
            break

    assert total_count is not None
    if len(unique_jobs) < total_count:
        limitations.append(
            f"pagination examined {len(unique_jobs)} of {total_count} unique jobs "
            f"within the {max_pages}-page bound"
        )
    if duplicate_ids:
        limitations.append(
            "duplicate job IDs were returned across pages and counted only once"
        )

    pagination = {
        "total_count": total_count,
        "pages_fetched": pages_fetched,
        "per_page": per_page,
        "max_pages": max_pages,
        "raw_items_returned": raw_items,
        "unique_job_ids_examined": len(unique_jobs),
        "duplicate_job_ids_ignored": sorted(duplicate_ids),
        "complete": len(unique_jobs) >= total_count,
    }
    return list(unique_jobs.values()), pagination, limitations, endpoints


def job_evidence(
    job: dict[str, Any],
    repository: str,
    selected_attempt: int,
    requested_log_ids: set[int],
    probed_log_ids: set[int],
    timeout_seconds: int,
    diagnostics: list[dict[str, Any]],
    limitations: list[str],
) -> dict[str, Any]:
    status = job.get("status")
    conclusion = job.get("conclusion")
    completed_at = job.get("completed_at")
    job_lifecycle = lifecycle(status, conclusion, completed_at)
    duration_seconds = seconds_between(job.get("started_at"), completed_at)
    waiting_seconds = seconds_between(job.get("created_at"), job.get("started_at"))
    source_attempt = job.get("run_attempt")
    belongs_to_selected_attempt = source_attempt in (None, selected_attempt)
    if source_attempt is None:
        attempt_membership_basis = "attempt_endpoint_no_job_field"
    elif belongs_to_selected_attempt:
        attempt_membership_basis = "job_run_attempt"
    else:
        attempt_membership_basis = "different_job_run_attempt"

    log_endpoint = f"repos/{repository}/actions/jobs/{job['id']}/logs"
    if not belongs_to_selected_attempt:
        log = {
            "status": "not_selected_attempt",
            "endpoint": log_endpoint,
            "content_included": False,
        }
    elif job["id"] not in requested_log_ids:
        log = {
            "status": "not_requested",
            "endpoint": log_endpoint,
            "content_included": False,
        }
    elif conclusion in NO_LOG_CONCLUSIONS:
        log = {
            "status": "not_expected",
            "endpoint": log_endpoint,
            "content_included": False,
        }
    elif job_lifecycle == "unfinished":
        log = {
            "status": "not_yet_available",
            "endpoint": log_endpoint,
            "content_included": False,
        }
    elif job["id"] in probed_log_ids:
        log = {
            "status": "already_probed",
            "endpoint": log_endpoint,
            "content_included": False,
        }
    else:
        probed_log_ids.add(job["id"])
        log_status, error_code = probe_job_log(log_endpoint, timeout_seconds)
        log = {
            "status": log_status,
            "endpoint": log_endpoint,
            "content_included": False,
        }
        if error_code:
            limitations.append(f"job {job['id']} log status is {log_status}")
            diagnostics.append(
                diagnostic(
                    "warning",
                    error_code,
                    f"Job {job['id']} log evidence is {log_status}",
                    {"job_id": job["id"], "status": log_status},
                )
            )

    if belongs_to_selected_attempt and job_lifecycle in {
        "unfinished",
        "completed_with_null_conclusion",
    }:
        limitations.append(f"job {job['id']} is {job_lifecycle}")
    if (
        belongs_to_selected_attempt
        and status == "completed"
        and duration_seconds is None
        and job_lifecycle != "skipped"
    ):
        limitations.append(f"job {job['id']} has no usable completed duration")

    labels = job.get("labels")
    if not isinstance(labels, list) or not all(
        isinstance(label, str) for label in labels
    ):
        labels = []
        limitations.append(f"job {job['id']} has no usable runner labels")

    return {
        "id": job["id"],
        "run_id": job.get("run_id"),
        "run_attempt": source_attempt,
        "belongs_to_selected_attempt": belongs_to_selected_attempt,
        "attempt_membership_basis": attempt_membership_basis,
        "name": job.get("name"),
        "status": status,
        "conclusion": conclusion,
        "lifecycle": job_lifecycle,
        "created_at": job.get("created_at"),
        "started_at": job.get("started_at"),
        "completed_at": completed_at,
        "waiting_seconds": waiting_seconds,
        "duration_seconds": duration_seconds,
        "rounded_job_minutes": (
            0
            if job_lifecycle == "skipped"
            else (
                math.ceil(duration_seconds / 60)
                if duration_seconds is not None
                else None
            )
        ),
        "labels": labels,
        "runner_id": job.get("runner_id"),
        "runner_name": job.get("runner_name"),
        "runner_group_id": job.get("runner_group_id"),
        "runner_group_name": job.get("runner_group_name"),
        "html_url": job.get("html_url"),
        "steps": [step_evidence(step) for step in job.get("steps") or []],
        "log": log,
    }


def timing_summary(
    run: dict[str, Any],
    selected_jobs: list[dict[str, Any]],
    collection_complete: bool,
) -> dict[str, Any]:
    created_to_started = seconds_between(
        run.get("created_at"), run.get("run_started_at")
    )
    waiting_values = [
        job["waiting_seconds"]
        for job in selected_jobs
        if job["waiting_seconds"] is not None
    ]
    starts = [
        parse_timestamp(job["started_at"])
        for job in selected_jobs
        if parse_timestamp(job["started_at"]) is not None
    ]
    completions = [
        parse_timestamp(job["completed_at"])
        for job in selected_jobs
        if parse_timestamp(job["completed_at"]) is not None
    ]
    unfinished_ids = [
        job["id"]
        for job in selected_jobs
        if job["lifecycle"] == "unfinished"
    ]

    wall_clock_seconds = None
    wall_clock_status = "unavailable"
    if starts and completions:
        wall_clock_seconds = int((max(completions) - min(starts)).total_seconds())
        if wall_clock_seconds >= 0:
            wall_clock_status = (
                "partial"
                if unfinished_ids or not collection_complete
                else "complete"
            )
        else:
            wall_clock_seconds = None

    return {
        "run_created_to_started_elapsed": {
            "seconds": created_to_started,
            "capacity_signal": False,
            "note": (
                "Raw run created_at to run_started_at elapsed. It is not runner "
                "queue time and must not be used to infer capacity, especially for "
                "rerun attempts."
            ),
        },
        "job_waiting": {
            "status": "complete" if collection_complete else "partial",
            "interpretation": (
                "observed_subtotal_not_complete_attempt"
                if not collection_complete
                else "selected_attempt_observations"
            ),
            "observations": len(waiting_values),
            "total_seconds": sum(waiting_values),
            "max_seconds": max(waiting_values) if waiting_values else None,
            "by_job": [
                {"job_id": job["id"], "waiting_seconds": job["waiting_seconds"]}
                for job in selected_jobs
            ],
        },
        "critical_path_wall_clock": {
            "status": wall_clock_status,
            "seconds": wall_clock_seconds,
            "interpretation": (
                "observed_partial_span"
                if not collection_complete
                else "selected_attempt_job_span"
            ),
            "method": (
                "Observed span from the earliest selected-attempt job start to the "
                "latest selected-attempt job completion. The jobs API omits the needs "
                "graph, so this is a wall-clock proxy, not a reconstructed dependency "
                "critical path."
            ),
            "unfinished_job_ids": unfinished_ids,
        },
    }


def billing_summary(
    selected_jobs: list[dict[str, Any]],
    collection_complete: bool,
    complete_interpretation: str = "selected_attempt_total",
) -> dict[str, Any]:
    groups: dict[tuple[str, ...], dict[str, Any]] = {}
    jobs_without_duration: list[int] = []
    for job in selected_jobs:
        minutes = job["rounded_job_minutes"]
        if minutes is None:
            jobs_without_duration.append(job["id"])
            continue
        key = tuple(str(label) for label in job["labels"])
        group = groups.setdefault(
            key,
            {
                "labels": list(key),
                "sku": None,
                "rate_per_minute": None,
                "currency": None,
                "resolution": "unresolved",
                "job_ids": [],
                "rounded_job_minutes": 0,
            },
        )
        group["job_ids"].append(job["id"])
        group["rounded_job_minutes"] += minutes

    rounded_total = sum(
        group["rounded_job_minutes"] for group in groups.values()
    )
    return {
        "rounded_job_minutes": {
            "status": (
                "partial"
                if jobs_without_duration or not collection_complete
                else "complete"
            ),
            "total": rounded_total,
            "interpretation": (
                "observed_subtotal_not_complete_run_total"
                if not collection_complete
                else complete_interpretation
            ),
            "by_exact_runner_labels": list(groups.values()),
            "jobs_without_duration": jobs_without_duration,
            "method": (
                "Each observed selected-attempt job duration is rounded up to a whole "
                "minute. Repeated job IDs and jobs reused from another attempt are "
                "excluded from aggregate totals."
            ),
        },
        "billed_cost": {
            "status": "unavailable",
            "amount": None,
            "currency": None,
            "reason": (
                "Run/job evidence does not establish invoice charges, included-minute "
                "treatment, repository visibility billing, or a live runner rate. "
                "Exact labels are retained without inventing a SKU or rate."
            ),
        },
        "billing_truth": {
            "status": "not_collected",
            "source": None,
            "note": (
                "This bounded run attempt is timing evidence, not Actions Usage "
                "Metrics, billing-export, or invoice truth."
            ),
        },
    }


def workflow_definition_provenance(run: dict[str, Any]) -> dict[str, Any]:
    path = run.get("path")
    definition_path = path
    definition_ref = None
    if isinstance(path, str) and "@" in path:
        candidate_path, candidate_ref = path.rsplit("@", 1)
        if candidate_ref.startswith("refs/"):
            definition_path = candidate_path
            definition_ref = candidate_ref
    return {
        "workflow_id": run.get("workflow_id"),
        "path_from_run": path,
        "definition_path": definition_path,
        "definition_ref": definition_ref,
        "definition_sha": None,
        "status": "ref_observed_from_run" if definition_ref else "path_only",
        "head_sha_is_definition_proof": False,
        "note": (
            "The run API path is authoritative only for the value it returns. "
            "head_sha/head_branch describe run source provenance and are not asserted "
            "as the executed workflow-definition ref or SHA."
        ),
    }


def ref_provenance(requested_ref: str | None, run: dict[str, Any]) -> dict[str, Any]:
    head_branch = run.get("head_branch")
    head_sha = run.get("head_sha")
    relationship = None
    if requested_ref is not None:
        if requested_ref == head_sha:
            relationship = "matches_head_sha"
        elif requested_ref == head_branch or requested_ref == f"refs/heads/{head_branch}":
            relationship = "matches_head_branch"
        else:
            relationship = "not_verifiable_from_run_fields"
    return {
        "requested_ref": requested_ref,
        "head_branch": head_branch,
        "head_sha": head_sha,
        "head_repository": full_name(run.get("head_repository")),
        "relationship": relationship,
        "treated_as_workflow_definition_ref": False,
    }


def run_evidence(run: dict[str, Any], attempt: int) -> dict[str, Any]:
    return {
        "id": run.get("id"),
        "attempt": attempt,
        "name": run.get("name"),
        "display_title": run.get("display_title"),
        "event": run.get("event"),
        "status": run.get("status"),
        "conclusion": run.get("conclusion"),
        "lifecycle": run_lifecycle(run.get("status"), run.get("conclusion")),
        "created_at": run.get("created_at"),
        "run_started_at": run.get("run_started_at"),
        "updated_at": run.get("updated_at"),
        "head_branch": run.get("head_branch"),
        "head_sha": run.get("head_sha"),
        "workflow_id": run.get("workflow_id"),
        "path": run.get("path"),
        "html_url": run.get("html_url"),
    }


def collect_attempt(
    args: argparse.Namespace,
    attempt: int,
    requested_log_ids: set[int],
    probed_log_ids: set[int],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    diagnostics: list[dict[str, Any]] = []
    limitations: list[str] = []
    endpoint = f"repos/{args.repository}/actions/runs/{args.run_id}/attempts/{attempt}"
    attempt_run = gh_api_json(endpoint, args.timeout_seconds)
    if not isinstance(attempt_run, dict):
        raise CollectionError(
            5, "tool_crash", "The run-attempt endpoint returned an unexpected JSON shape"
        )
    if attempt_run.get("id") != args.run_id or attempt_run.get("run_attempt") != attempt:
        raise CollectionError(
            5, "tool_crash", "The run-attempt response did not match the selected attempt"
        )
    returned_repository = full_name(attempt_run.get("repository"))
    if (
        returned_repository is None
        or returned_repository.casefold() != args.repository.casefold()
    ):
        raise CollectionError(
            5, "tool_crash", "The run-attempt response repository did not match"
        )

    raw_jobs, pagination, page_limitations, job_endpoints = collect_jobs(
        args.repository,
        args.run_id,
        attempt,
        args.per_page,
        args.max_pages,
        args.timeout_seconds,
    )
    limitations.extend(page_limitations)
    for raw_job in raw_jobs:
        job_run_id = raw_job.get("run_id")
        if job_run_id is not None and job_run_id != args.run_id:
            raise CollectionError(
                5, "tool_crash", f"Job {raw_job['id']} did not match the requested run ID"
            )
        if job_run_id is None:
            limitations.append(f"job {raw_job['id']} omitted run_id")

    jobs = [
        job_evidence(
            job,
            args.repository,
            attempt,
            requested_log_ids,
            probed_log_ids,
            args.timeout_seconds,
            diagnostics,
            limitations,
        )
        for job in raw_jobs
    ]
    selected_jobs = [job for job in jobs if job["belongs_to_selected_attempt"]]
    reused_jobs = [job for job in jobs if not job["belongs_to_selected_attempt"]]
    if reused_jobs:
        diagnostics.append(
            diagnostic(
                "info",
                "degraded_analysis",
                "Jobs originating in another attempt were excluded from this "
                "attempt's timing and rounded-minute totals",
                {"attempt": attempt, "job_ids": [job["id"] for job in reused_jobs]},
            )
        )
    if not pagination["complete"]:
        diagnostics.append(
            diagnostic(
                "warning",
                "degraded_analysis",
                f"Attempt {attempt} pagination did not cover total_count",
                {
                    "attempt": attempt,
                    "total_count": pagination["total_count"],
                    "examined": pagination["unique_job_ids_examined"],
                },
            )
        )
    if pagination["duplicate_job_ids_ignored"]:
        diagnostics.append(
            diagnostic(
                "warning",
                "degraded_analysis",
                f"Attempt {attempt} duplicate job IDs were ignored",
                {"job_ids": pagination["duplicate_job_ids_ignored"]},
            )
        )

    ref_details = ref_provenance(args.ref, attempt_run)
    if (
        args.ref is not None
        and ref_details["relationship"] == "not_verifiable_from_run_fields"
    ):
        limitations.append(
            f"attempt {attempt} could not match the requested ref to head_branch "
            "or head_sha; it was not treated as workflow-definition provenance"
        )

    attempt_coverage = {
        "status": "partial" if limitations else "complete",
        "requested": pagination["total_count"],
        "examined": pagination["unique_job_ids_examined"],
        "limitations": list(dict.fromkeys(limitations)),
    }
    record = {
        "attempt": attempt,
        "provenance": {
            "run_id": args.run_id,
            "repository": returned_repository,
            "ref": ref_details,
            "workflow_definition": workflow_definition_provenance(attempt_run),
            "endpoints": [
                {"kind": "attempt", "endpoint": endpoint},
                *job_endpoints,
            ],
        },
        "coverage": attempt_coverage,
        "run": run_evidence(attempt_run, attempt),
        "jobs_api": pagination,
        "selected_job_ids": [job["id"] for job in selected_jobs],
        "reused_job_ids": [job["id"] for job in reused_jobs],
        "timing": timing_summary(attempt_run, selected_jobs, pagination["complete"]),
        "billing": billing_summary(selected_jobs, pagination["complete"]),
        "diagnostics": diagnostics,
    }
    return record, selected_jobs, reused_jobs


def run_result(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    requested_log_ids = set() if args.skip_log_checks else set(args.log_job_id)
    scope = {
        "repository": args.repository,
        "run_id": args.run_id,
        "attempt": "all" if args.all_attempts else args.attempt,
        "ref": args.ref,
        "bounds": {
            "per_page": args.per_page,
            "max_pages_per_attempt": args.max_pages,
            "max_attempts": args.max_attempts,
            "timeout_seconds_per_command": args.timeout_seconds,
            "log_job_ids": sorted(requested_log_ids),
            "max_log_checks": args.max_log_checks,
        },
    }
    version = gh_version(args.timeout_seconds)
    run_endpoint = f"repos/{args.repository}/actions/runs/{args.run_id}"
    run = gh_api_json(run_endpoint, args.timeout_seconds)
    if not isinstance(run, dict):
        raise CollectionError(
            5, "tool_crash", "The workflow-run endpoint returned an unexpected JSON shape"
        )
    returned_repository = full_name(run.get("repository"))
    if run.get("id") != args.run_id:
        raise CollectionError(
            5, "tool_crash", "The workflow-run response did not match the requested run ID"
        )
    if (
        returned_repository is None
        or returned_repository.casefold() != args.repository.casefold()
    ):
        raise CollectionError(
            5, "tool_crash", "The workflow-run response repository did not match"
        )
    latest_attempt = run.get("run_attempt")
    if not isinstance(latest_attempt, int) or latest_attempt <= 0:
        raise CollectionError(
            5, "tool_crash", "The workflow-run response omitted a valid run_attempt"
        )
    if args.attempt is not None and args.attempt > latest_attempt:
        raise CollectionError(
            3,
            "inaccessible_input",
            f"Attempt {args.attempt} exceeds the latest run attempt {latest_attempt}",
        )

    attempt_start = (
        max(1, latest_attempt - args.max_attempts + 1)
        if args.all_attempts
        else (args.attempt if args.attempt is not None else latest_attempt)
    )
    attempts = (
        list(range(attempt_start, latest_attempt + 1))
        if args.all_attempts
        else [attempt_start]
    )
    attempts_truncated = args.all_attempts and attempt_start > 1
    records: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    limitations: list[str] = []
    selected_by_id: dict[int, dict[str, Any]] = {}
    reused_jobs: list[dict[str, Any]] = []
    cross_attempt_duplicates: set[int] = set()
    probed_log_ids: set[int] = set()

    if attempts_truncated:
        limitations.append(
            f"latest run attempt is {latest_attempt}; collected bounded attempt "
            f"range {attempt_start}-{latest_attempt} within max_attempts="
            f"{args.max_attempts}"
        )
        diagnostics.append(
            diagnostic(
                "warning",
                "degraded_analysis",
                "The all-attempts request was truncated to the latest bounded range",
                {
                    "latest_attempt": latest_attempt,
                    "range_start": attempt_start,
                    "range_end": latest_attempt,
                    "max_attempts": args.max_attempts,
                },
            )
        )

    for attempt in attempts:
        record, selected_jobs, attempt_reused = collect_attempt(
            args, attempt, requested_log_ids, probed_log_ids
        )
        records.append(record)
        diagnostics.extend(record["diagnostics"])
        limitations.extend(
            f"attempt {attempt}: {item}" for item in record["coverage"]["limitations"]
        )
        reused_jobs.extend(attempt_reused)
        counted_ids: list[int] = []
        for job in selected_jobs:
            if job["id"] in selected_by_id:
                cross_attempt_duplicates.add(job["id"])
                continue
            selected_by_id[job["id"]] = job
            counted_ids.append(job["id"])
        record["counted_job_ids"] = counted_ids

    cross_attempt_duplicates.update(
        job["id"] for job in reused_jobs if job["id"] in selected_by_id
    )
    if cross_attempt_duplicates:
        limitations.append(
            "job IDs repeated across attempt responses were counted only once: "
            + ", ".join(str(value) for value in sorted(cross_attempt_duplicates))
        )
        diagnostics.append(
            diagnostic(
                "warning",
                "degraded_analysis",
                "Repeated job IDs across attempts were ignored in aggregate totals",
                {"job_ids": sorted(cross_attempt_duplicates)},
            )
        )

    selected_job_ids = set(selected_by_id)
    reused_job_ids = {job["id"] for job in reused_jobs}
    fulfilled_log_job_ids = requested_log_ids & probed_log_ids
    unfulfilled_log_job_ids = requested_log_ids - fulfilled_log_job_ids
    out_of_selected_log_job_ids = (
        unfulfilled_log_job_ids & reused_job_ids
    ) - selected_job_ids
    selected_unprobed_log_job_ids = unfulfilled_log_job_ids & selected_job_ids
    absent_log_job_ids = unfulfilled_log_job_ids - selected_job_ids - reused_job_ids
    if unfulfilled_log_job_ids:
        limitations.append(
            "requested log job IDs were not selected and probed: "
            + ", ".join(str(value) for value in sorted(unfulfilled_log_job_ids))
        )
        diagnostics.append(
            diagnostic(
                "warning",
                "inaccessible_input",
                "Some requested job logs were not selected and probed",
                {
                    "unfulfilled_job_ids": sorted(unfulfilled_log_job_ids),
                    "out_of_selected_attempt_job_ids": sorted(
                        out_of_selected_log_job_ids
                    ),
                    "selected_but_not_probed_job_ids": sorted(
                        selected_unprobed_log_job_ids
                    ),
                    "absent_job_ids": sorted(absent_log_job_ids),
                },
            )
        )

    selected_jobs = list(selected_by_id.values())
    jobs_collection_complete = not attempts_truncated and all(
        record["jobs_api"]["complete"] for record in records
    )
    requested_count = sum(record["coverage"]["requested"] for record in records)
    examined_count = sum(record["coverage"]["examined"] for record in records)
    coverage = {
        "status": "partial" if limitations else "complete",
        "requested": requested_count,
        "examined": examined_count,
        "attempts_requested": latest_attempt if args.all_attempts else 1,
        "attempts_examined": len(attempts),
        "attempt_range_complete": not attempts_truncated,
        "limitations": list(dict.fromkeys(limitations)),
    }
    conclusion_counts = Counter(
        "null" if job["conclusion"] is None else str(job["conclusion"])
        for job in selected_jobs
    )
    lifecycle_counts = Counter(job["lifecycle"] for job in selected_jobs)
    log_counts = Counter(job["log"]["status"] for job in selected_jobs)
    selection = (
        ("bounded_all" if attempts_truncated else "all")
        if args.all_attempts
        else ("explicit" if args.attempt is not None else "latest")
    )
    single = not args.all_attempts
    provenance = {
        "host": "github.com",
        "gh_version": version,
        "api_version": API_VERSION,
        "repository_requested": args.repository,
        "repository_returned": returned_repository,
        "run_id_requested": args.run_id,
        "run_id_returned": run.get("id"),
        "attempt": {
            "requested": "all" if args.all_attempts else args.attempt,
            "selected": attempts if args.all_attempts else attempts[0],
            "latest": latest_attempt,
            "selection": selection,
            "range": {
                "start": attempt_start,
                "end": latest_attempt,
                "max_attempts": args.max_attempts,
                "complete": not attempts_truncated,
            },
            "per_attempt": [
                {
                    "attempt": record["attempt"],
                    "coverage": record["coverage"],
                    "provenance": record["provenance"],
                }
                for record in records
            ],
        },
        "ref": records[0]["provenance"]["ref"] if single else {"status": "per_attempt"},
        "workflow_definition": (
            records[0]["provenance"]["workflow_definition"]
            if single
            else {"status": "per_attempt"}
        ),
        "endpoints": [
            {"kind": "run", "endpoint": run_endpoint},
            *[
                endpoint
                for record in records
                for endpoint in record["provenance"]["endpoints"]
            ],
        ],
    }
    result = {
        "evidence": {
            "grade": "Sampled",
            "kind": "bounded_run_attempts" if args.all_attempts else "bounded_run_attempt",
            "claim_limit": (
                "Supports observations about only the collected run attempt(s). "
                "It is not repository frequency, usage, or billing truth."
            ),
        },
        "run": records[0]["run"] if single else run_evidence(run, latest_attempt),
        "attempts": records,
        "jobs_api": (
            records[0]["jobs_api"]
            if single
            else {
                "mode": "per_attempt",
                "total_count": requested_count,
                "unique_job_ids_counted": len(selected_jobs),
                "complete": jobs_collection_complete,
                "attempt_range_complete": not attempts_truncated,
            }
        ),
        "jobs": selected_jobs,
        "reused_jobs_excluded_from_totals": reused_jobs,
        "log_requests": {
            "requested_job_ids": sorted(requested_log_ids),
            "probed_job_ids": sorted(probed_log_ids),
            "fulfilled_job_ids": sorted(fulfilled_log_job_ids),
            "unfulfilled_job_ids": sorted(unfulfilled_log_job_ids),
            "out_of_selected_attempt_job_ids": sorted(
                out_of_selected_log_job_ids
            ),
            "selected_but_not_probed_job_ids": sorted(
                selected_unprobed_log_job_ids
            ),
            "absent_job_ids": sorted(absent_log_job_ids),
        },
        "summary": {
            "selected_attempt_job_ids": [job["id"] for job in selected_jobs],
            "reused_job_ids": sorted({job["id"] for job in reused_jobs}),
            "cross_attempt_duplicate_job_ids_ignored": sorted(
                cross_attempt_duplicates
            ),
            "conclusions": dict(sorted(conclusion_counts.items())),
            "lifecycles": dict(sorted(lifecycle_counts.items())),
            "logs": dict(sorted(log_counts.items())),
        },
        "timing": (
            records[0]["timing"]
            if single
            else {
                "mode": "per_attempt",
                "aggregate_wall_clock": {
                    "status": "unavailable",
                    "seconds": None,
                    "reason": "Repeated attempts are separate execution spans.",
                },
                "attempts": [
                    {"attempt": record["attempt"], **record["timing"]}
                    for record in records
                ],
            }
        ),
        "billing": billing_summary(
            selected_jobs,
            jobs_collection_complete,
            "all_collected_attempts_total" if args.all_attempts else "selected_attempt_total",
        ),
    }
    return envelope(scope, provenance, coverage, result, diagnostics), 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    args: argparse.Namespace | None = None
    try:
        args = parse_args(argv)
        document, exit_code = run_result(args)
        emit_diagnostics(document)
        emit(document, args.pretty, args.output)
        return exit_code
    except InvocationError as exc:
        document = envelope(
            diagnostics=[diagnostic("error", "invalid_input", str(exc))]
        )
        emit_diagnostics(document)
        print(json.dumps(document, separators=(",", ":")))
        return 2
    except CollectionError as exc:
        scope = {}
        if args is not None:
            scope = {
                "repository": args.repository,
                "run_id": args.run_id,
                "attempt": "all" if args.all_attempts else args.attempt,
                "ref": args.ref,
            }
        document = envelope(
            scope=scope,
            diagnostics=[diagnostic("error", exc.code, exc.message)],
        )
        emit_diagnostics(document)
        try:
            emit(document, args.pretty if args else False, args.output if args else None)
        except (InvocationError, CollectionError):
            print(json.dumps(document, separators=(",", ":")))
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
