#!/usr/bin/env python3
"""Run bounded actionlint and zizmor scans with a stable JSON envelope."""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path, PurePosixPath
from typing import Any

SCHEMA_VERSION = "actions-helper/v1"
TOOL_NAME = "scan-workflows"
DEFAULT_TIMEOUT_SECONDS = 120.0
VERSION_TIMEOUT_SECONDS = 10.0
MAX_WORKFLOWS = 500
MAX_ZIZMOR_INPUTS = 2_000
MAX_ARCHIVE_BYTES = 50 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 50_000
MAX_EXTRACTED_FILES = 2_000
MAX_EXTRACTED_BYTES = 100 * 1024 * 1024
MAX_STDERR_CHARS = 8_000
SKIPPED_NETWORK_AUDITS = [
    "impostor-commit",
    "ref-confusion",
    "known-vulnerable-actions",
    "stale-action-refs",
]
REPOSITORY = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/"
    r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,99})$"
)
SHELLCHECK_SEVERITY = re.compile(
    r"\b(SC\d{4})\b(?::|\s)+(error|warning|info|style)\b", re.IGNORECASE
)
SHELLCHECK_HYGIENE_CODES = {
    "SC2001",
    "SC2002",
    "SC2006",
    "SC2010",
    "SC2116",
    "SC2126",
}
ONLINE_FAILURE_MARKERS = (
    "no audit was performed",
    "couldn't list tags",
    "couldn't list branches",
    "could not list tags",
    "could not list branches",
    "can't fetch remote repository",
    "failed to fetch",
    "network error",
    "api.github.com",
)
NO_INPUT_MARKERS = ("no inputs collected", "collected 0 inputs")


class InvocationError(Exception):
    pass


class StructuredParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise InvocationError(message)


def empty_envelope() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "scope": {},
        "provenance": {"tools": {}},
        "coverage": {
            "status": "unavailable",
            "requested": 0,
            "examined": 0,
            "limitations": [],
        },
        "result": {
            "inputs": [],
            "actionlint": {
                "status": "not_run",
                "findings": [],
                "requested": 0,
                "examined": 0,
            },
            "zizmor": {
                "status": "not_run",
                "findings": [],
                "requested": 0,
                "examined": 0,
            },
            "skipped_network_audits": [],
            "policy_checks": [
                {
                    "name": name,
                    "status": "not_checked",
                    "reason": "not available to the workflow scanner",
                }
                for name in (
                    "organization allowed-actions policy",
                    "workflow-file rulesets and CODEOWNERS enforcement",
                    "cloud OIDC trust policy",
                    "self-hosted runner isolation policy",
                )
            ],
        },
        "diagnostics": [],
    }


def add_diagnostic(
    envelope: dict[str, Any],
    level: str,
    code: str,
    message: str,
    **metadata: Any,
) -> None:
    diagnostic = {"level": level, "code": code, "message": message}
    if metadata:
        diagnostic["metadata"] = metadata
    envelope["diagnostics"].append(diagnostic)


def add_limitation(envelope: dict[str, Any], limitation: str) -> None:
    limitations = envelope["coverage"]["limitations"]
    if limitation not in limitations:
        limitations.append(limitation)


def redact(text: str) -> str:
    value = text
    for name in ("GH_TOKEN", "GITHUB_TOKEN"):
        secret = os.environ.get(name)
        if secret:
            value = value.replace(secret, "[REDACTED]")
    value = re.sub(
        r"(?i)(authorization:\s*(?:bearer|token)\s+)\S+", r"\1[REDACTED]", value
    )
    if len(value) > MAX_STDERR_CHARS:
        value = value[:MAX_STDERR_CHARS] + "\n[stderr truncated]"
    return value.strip()


def safe_command(command: list[str]) -> list[str]:
    return [Path(command[0]).name, *command[1:]]


