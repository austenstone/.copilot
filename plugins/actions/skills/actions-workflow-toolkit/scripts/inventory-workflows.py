#!/usr/bin/env python3
"""Build a bounded GitHub.com workflow inventory and reusable-workflow graph."""

from __future__ import annotations

import argparse
import base64
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:
    yaml = None


SCHEMA_VERSION = "actions-helper/v1"
TOOL = "inventory-workflows"
HELPER_VERSION = "1"
API_TIMEOUT_SECONDS = 30
API_VERSION = "2022-11-28"
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
ORGANIZATION = re.compile(r"^[A-Za-z0-9_.-]+$")
FULL_SHA = re.compile(r"^[0-9a-fA-F]{40}$")
JOB_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
REMOTE_WORKFLOW = re.compile(
    r"^(?P<repository>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)"
    r"/(?P<path>\.github/workflows/[^@\s]+)@(?P<ref>[^\s]+)$"
)
LOCAL_WORKFLOW = re.compile(r"^\./(?P<path>\.github/workflows/[^\s]+)$")
WORKFLOW_SUFFIXES = (".yml", ".yaml")
MEANINGFUL_JOB_KEYS = (
    "concurrency",
    "environment",
    "outputs",
    "permissions",
    "runs-on",
)


class InvocationError(Exception):
    """The caller supplied invalid or unsafe arguments."""


class WorkflowParseError(Exception):
    """A workflow is not valid YAML or does not have a mapping root."""


@dataclass
class ApiError(Exception):
    endpoint: str
    kind: str
    message: str
    status: int | None = None


def diagnostic(level: str, code: str, message: str, **metadata: Any) -> dict[str, Any]:
    item: dict[str, Any] = {"level": level, "code": code, "message": message}
    if metadata:
        item["metadata"] = metadata
    return item


def canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: canonicalize(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [canonicalize(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(
        canonicalize(value),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def ref_pin(ref: str | None) -> dict[str, Any]:
    if ref is None:
        return {"kind": "default_branch", "pinned": False, "value": None}
    return {
        "kind": "commit_sha" if FULL_SHA.fullmatch(ref) else "tag_or_branch",
        "pinned": bool(FULL_SHA.fullmatch(ref)),
        "value": ref,
    }


def actions_loader() -> type[Any]:
    if yaml is None:
        raise RuntimeError("PyYAML is unavailable")

    class ActionsSafeLoader(yaml.SafeLoader):
        pass

    ActionsSafeLoader.yaml_implicit_resolvers = {
        key: [
            resolver
            for resolver in resolvers
            if resolver[0]
            not in ("tag:yaml.org,2002:bool", "tag:yaml.org,2002:timestamp")
        ]
        for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }
    ActionsSafeLoader.add_implicit_resolver(
        "tag:yaml.org,2002:bool",
        re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"),
        list("tTfF"),
    )
    return ActionsSafeLoader


ACTIONS_SAFE_LOADER = actions_loader() if yaml is not None else None


def parse_workflow(text: str) -> dict[str, Any]:
    assert yaml is not None and ACTIONS_SAFE_LOADER is not None
    try:
        value = yaml.load(text, Loader=ACTIONS_SAFE_LOADER)
    except yaml.YAMLError as exc:
        raise WorkflowParseError(str(exc).splitlines()[0]) from exc
    if not isinstance(value, dict):
        raise WorkflowParseError("workflow root is not a mapping")
    return value


def normalize_named_value(value: Any) -> Any:
    if isinstance(value, (str, dict)) or value is None:
        return canonicalize(value)
    return value


def normalize_events(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return sorted(str(item) for item in value)
    if isinstance(value, dict):
        return sorted(str(key) for key in value)
    return []


def workflow_call_contract(value: Any) -> dict[str, Any] | None:
    empty = {"inputs": {}, "secrets": {}, "outputs": {}}
    if value == "workflow_call":
        return empty
    if isinstance(value, list) and "workflow_call" in value:
        return empty
    if not isinstance(value, dict) or "workflow_call" not in value:
        return None
    contract = value.get("workflow_call")
    if contract is None:
        return empty
    if not isinstance(contract, dict):
        return {"unparsed": canonicalize(contract)}
    return {
        "inputs": canonicalize(contract.get("inputs") or {}),
        "secrets": canonicalize(contract.get("secrets") or {}),
        "outputs": canonicalize(contract.get("outputs") or {}),
    }


def classify_api_error(endpoint: str, stderr: str, returncode: int) -> ApiError:
    safe = stderr.strip()
    lowered = safe.lower()
    status_match = re.search(r"http\s*([1-5][0-9]{2})", lowered)
    if not status_match:
        status_match = re.search(r"\b([45][0-9]{2})\b", lowered)
    status = int(status_match.group(1)) if status_match else None
    if (
        status == 401
        or "authentication" in lowered
        or "not logged" in lowered
        or "bad credentials" in lowered
        or "oauth" in lowered
    ):
        kind = "authentication"
    elif (
        "rate limit" in lowered
        or "secondary rate" in lowered
        or "abuse detection" in lowered
        or "x-ratelimit-remaining: 0" in lowered
    ):
        kind = "rate_limited"
    elif status == 403 or "forbidden" in lowered or "not accessible" in lowered:
        kind = "forbidden_or_rate_limited"
    elif status == 404 or "not found" in lowered:
        kind = "not_found_or_inaccessible"
    elif "timed out" in lowered or returncode == 124:
        kind = "timeout"
    else:
        kind = "online_failure"
    message = {
        "authentication": "Authenticated GitHub.com access was unavailable",
        "rate_limited": "GitHub.com API rate limiting prevented complete inventory",
        "forbidden_or_rate_limited": (
            "GitHub.com returned 403; authorization, policy, and rate limiting "
            "cannot be distinguished from this response"
        ),
        "not_found_or_inaccessible": (
            "GitHub.com returned 404; absence and inaccessibility cannot be "
            "distinguished from this response"
        ),
        "timeout": "The bounded GitHub.com API request timed out",
        "online_failure": f"GitHub.com API request failed with gh exit {returncode}",
    }[kind]
    return ApiError(endpoint, kind, message, status)


class GhClient:
    def __init__(self):
        executable = shutil.which("gh")
        if not executable:
            raise FileNotFoundError("gh")
        self.executable = executable
        self.endpoints: list[str] = []
        try:
            completed = subprocess.run(
                [self.executable, "--version"],
                capture_output=True,
                text=True,
                timeout=API_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ApiError(
                "gh --version", "timeout", "gh version check timed out"
            ) from exc
        if completed.returncode:
            raise FileNotFoundError("gh")
        lines = completed.stdout.splitlines()
        self.version = lines[0].strip() if lines else "unknown"

    def get(self, endpoint: str) -> Any:
        self.endpoints.append(endpoint)
        command = [
            self.executable,
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
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=API_TIMEOUT_SECONDS,
                check=False,
                env={**os.environ, "GH_HOST": "github.com"},
            )
        except subprocess.TimeoutExpired as exc:
            raise ApiError(endpoint, "timeout", "GitHub API request timed out") from exc
        if completed.returncode:
            raise classify_api_error(endpoint, completed.stderr, completed.returncode)
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ApiError(
                endpoint,
                "invalid_output",
                "gh returned invalid JSON",
            ) from exc


def content_endpoint(repository: str, path: str, ref: str | None) -> str:
    encoded_path = urllib.parse.quote(path, safe="/")
    endpoint = f"repos/{repository}/contents/{encoded_path}"
    if ref:
        endpoint += "?" + urllib.parse.urlencode({"ref": ref})
    return endpoint


def decode_content(payload: Any) -> str:
    if not isinstance(payload, dict):
        raise ValueError("content response is not an object")
    content = payload.get("content")
    if not isinstance(content, str):
        raise ValueError("content response has no base64 content")
    try:
        return base64.b64decode(content, validate=False).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("workflow content is not valid base64 UTF-8") from exc


def load_input(path: Path) -> list[dict[str, str | None]]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InvocationError(f"cannot read input file: {exc}") from exc
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        value = [
            line.strip()
            for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
    if isinstance(value, dict):
        value = value.get("repositories")
    if not isinstance(value, list):
        raise InvocationError("input must be a JSON list, repositories object, or lines")
    repositories: list[dict[str, str | None]] = []
    for item in value:
        if isinstance(item, str):
            repository, separator, ref = item.partition("@")
            entry = {"repository": repository, "ref": ref if separator else None}
        elif isinstance(item, dict):
            entry = {"repository": item.get("repository"), "ref": item.get("ref")}
        else:
            raise InvocationError("input repository entries must be strings or objects")
        repository = entry["repository"]
        ref = entry["ref"]
        if not isinstance(repository, str) or not REPOSITORY.fullmatch(repository):
            raise InvocationError(f"invalid GitHub.com repository in input: {repository}")
        if ref is not None and (not isinstance(ref, str) or not ref.strip()):
            raise InvocationError(f"invalid ref for {repository}")
        repositories.append({"repository": repository, "ref": ref})
    return repositories


def safe_output_path(raw: str) -> Path:
    cwd = Path.cwd().resolve()
    path = Path(raw)
    resolved = (cwd / path).resolve() if not path.is_absolute() else path.resolve()
    try:
        resolved.relative_to(cwd)
    except ValueError as exc:
        raise InvocationError("--output must stay below the current working directory") from exc
    if resolved == cwd or (resolved.exists() and resolved.is_dir()):
        raise InvocationError("--output must name a file below the current working directory")
    return resolved


class Inventory:
    def __init__(self, args: argparse.Namespace, client: GhClient):
        self.args = args
        self.client = client
        self.diagnostics: list[dict[str, Any]] = []
        self.limitations: list[str] = []
        self.repositories: list[dict[str, Any]] = []
        self.workflows: list[dict[str, Any]] = []
        self.edges: list[dict[str, Any]] = []
        self.jobs: list[dict[str, Any]] = []
        self.seen_workflows: dict[tuple[str, str, str | None], dict[str, Any]] = {}
        self.ref_resolutions: dict[tuple[str, str | None], dict[str, Any]] = {}
        self.workflow_attempts = 0
        self.callee_fetches = 0
        self.comparisons = 0

    def add_limitation(self, code: str) -> None:
        if code not in self.limitations:
            self.limitations.append(code)

    def api_limitation(
        self, error: ApiError, repository: str | None = None, path: str | None = None
    ) -> None:
        code = {
            "rate_limited": "rate_limiting",
            "timeout": "timeout",
            "authentication": "inaccessible_input",
        }.get(error.kind, "inaccessible_input")
        self.diagnostics.append(
            diagnostic(
                "warning",
                code,
                error.message,
                endpoint=error.endpoint,
                ambiguity=error.kind,
                repository=repository,
                path=path,
                http_status=error.status,
            )
        )
        self.add_limitation(error.kind)

    def resolve_ref(
        self,
        repository: str,
        requested_ref: str | None,
        default_branch: str | None = None,
    ) -> dict[str, Any]:
        cache_key = (repository.lower(), requested_ref or default_branch)
        if cache_key in self.ref_resolutions:
            cached = self.ref_resolutions[cache_key]
            return {
                **cached,
                "requested_ref": requested_ref,
                "content_ref": cached["effective_sha"] or requested_ref,
            }
        if requested_ref and FULL_SHA.fullmatch(requested_ref):
            resolution = {
                "requested_ref": requested_ref,
                "lookup_ref": requested_ref,
                "effective_sha": requested_ref.lower(),
                "content_ref": requested_ref.lower(),
                "status": "immutable_ref_supplied",
            }
            self.ref_resolutions[cache_key] = resolution
            return resolution

        lookup_ref = requested_ref or default_branch
        resolution = {
            "requested_ref": requested_ref,
            "lookup_ref": lookup_ref,
            "effective_sha": None,
            "content_ref": requested_ref,
            "status": "unverified",
        }
        if not lookup_ref:
            self.add_limitation("immutable_ref_unverified")
            self.diagnostics.append(
                diagnostic(
                    "warning",
                    "degraded_analysis",
                    "No ref was available to resolve an immutable repository commit",
                    repository=repository,
                )
            )
        else:
            endpoint = (
                f"repos/{repository}/commits/"
                f"{urllib.parse.quote(lookup_ref, safe='')}"
            )
            try:
                payload = self.client.get(endpoint)
            except ApiError as error:
                self.api_limitation(error, repository, lookup_ref)
                self.add_limitation("immutable_ref_unverified")
            else:
                effective_sha = payload.get("sha") if isinstance(payload, dict) else None
                if isinstance(effective_sha, str) and FULL_SHA.fullmatch(effective_sha):
                    resolution.update(
                        {
                            "effective_sha": effective_sha.lower(),
                            "content_ref": effective_sha.lower(),
                            "status": "resolved_to_commit",
                        }
                    )
                else:
                    self.add_limitation("immutable_ref_unverified")
                    self.diagnostics.append(
                        diagnostic(
                            "warning",
                            "degraded_analysis",
                            "Commit resolution returned no full immutable SHA",
                            repository=repository,
                            ref=lookup_ref,
                        )
                    )
        self.ref_resolutions[cache_key] = resolution
        return resolution

    def initial_repositories(self) -> list[dict[str, str | None]]:
        if self.args.repository:
            try:
                payload = self.client.get(f"repos/{self.args.repository}")
            except ApiError as error:
                self.api_limitation(error, self.args.repository)
                raise
            if not isinstance(payload, dict):
                raise ApiError(
                    f"repos/{self.args.repository}",
                    "invalid_output",
                    "repository response is not an object",
                )
            return [
                {
                    "repository": self.args.repository,
                    "ref": self.args.ref,
                    "default_branch": payload.get("default_branch"),
                    "archived": bool(payload.get("archived", False)),
                }
            ]
        if self.args.input:
            entries = load_input(Path(self.args.input))
            if len(entries) > self.args.max_repositories:
                self.add_limitation("repository_limit_reached")
                entries = entries[: self.args.max_repositories]
            result = []
            for entry in entries:
                repository = str(entry["repository"])
                try:
                    payload = self.client.get(f"repos/{repository}")
                except ApiError as error:
                    self.api_limitation(error, repository)
                    result.append(
                        {
                            **entry,
                            "default_branch": None,
                            "archived": None,
                            "status": "inaccessible",
                        }
                    )
                    continue
                result.append(
                    {
                        **entry,
                        "default_branch": payload.get("default_branch"),
                        "archived": bool(payload.get("archived", False)),
                    }
                )
            return result
        result = []
        page = 1
        while len(result) < self.args.max_repositories:
            endpoint = (
                f"orgs/{self.args.organization}/repos"
                f"?type=all&per_page=100&page={page}"
            )
            try:
                payload = self.client.get(endpoint)
            except ApiError as error:
                self.api_limitation(error)
                if result:
                    break
                raise
            if not isinstance(payload, list):
                raise ApiError(endpoint, "invalid_output", "repository page is not an array")
            remaining = self.args.max_repositories - len(result)
            selected = payload[:remaining]
            for repository in selected:
                if not isinstance(repository, dict):
                    continue
                full_name = repository.get("full_name")
                if not isinstance(full_name, str) or not REPOSITORY.fullmatch(full_name):
                    continue
                result.append(
                    {
                        "repository": full_name,
                        "ref": None,
                        "default_branch": repository.get("default_branch"),
                        "archived": bool(repository.get("archived", False)),
                    }
                )
            if len(payload) > remaining or (
                len(result) == self.args.max_repositories and len(payload) == 100
            ):
                self.add_limitation("repository_limit_reached")
                break
            if len(payload) < 100:
                break
            page += 1
        return result

    def run(self) -> None:
        for repository in self.initial_repositories():
            status = repository.pop("status", "examined")
            record = {**repository, "status": status, "workflow_count": 0}
            self.repositories.append(record)
            if status == "inaccessible":
                continue
            self.inventory_repository(record)
        self.follow_edges()
        self.compute_similarity()

    def inventory_repository(self, repository_record: dict[str, Any]) -> None:
        repository = repository_record["repository"]
        requested_ref = repository_record["ref"]
        resolution = self.resolve_ref(
            repository,
            requested_ref,
            repository_record.get("default_branch"),
        )
        repository_record["ref_resolution"] = {
            key: resolution[key]
            for key in ("requested_ref", "lookup_ref", "effective_sha", "status")
        }
        endpoint = content_endpoint(
            repository, ".github/workflows", resolution["content_ref"]
        )
        try:
            payload = self.client.get(endpoint)
        except ApiError as error:
            if error.status == 404 and requested_ref is None:
                repository_record["status"] = "no_workflow_directory_or_inaccessible"
            else:
                repository_record["status"] = "inaccessible"
            self.api_limitation(error, repository, ".github/workflows")
            return
        if not isinstance(payload, list):
            self.diagnostics.append(
                diagnostic(
                    "warning",
                    "degraded_analysis",
                    "workflow directory response is not an array",
                    repository=repository,
                )
            )
            self.add_limitation("invalid_directory_response")
            return
        entries = sorted(
            (
                item
                for item in payload
                if isinstance(item, dict)
                and item.get("type") == "file"
                and isinstance(item.get("path"), str)
                and str(item["path"]).lower().endswith(WORKFLOW_SUFFIXES)
            ),
            key=lambda item: str(item["path"]),
        )
        for entry in entries:
            if self.workflow_attempts >= self.args.max_workflows:
                self.add_limitation("workflow_limit_reached")
                break
            workflow = self.fetch_workflow(
                repository,
                str(entry["path"]),
                requested_ref,
                0,
                resolution,
            )
            if workflow:
                repository_record["workflow_count"] += 1

    def fetch_workflow(
        self,
        repository: str,
        path: str,
        requested_ref: str | None,
        depth: int,
        resolution: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        resolution = resolution or self.resolve_ref(repository, requested_ref)
        content_ref = resolution["content_ref"]
        key = (repository.lower(), path, content_ref)
        if key in self.seen_workflows:
            return self.seen_workflows[key]
        if self.workflow_attempts >= self.args.max_workflows:
            self.add_limitation("workflow_limit_reached")
            return None
        self.workflow_attempts += 1
        endpoint = content_endpoint(repository, path, content_ref)
        try:
            payload = self.client.get(endpoint)
        except ApiError as error:
            self.api_limitation(error, repository, path)
            return None
        try:
            text = decode_content(payload)
        except ValueError as error:
            self.diagnostics.append(
                diagnostic(
                    "warning",
                    "degraded_analysis",
                    str(error),
                    repository=repository,
                    path=path,
                )
            )
            self.add_limitation("invalid_workflow_content")
            return None
        try:
            parsed = parse_workflow(text)
        except WorkflowParseError as error:
            self.diagnostics.append(
                diagnostic(
                    "warning",
                    "degraded_analysis",
                    f"workflow YAML could not be parsed: {error}",
                    repository=repository,
                    path=path,
                )
            )
            self.add_limitation("invalid_workflow_yaml")
            parsed = {}
        workflow_id = f"{repository}:{path}@{requested_ref or '<default>'}"
        workflow_jobs = parsed.get("jobs")
        if not isinstance(workflow_jobs, dict):
            workflow_jobs = {}
        valid_job_ids = []
        for job_id in workflow_jobs:
            if isinstance(job_id, str) and JOB_ID.fullmatch(job_id):
                valid_job_ids.append(job_id)
                continue
            self.add_limitation("invalid_job_id")
            self.diagnostics.append(
                diagnostic(
                    "warning",
                    "invalid_input",
                    "Workflow contains a job ID that is not a valid string identifier",
                    repository=repository,
                    path=path,
                    job_id=str(job_id),
                )
            )
        jobs = []
        for job_id in sorted(valid_job_ids):
            value = workflow_jobs[job_id]
            if not isinstance(value, dict):
                continue
            canonical_job = canonicalize(value)
            serialized = canonical_json(canonical_job)
            job = {
                "workflow": workflow_id,
                "id": str(job_id),
                "name": value.get("name"),
                "uses": value.get("uses"),
                "runs_on": canonicalize(value.get("runs-on")),
                "environment": normalize_named_value(value.get("environment")),
                "concurrency": normalize_named_value(value.get("concurrency")),
                "permissions": canonicalize(value.get("permissions")),
                "outputs": canonicalize(value.get("outputs")),
                "canonical_sha256": sha256(serialized),
                "canonical_job": canonical_job,
            }
            jobs.append(job)
            self.jobs.append(job)
        workflow = {
            "id": workflow_id,
            "repository": repository,
            "path": path,
            "requested_ref": requested_ref,
            "source_ref": {
                "requested": ref_pin(requested_ref),
                "effective_sha": resolution["effective_sha"],
                "status": resolution["status"],
            },
            "blob_sha": payload.get("sha") if isinstance(payload, dict) else None,
            "html_url": payload.get("html_url") if isinstance(payload, dict) else None,
            "depth": depth,
            "name": parsed.get("name"),
            "events": normalize_events(parsed.get("on")),
            "workflow_call": workflow_call_contract(parsed.get("on")),
            "permissions": canonicalize(parsed.get("permissions")),
            "concurrency": normalize_named_value(parsed.get("concurrency")),
            "outputs": canonicalize(parsed.get("outputs")),
            "job_count": len(jobs),
            "jobs": jobs,
        }
        self.seen_workflows[key] = workflow
        self.workflows.append(workflow)
        for job in jobs:
            uses = job.get("uses")
            if not isinstance(uses, str):
                continue
            target = self.parse_workflow_call(
                repository, path, requested_ref, resolution, uses
            )
            if not target:
                continue
            self.edges.append(
                {
                    "caller": workflow_id,
                    "caller_job": job["id"],
                    "uses": uses,
                    "caller_contract": {
                        key: canonicalize(job["canonical_job"].get(key))
                        for key in (
                            "with",
                            "secrets",
                            "permissions",
                            "concurrency",
                            "strategy",
                            "needs",
                            "if",
                        )
                        if key in job["canonical_job"]
                    },
                    **target,
                    "depth": depth + 1,
                    "status": "pending",
                }
            )
        return workflow

    def parse_workflow_call(
        self,
        repository: str,
        path: str,
        source_ref: str | None,
        source_resolution: dict[str, Any],
        uses: str,
    ) -> dict[str, Any] | None:
        local = LOCAL_WORKFLOW.fullmatch(uses)
        if local:
            effective_sha = source_resolution["effective_sha"]
            return {
                "callee_repository": repository,
                "callee_path": local.group("path"),
                "callee_ref": source_ref,
                "callee_resolution": source_resolution,
                "pin": {
                    "kind": (
                        "local_same_commit"
                        if effective_sha
                        else "local_ref_unverified"
                    ),
                    "pinned": bool(effective_sha),
                    "value": effective_sha or source_ref,
                    "evidence": (
                        "caller and callee fetched at one resolved repository commit"
                        if effective_sha
                        else "immutable caller commit was not verified"
                    ),
                },
            }
        remote = REMOTE_WORKFLOW.fullmatch(uses)
        if not remote:
            if "/.github/workflows/" in uses:
                self.diagnostics.append(
                    diagnostic(
                        "warning",
                        "degraded_analysis",
                        "reusable-workflow reference could not be parsed",
                        repository=repository,
                        path=path,
                        uses=uses,
                    )
                )
                self.add_limitation("unparsed_reusable_workflow_reference")
            return None
        callee_ref = remote.group("ref")
        return {
            "callee_repository": remote.group("repository"),
            "callee_path": remote.group("path"),
            "callee_ref": callee_ref,
            "callee_resolution": None,
            "pin": ref_pin(callee_ref),
        }

    def follow_edges(self) -> None:
        index = 0
        while index < len(self.edges):
            edge = self.edges[index]
            index += 1
            if edge["status"] != "pending":
                continue
            if edge["depth"] > self.args.max_depth:
                edge["status"] = "not_followed"
                edge["limitation"] = "depth_limit_reached"
                self.add_limitation("caller_graph_depth_limit_reached")
                continue
            if self.callee_fetches >= self.args.max_callees:
                edge["status"] = "not_followed"
                edge["limitation"] = "callee_limit_reached"
                self.add_limitation("callee_limit_reached")
                continue
            resolution = edge.get("callee_resolution") or self.resolve_ref(
                edge["callee_repository"], edge["callee_ref"]
            )
            edge["callee_resolution"] = {
                key: resolution[key]
                for key in ("requested_ref", "lookup_ref", "effective_sha", "status")
            }
            key = (
                edge["callee_repository"].lower(),
                edge["callee_path"],
                resolution["content_ref"],
            )
            if key in self.seen_workflows:
                edge["status"] = "resolved"
                edge["callee"] = self.seen_workflows[key]["id"]
                continue
            self.callee_fetches += 1
            before_diagnostics = len(self.diagnostics)
            workflow = self.fetch_workflow(
                edge["callee_repository"],
                edge["callee_path"],
                edge["callee_ref"],
                edge["depth"],
                resolution,
            )
            if workflow:
                edge["status"] = "resolved"
                edge["callee"] = workflow["id"]
            else:
                edge["status"] = "inaccessible_or_unexamined"
                if len(self.diagnostics) > before_diagnostics:
                    metadata = self.diagnostics[-1].get("metadata", {})
                    edge["ambiguity"] = metadata.get("ambiguity")
                    edge["http_status"] = metadata.get("http_status")
                if "workflow_limit_reached" in self.limitations:
                    edge["limitation"] = "workflow_limit_reached"

    def compute_similarity(self) -> None:
        exact: dict[str, list[dict[str, str]]] = {}
        canonical_by_job: list[tuple[dict[str, Any], str]] = []
        for job in self.jobs:
            label = {"workflow": job["workflow"], "job": job["id"]}
            exact.setdefault(job["canonical_sha256"], []).append(label)
            canonical_by_job.append((job, canonical_json(job["canonical_job"])))
        self.exact_groups = [
            {"canonical_sha256": digest, "members": members}
            for digest, members in sorted(exact.items())
            if len(members) > 1
        ]
        pairs = []
        limit_reached = False
        for left_index, (left, left_text) in enumerate(canonical_by_job):
            for right, right_text in canonical_by_job[left_index + 1 :]:
                if self.comparisons >= self.args.max_comparisons:
                    limit_reached = True
                    break
                self.comparisons += 1
                if left["canonical_sha256"] == right["canonical_sha256"]:
                    continue
                score = difflib.SequenceMatcher(
                    None, left_text, right_text, autojunk=False
                ).ratio()
                if score >= self.args.similarity_threshold:
                    differences = [
                        key
                        for key in MEANINGFUL_JOB_KEYS
                        if left["canonical_job"].get(key)
                        != right["canonical_job"].get(key)
                    ]
                    pairs.append(
                        {
                            "left": {
                                "workflow": left["workflow"],
                                "job": left["id"],
                            },
                            "right": {
                                "workflow": right["workflow"],
                                "job": right["id"],
                            },
                            "score": round(score, 4),
                            "classification": "similarity_only",
                            "semantic_equivalence": "not_asserted",
                            "meaningful_differences": differences,
                        }
                    )
            if limit_reached:
                break
        if limit_reached:
            self.add_limitation("comparison_limit_reached")
        self.similar_pairs = sorted(
            pairs,
            key=lambda pair: (
                -pair["score"],
                pair["left"]["workflow"],
                pair["left"]["job"],
                pair["right"]["workflow"],
                pair["right"]["job"],
            ),
        )

    def result(self) -> dict[str, Any]:
        inaccessible = sum(
            edge["status"] == "inaccessible_or_unexamined" for edge in self.edges
        )
        unpinned = sum(
            edge["pin"]["kind"] == "tag_or_branch" for edge in self.edges
        )
        unverified_local = sum(
            edge["pin"]["kind"] == "local_ref_unverified" for edge in self.edges
        )
        caller_limitations = [
            "Incoming callers are limited to reusable-workflow calls found in examined workflows.",
            (
                "Dynamic references and callers outside the requested repository set "
                "are not discoverable."
            ),
        ]
        if self.limitations:
            caller_limitations.append(
                "Inventory bounds or inaccessible inputs further limit caller coverage."
            )
        return {
            "summary": {
                "repositories": len(self.repositories),
                "workflows": len(self.workflows),
                "workflow_attempts": self.workflow_attempts,
                "jobs": len(self.jobs),
                "reusable_workflow_edges": len(self.edges),
                "unpinned_remote_edges": unpinned,
                "unverified_local_edges": unverified_local,
                "inaccessible_or_unexamined_callees": inaccessible,
            },
            "repositories": self.repositories,
            "workflows": self.workflows,
            "reusable_workflow_edges": self.edges,
            "caller_coverage": {
                "status": "limited" if self.limitations else "scoped",
                "limitations": caller_limitations,
            },
            "duplication": {
                "method": "canonical JSON exact hashes plus bounded textual similarity",
                "similarity_is_semantic_equivalence": False,
                "exact_groups": self.exact_groups,
                "similar_pairs": self.similar_pairs,
                "comparisons": self.comparisons,
                "comparison_limit": self.args.max_comparisons,
            },
        }


class ContractArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise InvocationError(message)


def parser() -> argparse.ArgumentParser:
    value = ContractArgumentParser(
        description="Inventory GitHub.com workflows without cloning repositories."
    )
    scope = value.add_mutually_exclusive_group(required=True)
    scope.add_argument("--repository", metavar="OWNER/REPO")
    scope.add_argument("--organization", metavar="ORG")
    scope.add_argument(
        "--input",
        metavar="PATH",
        help="JSON or line-delimited GitHub.com repository manifest",
    )
    value.add_argument("--ref", help="remote ref; valid only with --repository")
    value.add_argument("--max-repositories", type=int)
    value.add_argument("--max-workflows", type=int, required=True)
    value.add_argument("--max-depth", type=int, default=3)
    value.add_argument("--max-callees", type=int, default=100)
    value.add_argument("--max-comparisons", type=int, default=5000)
    value.add_argument("--similarity-threshold", type=float, default=0.88)
    value.add_argument("--output")
    value.add_argument("--pretty", action="store_true")
    return value


def validate_args(args: argparse.Namespace) -> None:
    if args.repository and not REPOSITORY.fullmatch(args.repository):
        raise InvocationError("--repository must be an OWNER/REPO GitHub.com slug")
    if args.organization and not ORGANIZATION.fullmatch(args.organization):
        raise InvocationError("--organization must be a GitHub.com organization slug")
    if args.ref and not args.repository:
        raise InvocationError("--ref is valid only with --repository")
    if (args.organization or args.input) and args.max_repositories is None:
        raise InvocationError(
            "--max-repositories is required with --organization or --input"
        )
    if args.repository and args.max_repositories is not None:
        raise InvocationError("--max-repositories is not valid with --repository")
    for name in (
        "max_workflows",
        "max_callees",
        "max_comparisons",
    ):
        if getattr(args, name) is None or getattr(args, name) <= 0:
            raise InvocationError(f"--{name.replace('_', '-')} must be positive")
    if args.max_repositories is not None and args.max_repositories <= 0:
        raise InvocationError("--max-repositories must be positive")
    if args.max_depth < 0:
        raise InvocationError("--max-depth must be zero or greater")
    if not 0.0 <= args.similarity_threshold <= 1.0:
        raise InvocationError("--similarity-threshold must be between 0 and 1")
    if args.input and not Path(args.input).is_file():
        raise InvocationError("--input must name a readable file")


def envelope(
    args: argparse.Namespace,
    coverage: dict[str, Any],
    result: dict[str, Any],
    diagnostics: list[dict[str, Any]],
    endpoints: list[str],
    gh_version: str | None = None,
) -> dict[str, Any]:
    scope: dict[str, Any] = {
        "repository": args.repository,
        "organization": args.organization,
        "input": args.input,
        "ref": args.ref,
        "bounds": {
            "max_repositories": args.max_repositories,
            "max_workflows": args.max_workflows,
            "max_depth": args.max_depth,
            "max_callees": args.max_callees,
            "max_comparisons": args.max_comparisons,
        },
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL,
        "scope": scope,
        "provenance": {
            "source": "GitHub.com REST API via gh",
            "helper_version": HELPER_VERSION,
            "gh_version": gh_version,
            "yaml_library": f"PyYAML {yaml.__version__}" if yaml is not None else None,
            "github_api_version": API_VERSION,
            "api_timeout_seconds": API_TIMEOUT_SECONDS,
            "api_endpoints": endpoints,
            "configuration": {
                "similarity_threshold": args.similarity_threshold,
                "pinned_remote_ref": "full 40-character commit SHA",
            },
        },
        "coverage": coverage,
        "result": result,
        "diagnostics": diagnostics,
    }


def emit(document: dict[str, Any], args: argparse.Namespace) -> None:
    for item in document.get("diagnostics", []):
        level = str(item.get("level", "info")).upper()
        code = item.get("code", "unknown")
        message = item.get("message", "")
        print(f"{level} {code}: {message}", file=sys.stderr)

    text = json.dumps(document, indent=2 if args.pretty else None, ensure_ascii=False)
    if args.pretty:
        text += "\n"
    if args.output:
        path = safe_output_path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
        if not text.endswith("\n"):
            sys.stdout.write("\n")


def failure_document(
    args: argparse.Namespace,
    code: str,
    message: str,
    coverage_status: str = "unavailable",
    endpoints: list[str] | None = None,
    gh_version: str | None = None,
    **metadata: Any,
) -> dict[str, Any]:
    return envelope(
        args,
        {
            "status": coverage_status,
            "requested": args.max_workflows,
            "examined": 0,
            "limitations": [code],
        },
        {},
        [diagnostic("error", code, message, **metadata)],
        endpoints or [],
        gh_version,
    )


def empty_args() -> argparse.Namespace:
    return argparse.Namespace(
        repository=None,
        organization=None,
        input=None,
        ref=None,
        max_repositories=None,
        max_workflows=None,
        max_depth=None,
        max_callees=None,
        max_comparisons=None,
        similarity_threshold=None,
        output=None,
        pretty=False,
    )


def main(argv: list[str] | None = None) -> int:
    try:
        args = parser().parse_args(argv)
    except InvocationError as error:
        args = empty_args()
        emit(failure_document(args, "invalid_input", str(error)), args)
        return 2
    try:
        validate_args(args)
        if args.output:
            safe_output_path(args.output)
    except InvocationError as error:
        args.output = None
        emit(failure_document(args, "invalid_input", str(error)), args)
        return 2
    if yaml is None:
        emit(
            failure_document(
                args,
                "missing_dependency",
                "PyYAML is required for Actions-safe workflow parsing and was not found",
            ),
            args,
        )
        return 4
    try:
        client = GhClient()
    except FileNotFoundError:
        emit(
            failure_document(
                args,
                "missing_executable",
                "gh is required for GitHub.com inventory",
            ),
            args,
        )
        return 4
    except ApiError as error:
        emit(
            failure_document(
                args,
                "timeout",
                error.message,
                ambiguity=error.kind,
                endpoint=error.endpoint,
            ),
            args,
        )
        return 4
    inventory = Inventory(args, client)
    try:
        inventory.run()
    except InvocationError as error:
        emit(
            failure_document(
                args,
                "invalid_input",
                str(error),
                endpoints=client.endpoints,
                gh_version=client.version,
            ),
            args,
        )
        return 2
    except ApiError as error:
        code = {
            "authentication": "inaccessible_input",
            "rate_limited": "rate_limiting",
            "forbidden_or_rate_limited": "inaccessible_input",
            "not_found_or_inaccessible": "inaccessible_input",
            "timeout": "timeout",
            "invalid_output": "tool_crash",
        }.get(error.kind, "online_failure")
        exit_code = (
            4
            if error.kind
            in ("authentication", "rate_limited", "forbidden_or_rate_limited")
            else 5
            if error.kind == "invalid_output"
            else 3
        )
        emit(
            failure_document(
                args,
                code,
                error.message,
                endpoints=client.endpoints,
                gh_version=client.version,
                ambiguity=error.kind,
                endpoint=error.endpoint,
                http_status=error.status,
            ),
            args,
        )
        return exit_code
    limitations = sorted(inventory.limitations)
    coverage = {
        "status": "partial" if limitations else "complete",
        "requested": args.max_workflows,
        "examined": inventory.workflow_attempts,
        "limitations": limitations,
    }
    if not inventory.workflows:
        document = envelope(
            args,
            {
                "status": "unavailable",
                "requested": args.max_workflows,
                "examined": inventory.workflow_attempts,
                "limitations": limitations or ["no_inputs"],
            },
            inventory.result(),
            inventory.diagnostics
            + [diagnostic("error", "no_inputs", "no workflow inputs were available")],
            client.endpoints,
            client.version,
        )
        emit(document, args)
        return 3
    emit(
        envelope(
            args,
            coverage,
            inventory.result(),
            inventory.diagnostics,
            client.endpoints,
            client.version,
        ),
        args,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