def run_command(
    command: list[str],
    *,
    cwd: Path,
    timeout: float,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        return {
            "command": safe_command(command),
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": redact(completed.stderr),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else exc.stdout
        stderr = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else exc.stderr
        return {
            "command": safe_command(command),
            "exit_code": None,
            "stdout": stdout or "",
            "stderr": redact(stderr or ""),
            "timed_out": True,
        }


def executable_details(name: str, version_args: list[str], cwd: Path) -> dict[str, Any]:
    executable = shutil.which(name)
    if not executable:
        return {"available": False, "executable": None, "version": None}
    attempt = run_command(
        [executable, *version_args], cwd=cwd, timeout=VERSION_TIMEOUT_SECONDS
    )
    lines = [
        line.strip()
        for line in (attempt["stdout"] or attempt["stderr"]).splitlines()
        if line.strip()
    ]
    version_line = next(
        (line for line in lines if line.lower().startswith("version:")),
        lines[0] if lines else "unknown",
    )
    return {
        "available": True,
        "executable": executable,
        "version": version_line,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = StructuredParser(add_help=True)
    parser.add_argument("--path")
    parser.add_argument("--repository")
    parser.add_argument("--ref")
    parser.add_argument("--output")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument(
        "--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS
    )
    return parser


def validate_args(args: argparse.Namespace) -> None:
    if bool(args.path) == bool(args.repository):
        raise InvocationError("provide exactly one of --path or --repository")
    if args.ref and not args.repository:
        raise InvocationError("--ref requires --repository")
    if args.repository and not REPOSITORY.fullmatch(args.repository):
        raise InvocationError("--repository must be an exact OWNER/REPO slug")
    if args.ref and (
        len(args.ref) > 255
        or any(character.isspace() or ord(character) < 32 for character in args.ref)
    ):
        raise InvocationError("--ref contains unsupported characters")
    if not 0.05 <= args.timeout_seconds <= 600:
        raise InvocationError("--timeout-seconds must be between 0.05 and 600")


def output_path(raw_path: str | None, cwd: Path) -> Path | None:
    if raw_path is None:
        return None
    candidate = (cwd / raw_path).resolve() if not Path(raw_path).is_absolute() else Path(raw_path).resolve()
    try:
        candidate.relative_to(cwd.resolve())
    except ValueError as exc:
        raise InvocationError("--output must resolve below the current working directory") from exc
    if candidate == cwd.resolve():
        raise InvocationError("--output must name a file")
    return candidate


def repository_root(path: Path) -> Path:
    if path.is_dir() and (path / ".github/workflows").is_dir():
        return path
    start = path if path.is_dir() else path.parent
    for candidate in (start, *start.parents):
        workflows = candidate / ".github/workflows"
        if workflows.is_dir():
            try:
                path.resolve().relative_to(workflows.resolve())
                return candidate
            except ValueError:
                continue
    return start


def discover_workflows(path: Path) -> tuple[Path, list[Path], Path]:
    resolved = path.resolve()
    if not resolved.exists():
        raise FileNotFoundError(str(resolved))
    root = repository_root(resolved)
    if resolved.is_file():
        files = [resolved] if resolved.suffix.lower() in {".yml", ".yaml"} else []
        return root, files, resolved
    workflow_root = (
        resolved / ".github/workflows"
        if (resolved / ".github/workflows").is_dir()
        else resolved
    )
    files = sorted(
        file.resolve()
        for file in workflow_root.rglob("*")
        if file.is_file() and file.suffix.lower() in {".yml", ".yaml"}
    )
    return root, files, workflow_root


def relative_display(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def find_configs(root: Path, names: tuple[str, ...]) -> list[str]:
    return [
        name
        for name in names
        if (root / name).is_file()
    ]


def parse_json_array(attempt: dict[str, Any]) -> list[Any] | None:
    try:
        value = json.loads(attempt["stdout"])
    except (json.JSONDecodeError, TypeError):
        return None
    return value if isinstance(value, list) else None


def classify_actionlint(finding: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(finding)
    kind = str(finding.get("kind", ""))
    message = str(finding.get("message", ""))
    if kind == "runner-label":
        normalized["interpretation"] = {
            "classification": "configuration-dependent",
            "reason": (
                "Runner labels may be valid custom labels. Interpret this diagnostic "
                "against the recorded actionlint version and repository configuration."
            ),
        }
    elif kind == "shellcheck":
        match = SHELLCHECK_SEVERITY.search(message)
        code = match.group(1).upper() if match else None
        severity = match.group(2).lower() if match else "unknown"
        classification = (
            "shell-hygiene"
            if severity == "style" or code in SHELLCHECK_HYGIENE_CODES
            else "shell-correctness"
            if severity in {"error", "warning", "info"}
            else "shell-review"
        )
        normalized["interpretation"] = {
            "classification": classification,
            "shellcheck_code": code,
            "shellcheck_severity": severity,
            "reason": (
                "Classified by the diagnostic's behavior, not severity alone. "
                "Known style-only codes are hygiene; word splitting, expansion, "
                "control-flow, and command failures remain correctness concerns."
            ),
        }
    else:
        normalized["interpretation"] = {"classification": "correctness"}
    return normalized


def record_stderr(
    envelope: dict[str, Any], tool: str, attempt_name: str, attempt: dict[str, Any]
) -> None:
    if attempt["stderr"]:
        add_diagnostic(
            envelope,
            "info",
            "tool_stderr",
            f"{tool} wrote to stderr during {attempt_name}",
            tool=tool,
            attempt=attempt_name,
            stderr=attempt["stderr"],
        )


def attempt_record(attempt: dict[str, Any], name: str) -> dict[str, Any]:
    return {
        "name": name,
        "command": attempt["command"],
        "exit_code": attempt["exit_code"],
        "timed_out": attempt["timed_out"],
        "stderr": attempt["stderr"],
    }


def run_actionlint(
    envelope: dict[str, Any],
    details: dict[str, Any],
    root: Path,
    workflows: list[Path],
    timeout: float,
) -> tuple[dict[str, Any], bool, set[str]]:
    result: dict[str, Any] = {
        "status": "unavailable",
        "findings": [],
        "attempts": [],
        "requested": len(workflows),
        "examined": 0,
    }
    if not details["available"]:
        add_diagnostic(
            envelope,
            "error",
            "missing_executable",
            "actionlint was not found on PATH",
            tool="actionlint",
        )
        return result, False, set()

    selected = workflows[:MAX_WORKFLOWS]
    selected_names = {relative_display(path, root) for path in selected}
    if len(workflows) > len(selected):
        add_limitation(
            envelope,
            f"actionlint examined the first {MAX_WORKFLOWS} sorted workflow files",
        )
        add_diagnostic(
            envelope,
            "warning",
            "degraded_analysis",
            "actionlint workflow-file bound reached",
            tool="actionlint",
            requested=len(workflows),
            examined=len(selected),
        )

    arguments = [
        details["executable"],
        "-format",
        "{{json .}}",
        *[relative_display(path, root) for path in selected],
    ]
    attempt = run_command(arguments, cwd=root, timeout=timeout)
    result["attempts"].append(attempt_record(attempt, "shellcheck-enabled"))
    record_stderr(envelope, "actionlint", "shellcheck-enabled", attempt)

    degraded = False
    if attempt["timed_out"]:
        add_diagnostic(
            envelope,
            "warning",
            "timeout",
            "actionlint timed out; retrying without shellcheck",
            tool="actionlint",
            timeout_seconds=timeout,
        )
        arguments = [
            details["executable"],
            "-shellcheck=",
            "-format",
            "{{json .}}",
            *[relative_display(path, root) for path in selected],
        ]
        attempt = run_command(arguments, cwd=root, timeout=timeout)
        result["attempts"].append(attempt_record(attempt, "shellcheck-disabled"))
        record_stderr(envelope, "actionlint", "shellcheck-disabled", attempt)
        degraded = True
        add_limitation(envelope, "actionlint shell analysis was skipped after timeout")
        add_diagnostic(
            envelope,
            "warning",
            "degraded_analysis",
            "actionlint completed without shellcheck after the bounded retry",
            tool="actionlint",
        )

    findings = parse_json_array(attempt)
    if attempt["timed_out"]:
        result["status"] = "failed"
        add_diagnostic(
            envelope,
            "error",
            "timeout",
            "actionlint timed out after its recovery attempt",
            tool="actionlint",
            timeout_seconds=timeout,
        )
        return result, True, set()
    if attempt["exit_code"] not in (0, 1):
        result["status"] = "failed"
        result["exit_code"] = attempt["exit_code"]
        add_diagnostic(
            envelope,
            "error",
            "tool_crash",
            "actionlint exited outside its clean/findings contract",
            tool="actionlint",
            exit_code=attempt["exit_code"],
        )
        return result, True, set()
    if findings is None:
        result["status"] = "failed"
        result["exit_code"] = attempt["exit_code"]
        add_diagnostic(
            envelope,
            "error",
            "tool_crash",
            "actionlint did not produce a JSON array",
            tool="actionlint",
        )
        return result, True, set()

    result.update(
        {
            "status": "degraded" if degraded else "completed",
            "exit_code": attempt["exit_code"],
            "findings": [classify_actionlint(item) for item in findings],
            "examined": len(selected_names),
        }
    )
    return result, False, selected_names


def is_online_failure(attempt: dict[str, Any]) -> bool:
    stderr = attempt["stderr"].lower()
    return any(marker in stderr for marker in ONLINE_FAILURE_MARKERS)


def is_no_inputs(attempt: dict[str, Any]) -> bool:
    stderr = attempt["stderr"].lower()
    return attempt["exit_code"] == 3 or any(marker in stderr for marker in NO_INPUT_MARKERS)


def zizmor_attempt_plan(mode: str) -> list[tuple[str, list[str]]]:
    plan = [
        ("online", []),
        ("no-online-audits", ["--no-online-audits"]),
    ]
    if mode == "local":
        plan.append(("offline", ["--offline"]))
    return plan


def run_zizmor(
    envelope: dict[str, Any],
    details: dict[str, Any],
    *,
    mode: str,
    targets: list[str],
    requested_workflows: int,
    examined_workflows: set[str],
    cwd: Path,
    timeout: float,
) -> tuple[dict[str, Any], str | None, set[str]]:
    result: dict[str, Any] = {
        "status": "unavailable",
        "findings": [],
        "attempts": [],
        "requested": requested_workflows,
        "examined": 0,
    }
    if not details["available"]:
        add_diagnostic(
            envelope,
            "error",
            "missing_executable",
            "zizmor was not found on PATH",
            tool="zizmor",
        )
        return result, "missing", set()

    recovery_reason: str | None = None
    for index, (attempt_name, flags) in enumerate(zizmor_attempt_plan(mode)):
        command = [
            details["executable"],
            "--format",
            "json",
            *flags,
            *targets,
        ]
        attempt = run_command(command, cwd=cwd, timeout=timeout)
        result["attempts"].append(attempt_record(attempt, attempt_name))
        record_stderr(envelope, "zizmor", attempt_name, attempt)

        findings = parse_json_array(attempt)
        if (
            not attempt["timed_out"]
            and attempt["exit_code"] in (0, 11, 12, 13, 14)
            and findings is not None
        ):
            degraded = index > 0
            result.update(
                {
                    "status": "degraded" if degraded else "completed",
                    "exit_code": attempt["exit_code"],
                    "findings": findings,
                    "network_audits": "skipped" if degraded else "checked",
                    "examined": len(examined_workflows),
                }
            )
            if degraded:
                envelope["result"]["skipped_network_audits"] = SKIPPED_NETWORK_AUDITS
                add_limitation(
                    envelope,
                    "zizmor network-dependent audits were skipped during recovery",
                )
                add_diagnostic(
                    envelope,
                    "warning",
                    "degraded_analysis",
                    "zizmor recovered without network-dependent audits",
                    tool="zizmor",
                    skipped_audits=SKIPPED_NETWORK_AUDITS,
                )
            return result, None, examined_workflows

        if is_no_inputs(attempt):
            result["status"] = "unavailable"
            add_diagnostic(
                envelope,
                "error",
                "no_inputs",
                f"zizmor collected no auditable inputs in {mode} mode",
                tool="zizmor",
                mode=mode,
            )
            return result, "no_inputs", set()

        recoverable = (
            attempt["timed_out"]
            or is_online_failure(attempt)
            or (mode == "local" and recovery_reason is not None)
        )
        if recoverable and index + 1 < len(zizmor_attempt_plan(mode)):
            recovery_reason = "timeout" if attempt["timed_out"] else "online_failure"
            add_diagnostic(
                envelope,
                "warning",
                recovery_reason,
                f"zizmor {attempt_name} attempt failed; applying bounded recovery",
                tool="zizmor",
                mode=mode,
            )
            continue

        if mode == "remote" and (recoverable or recovery_reason is not None):
            add_diagnostic(
                envelope,
                "error",
                "online_failure",
                (
                    "remote zizmor recovery failed; offline mode cannot fetch a "
                    "repository slug and was not attempted"
                ),
                tool="zizmor",
                mode=mode,
                offline_attempted=False,
            )
            result["status"] = "failed"
            return result, "online_failure", set()

        result["status"] = "failed"
        result["exit_code"] = attempt["exit_code"]
        code = "timeout" if attempt["timed_out"] else "tool_crash"
        add_diagnostic(
            envelope,
            "error",
            code,
            "zizmor did not produce a valid findings result",
            tool="zizmor",
            exit_code=attempt["exit_code"],
        )
        return result, recovery_reason or "crash", set()

    result["status"] = "failed"
    return result, recovery_reason or "crash", set()


def wanted_archive_member(relative: PurePosixPath) -> bool:
    parts = relative.parts
    if not parts:
        return False
    path = relative.as_posix()
    name = relative.name.lower()
    if path.startswith(".github/workflows/") and name.endswith((".yml", ".yaml")):
        return True
    if name in {"action.yml", "action.yaml"}:
        return True
    return path in {
        "actionlint.yaml",
        "actionlint.yml",
        ".github/actionlint.yaml",
        ".github/actionlint.yml",
        "zizmor.yml",
        ".zizmor.yml",
        ".github/zizmor.yml",
    }


def zizmor_local_inputs(
    envelope: dict[str, Any],
    root: Path,
    workflows: list[Path],
    *,
    include_actions: bool,
) -> list[str]:
    inputs = list(workflows)
    if include_actions:
        for name in ("action.yml", "action.yaml"):
            inputs.extend(root.rglob(name))
    unique = sorted({path.resolve() for path in inputs})
    if len(unique) > MAX_ZIZMOR_INPUTS:
        add_limitation(
            envelope,
            f"zizmor examined the first {MAX_ZIZMOR_INPUTS} sorted local inputs",
        )
        add_diagnostic(
            envelope,
            "warning",
            "degraded_analysis",
            "zizmor local input bound reached",
            tool="zizmor",
            requested=len(unique),
            examined=MAX_ZIZMOR_INPUTS,
        )
    return [relative_display(path, root) for path in unique[:MAX_ZIZMOR_INPUTS]]


def fetch_remote_archive(
    envelope: dict[str, Any],
    repository: str,
    ref: str | None,
    cwd: Path,
    timeout: float,
) -> tuple[Path | None, Path | None, str | None]:
    suffix = f"/{urllib.parse.quote(ref, safe='')}" if ref else ""
    endpoint = f"https://api.github.com/repos/{repository}/tarball{suffix}"
    envelope["provenance"]["source"]["archive_endpoint"] = endpoint
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "actions-workflow-toolkit/scan-workflows",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(endpoint, headers=headers)

    try:
        with urllib.request.urlopen(request, timeout=min(timeout, 60.0)) as response:
            length = response.headers.get("Content-Length")
            if length and int(length) > MAX_ARCHIVE_BYTES:
                raise ValueError("remote archive exceeds the compressed-size bound")
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = response.read(min(1024 * 1024, MAX_ARCHIVE_BYTES - total + 1))
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_ARCHIVE_BYTES:
                    raise ValueError("remote archive exceeds the compressed-size bound")
                chunks.append(chunk)
    except urllib.error.HTTPError as exc:
        remaining = exc.headers.get("X-RateLimit-Remaining")
        if exc.code == 404:
            code = "inaccessible_input"
            message = "remote repository or ref was not accessible"
        elif exc.code == 403 and remaining == "0":
            code = "rate_limiting"
            message = "GitHub API rate limit prevented remote workflow retrieval"
        elif exc.code in (401, 403):
            code = "online_failure"
            message = "authenticated GitHub access was unavailable"
        else:
            code = "online_failure"
            message = f"GitHub API returned HTTP {exc.code}"
        add_diagnostic(envelope, "error", code, message, http_status=exc.code)
        return None, None, code
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        add_diagnostic(
            envelope,
            "error",
            "online_failure",
            f"remote workflow retrieval failed: {redact(str(exc))}",
        )
        return None, None, "online_failure"

    scratch = cwd / f".scan-workflows-{uuid.uuid4().hex}"
    scratch.mkdir(mode=0o700)
    extracted_files = 0
    extracted_bytes = 0
    try:
        with tarfile.open(fileobj=io.BytesIO(b"".join(chunks)), mode="r:*") as archive:
            for member_index, member in enumerate(archive, start=1):
                if member_index > MAX_ARCHIVE_MEMBERS:
                    add_limitation(
                        envelope, "remote archive member bound was reached"
                    )
                    add_diagnostic(
                        envelope,
                        "warning",
                        "degraded_analysis",
                        "remote archive traversal was bounded",
                        max_members=MAX_ARCHIVE_MEMBERS,
                    )
                    break
                member_path = PurePosixPath(member.name)
                if member_path.is_absolute() or ".." in member_path.parts:
                    continue
                relative = PurePosixPath(*member_path.parts[1:])
                if not member.isfile() or not wanted_archive_member(relative):
                    continue
                if (
                    extracted_files >= MAX_EXTRACTED_FILES
                    or extracted_bytes + member.size > MAX_EXTRACTED_BYTES
                ):
                    add_limitation(
                        envelope,
                        "remote archive extraction reached its file or byte bound",
                    )
                    add_diagnostic(
                        envelope,
                        "warning",
                        "degraded_analysis",
                        "remote archive extraction was bounded",
                        max_files=MAX_EXTRACTED_FILES,
                        max_bytes=MAX_EXTRACTED_BYTES,
                    )
                    break
                destination = scratch.joinpath(*relative.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    continue
                data = source.read(member.size + 1)
                if len(data) != member.size:
                    raise tarfile.ReadError("archive member size did not match content")
                destination.write_bytes(data)
                extracted_files += 1
                extracted_bytes += len(data)
    except (tarfile.TarError, OSError, ValueError) as exc:
        shutil.rmtree(scratch, ignore_errors=True)
        add_diagnostic(
            envelope,
            "error",
            "online_failure",
            f"remote archive could not be safely extracted: {redact(str(exc))}",
        )
        return None, None, "online_failure"

    envelope["provenance"]["source"]["archive"] = {
        "compressed_bytes": total,
        "extracted_files": extracted_files,
        "extracted_bytes": extracted_bytes,
        "limits": {
            "compressed_bytes": MAX_ARCHIVE_BYTES,
            "members": MAX_ARCHIVE_MEMBERS,
            "files": MAX_EXTRACTED_FILES,
            "extracted_bytes": MAX_EXTRACTED_BYTES,
        },
    }
    return scratch, scratch, None


def write_document(
    envelope: dict[str, Any],
    destination: Path | None,
    pretty: bool,
) -> None:
    document = json.dumps(
        envelope,
        indent=2 if pretty else None,
        sort_keys=pretty,
        separators=None if pretty else (",", ":"),
    )
    if destination:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(document + "\n", encoding="utf-8")
    else:
        print(document)
    for diagnostic in envelope["diagnostics"]:
        print(
            f"{diagnostic['level']}: {diagnostic['code']}: {diagnostic['message']}",
            file=sys.stderr,
        )


def main(argv: list[str] | None = None) -> int:
    envelope = empty_envelope()
    cwd = Path.cwd().resolve()
    destination: Path | None = None
    scratch: Path | None = None
    try:
        args = build_parser().parse_args(argv)
        validate_args(args)
        destination = output_path(args.output, cwd)
    except InvocationError as exc:
        add_diagnostic(envelope, "error", "invalid_input", str(exc))
        write_document(envelope, None, False)
        return 2

    envelope["scope"] = {
        "mode": "remote" if args.repository else "local",
        "path": args.path,
        "repository": args.repository,
        "ref": args.ref,
        "bounds": {
            "tool_timeout_seconds": args.timeout_seconds,
            "actionlint_workflows": MAX_WORKFLOWS,
            "zizmor_inputs": MAX_ZIZMOR_INPUTS,
            "remote_archive_bytes": MAX_ARCHIVE_BYTES,
        },
    }
    envelope["provenance"]["source"] = {}

    root: Path
    workflows: list[Path]
    zizmor_target: str
    remote_zizmor: dict[str, Any] | None = None
    remote_zizmor_failure: str | None = None
    zizmor_examined: set[str] = set()

    if args.path:
        selected_path = Path(args.path)
        if not selected_path.is_absolute():
            selected_path = cwd / selected_path
        try:
            root, workflows, target_path = discover_workflows(selected_path)
        except (FileNotFoundError, OSError) as exc:
            add_diagnostic(
                envelope,
                "error",
                "inaccessible_input",
                f"local path was unavailable: {redact(str(exc))}",
            )
            write_document(envelope, destination, args.pretty)
            return 3
        envelope["provenance"]["source"] = {
            "kind": "local",
            "resolved_path": str(selected_path.resolve()),
            "scan_root": str(root),
        }
        zizmor_target = relative_display(target_path, root)
    else:
        root = cwd
        workflows = []
        target = args.repository + (f"@{args.ref}" if args.ref else "")
        envelope["provenance"]["source"] = {
            "kind": "github.com",
            "repository": args.repository,
            "ref": args.ref,
            "zizmor_target": target,
        }
        zizmor_target = target

    actionlint_details = executable_details("actionlint", ["-version"], root)
    zizmor_details = executable_details("zizmor", ["--version"], root)
    shellcheck_details = executable_details("shellcheck", ["--version"], root)
    envelope["provenance"]["tools"] = {
        "actionlint": actionlint_details,
        "zizmor": zizmor_details,
        "shellcheck": shellcheck_details,
    }

    if args.repository:
        (
            remote_zizmor,
            remote_zizmor_failure,
            zizmor_examined,
        ) = run_zizmor(
            envelope,
            zizmor_details,
            mode="remote",
            targets=[zizmor_target],
            requested_workflows=0,
            examined_workflows=set(),
            cwd=root,
            timeout=args.timeout_seconds,
        )

    if args.repository:
        scratch, fetched_root, fetch_failure = fetch_remote_archive(
            envelope,
            args.repository,
            args.ref,
            cwd,
            args.timeout_seconds,
        )
        if fetched_root:
            root, workflows, target_path = discover_workflows(fetched_root)
            zizmor_target = relative_display(target_path, root)
        else:
            add_limitation(envelope, "remote workflows were unavailable to actionlint")
            if remote_zizmor is not None:
                envelope["result"]["zizmor"] = remote_zizmor
            usable_remote = bool(
                remote_zizmor
                and remote_zizmor["status"] in {"completed", "degraded"}
            )
            envelope["coverage"].update(
                {
                    "status": "partial" if usable_remote else "unavailable",
                    "requested": 0,
                    "examined": 0,
                }
            )
            envelope["result"]["actionlint"]["status"] = "unavailable"
            write_document(envelope, destination, args.pretty)
            if usable_remote:
                return 0
            if remote_zizmor_failure == "crash":
                return 5
            return 4 if fetch_failure in {"online_failure", "rate_limiting"} else 3

    envelope["result"]["inputs"] = [
        relative_display(path, root) for path in workflows
    ]
    workflow_names = set(envelope["result"]["inputs"])
    envelope["coverage"]["requested"] = len(workflows)
    if remote_zizmor is not None:
        remote_zizmor["requested"] = len(workflow_names)
        if remote_zizmor["status"] in {"completed", "degraded"}:
            remote_zizmor["examined"] = len(workflow_names)
            zizmor_examined = workflow_names
    if not workflows:
        add_diagnostic(
            envelope,
            "error",
            "no_inputs",
            "no .yml or .yaml workflow files were found in the selected scope",
        )
        if remote_zizmor is not None:
            envelope["result"]["zizmor"] = remote_zizmor
        usable_remote = bool(
            remote_zizmor and remote_zizmor["status"] in {"completed", "degraded"}
        )
        envelope["coverage"]["status"] = "partial" if usable_remote else "unavailable"
        write_document(envelope, destination, args.pretty)
        if scratch:
            shutil.rmtree(scratch, ignore_errors=True)
        return 0 if usable_remote else 3

    if destination and destination.resolve() in {path.resolve() for path in workflows}:
        add_diagnostic(
            envelope,
            "error",
            "invalid_input",
            "--output cannot overwrite a selected workflow file",
        )
        write_document(envelope, None, args.pretty)
        if scratch:
            shutil.rmtree(scratch, ignore_errors=True)
        return 2

    actionlint_details["configuration"] = {
        "files": find_configs(
            root,
            (
                "actionlint.yaml",
                "actionlint.yml",
                ".github/actionlint.yaml",
                ".github/actionlint.yml",
            ),
        ),
        "shellcheck_available": shellcheck_details["available"],
        "timeout_seconds": args.timeout_seconds,
    }
    zizmor_details["configuration"] = {
        "files": find_configs(
            root, ("zizmor.yml", ".zizmor.yml", ".github/zizmor.yml")
        ),
        "timeout_seconds": args.timeout_seconds,
        "mode": "remote" if args.repository else "local",
    }

    actionlint_result, actionlint_failed, actionlint_examined = run_actionlint(
        envelope,
        actionlint_details,
        root,
        workflows,
        args.timeout_seconds,
    )
    envelope["result"]["actionlint"] = actionlint_result

    if not shellcheck_details["available"] and actionlint_details["available"]:
        add_limitation(envelope, "shellcheck was unavailable to actionlint")
        add_diagnostic(
            envelope,
            "warning",
            "missing_executable",
            "shellcheck was not found; run-block shell analysis may be absent",
            tool="shellcheck",
        )

    zizmor_failed = False
    if args.repository and remote_zizmor_failure != "no_inputs":
        envelope["result"]["zizmor"] = remote_zizmor or {
            "status": "unavailable",
            "findings": [],
        }
        zizmor_failed = bool(
            remote_zizmor_failure
            and remote_zizmor_failure not in {"missing"}
        )
    else:
        local_targets = zizmor_local_inputs(
            envelope,
            root,
            workflows,
            include_actions=bool(args.repository),
        )
        local_examined_candidates = workflow_names.intersection(local_targets)
        (
            local_zizmor,
            local_failure,
            zizmor_examined,
        ) = run_zizmor(
            envelope,
            zizmor_details,
            mode="local",
            targets=local_targets,
            requested_workflows=len(workflow_names),
            examined_workflows=local_examined_candidates,
            cwd=root,
            timeout=args.timeout_seconds,
        )
        if args.repository and remote_zizmor_failure == "no_inputs":
            local_zizmor["recovery"] = "local archive after remote no inputs"
            add_limitation(
                envelope,
                "remote zizmor collected no inputs; local archive recovery used a different input set",
            )
            add_diagnostic(
                envelope,
                "warning",
                "degraded_analysis",
                "remote zizmor no-input result recovered with the exact repository archive",
                tool="zizmor",
            )
        envelope["result"]["zizmor"] = local_zizmor
        zizmor_failed = bool(
            local_failure and local_failure not in {"missing", "no_inputs"}
        )

    statuses = {
        envelope["result"]["actionlint"]["status"],
        envelope["result"]["zizmor"]["status"],
    }
    usable = bool(statuses & {"completed", "degraded"})
    complete = statuses == {"completed"} and not envelope["coverage"]["limitations"]
    envelope["coverage"]["status"] = (
        "complete" if complete else "partial" if usable else "unavailable"
    )
    envelope["coverage"]["examined"] = len(
        actionlint_examined.union(zizmor_examined)
    )

    if scratch:
        shutil.rmtree(scratch, ignore_errors=True)
    write_document(envelope, destination, args.pretty)

    if actionlint_failed or zizmor_failed:
        return 5
    if not usable:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
