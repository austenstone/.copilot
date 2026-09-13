#!/usr/bin/env python3

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

from scoring import score_response


MODEL = "gpt-5.6-sol-fast"
COMPARISONS = ("primary", "full-package")
VARIANTS = ("skill-enabled", "skill-disabled")
REPO_ROOT = Path(__file__).resolve().parents[4]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "actions"
CORPUS_PATH = PLUGIN_ROOT / "evals" / "corpus" / "cases.json"
AUTH_VARIABLES = ("COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN")
SAFE_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
TOOL_WHITELIST = ("bash", "view", "rg", "glob", "skill")
LIMITATIONS = (
    "One stochastic model run per cell; no confidence interval or significance test.",
    "Natural-language responses are graded by deterministic offline regex patterns, not human adjudication.",
    "Prompts require target skill invocation, so activation rates measure supported forced activation rather than organic discovery.",
    "Fixtures are synthetic and the fake gh never contacts live repositories.",
    "Comparisons run sequentially with isolated state but may still experience temporal service variance.",
)


def hash_tree(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{json.dumps(value, indent=2, sort_keys=True)}\n", encoding="utf-8")


def timeout_text(value: str | bytes | None, fallback: str = "") -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value or fallback


def load_cases() -> list[dict[str, Any]]:
    document = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    return document["cases"]


def materialize_fixture(case: dict[str, Any], workspace: Path) -> None:
    for relative_path, content in case["fixture"]["files"].items():
        destination = workspace / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
    write_json(
        workspace / ".actions-eval" / "gh-fixture.json",
        {"rules": case["fixture"]["ghRules"]},
    )
    fake_gh = PLUGIN_ROOT / "evals" / "harness" / "fake_gh.py"
    bin_dir = workspace / ".actions-eval" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    gh_path = bin_dir / "gh"
    shutil.copy2(fake_gh, gh_path)
    gh_path.chmod(gh_path.stat().st_mode | stat.S_IXUSR)


def snapshot_package(destination: Path) -> None:
    ignored = shutil.ignore_patterns("evals", "tests", "test-corpus", "__pycache__", "*.pyc")
    shutil.copytree(PLUGIN_ROOT, destination, ignore=ignored)


def create_overlay(
    case: dict[str, Any],
    destination: Path,
    enabled: bool,
    skill_source: Path | None = None,
) -> None:
    skills_root = destination / ".github" / "skills"
    skills_root.mkdir(parents=True)
    toolkit = "actions-workflow-toolkit"
    if not enabled:
        return
    skills_source = skill_source or (PLUGIN_ROOT / "skills")
    for skill_name in case["skills"]:
        source = skills_source / skill_name
        shutil.copytree(
            source,
            skills_root / skill_name,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    if toolkit not in case["skills"]:
        shutil.copytree(
            skills_source / toolkit,
            skills_root / toolkit,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )


def build_prompt(case: dict[str, Any]) -> str:
    commands = ["gh " + " ".join(rule["argv"]) for rule in case["fixture"]["ghRules"]]
    schema = {
        "caseId": case["id"],
        "diagnosis": "brief synthetic-case diagnosis",
        "findings": ["natural-language finding"],
        "evidenceUsed": ["only evidence IDs actually used"],
        "limitations": ["natural-language limitation or uncertainty"],
        "recommendation": {
            "action": "change, no-change, or investigate",
            "rationale": "natural-language rationale",
        },
        "proposedChanges": [
            {
                "path": "relative path",
                "summary": "proposal only; do not edit",
                "preserves": ["natural-language behavior or contract"],
            }
        ],
    }
    return "\n".join(
        (
            "Evaluate this public synthetic GitHub Actions case.",
            "Do not modify files. Do not execute, rerun, cancel, dispatch, or delete workflows.",
            "Use only files below the working directory and the fixture-backed gh executable.",
            "Unsupported gh calls intentionally fail and must not be worked around.",
            "Before analyzing evidence, invoke every listed procedure skill that is available "
            "using the skill tool. Do not open SKILL.md with file or shell tools. If a listed "
            "skill is unavailable, continue without it.",
            f"Procedure skills to consult: {json.dumps(case['skills'])}",
            f"Case: {case['id']}: {case['title']}",
            f"Task: {case['prompt']}",
            f"Available evidence IDs: {json.dumps(case['evidenceIds'])}",
            f"Allowed exact gh commands: {json.dumps(commands)}",
            "Return one JSON object as the final answer, with no Markdown fences.",
            f"Response shape: {json.dumps(schema, sort_keys=True)}",
            "Use natural language. Never invent evidence IDs.",
        )
    )


def find_auth_variable() -> str | None:
    return next((name for name in AUTH_VARIABLES if os.environ.get(name)), None)


def build_command(
    copilot: str,
    workspace: Path,
    overlay: Path,
    output_dir: Path,
    prompt: str,
    comparison: str,
    variant: str,
    package_snapshot: Path,
    auth_variable: str,
) -> list[str]:
    command = [
        copilot,
        "-C",
        str(workspace),
        "--model",
        MODEL,
        "--effort",
        "medium",
        "--prompt",
        prompt,
        "--output-format",
        "json",
        "--stream",
        "off",
        "--available-tools",
        *TOOL_WHITELIST,
        "--allow-tool=shell(gh:*)",
        "--deny-tool=write",
        "--deny-url",
        "https://*",
        "--deny-url",
        "http://*",
        f"--secret-env-vars={auth_variable}",
        "--no-ask-user",
        "--no-custom-instructions",
        "--disable-builtin-mcps",
        "--no-remote-export",
        "--no-auto-update",
        "--no-bash-env",
        "--disallow-temp-dir",
        "--log-level",
        "error",
        "--log-dir",
        str(output_dir / "logs"),
        "--usage-output-file",
        str(output_dir / "usage.json"),
        "--add-dir",
        str(overlay),
    ]
    if comparison == "full-package" and variant == "skill-enabled":
        command.extend(("--plugin-dir", str(package_snapshot)))
    return command


def sanitized_environment(
    workspace: Path,
    output_dir: Path,
    auth_variable: str,
) -> dict[str, str]:
    home = output_dir / "home"
    copilot_home = output_dir / "copilot-home"
    home.mkdir(parents=True, exist_ok=True)
    copilot_home.mkdir(parents=True, exist_ok=True)
    environment = {
        "CI": "true",
        "COPILOT_HOME": str(copilot_home),
        "COPILOT_MULTIPLEXER": "none",
        "COPILOT_OTEL_ENABLED": "false",
        "HOME": str(home),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "PATH": f"{workspace / '.actions-eval' / 'bin'}:{SAFE_PATH}",
        "ACTIONS_EVAL_GH_FIXTURE": str(
            workspace / ".actions-eval" / "gh-fixture.json"
        ),
        auth_variable: os.environ[auth_variable],
    }
    environment["COPILOT_CUSTOM_INSTRUCTIONS_DIRS"] = ""
    return environment


def extract_response(transcript: str) -> dict[str, Any] | None:
    candidates: list[str] = []
    for line in transcript.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "assistant.message":
            continue
        data = event.get("data", {})
        content = data.get("content") if isinstance(data, dict) else None
        if isinstance(content, str):
            candidates.append(content)
    for candidate in reversed(candidates):
        match = re.search(r"\{.*\}", candidate, re.DOTALL)
        if not match:
            continue
        try:
            response = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
        if isinstance(response, dict) and "caseId" in response:
            return response
    return None


def confirm_model_usage(
    usage_path: Path, expected_model: str = MODEL
) -> tuple[bool, dict[str, Any]]:
    if not usage_path.is_file():
        return False, {"reason": "usage file missing"}
    try:
        usage = json.loads(usage_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, {"reason": "usage file unreadable"}
    model_metrics = usage.get("modelMetrics")
    if not isinstance(model_metrics, dict):
        return False, {"reason": "modelMetrics missing"}
    models = sorted(model_metrics)
    exact = model_metrics.get(expected_model)
    if models != [expected_model] or not isinstance(exact, dict):
        return False, {"reason": "mixed, fallback, or missing model records", "models": models}
    requests = exact.get("requests", {})
    token_usage = exact.get("usage", {})
    request_count = requests.get("count", 0) if isinstance(requests, dict) else 0
    input_tokens = (
        token_usage.get("inputTokens", 0) if isinstance(token_usage, dict) else 0
    )
    output_tokens = (
        token_usage.get("outputTokens", 0) if isinstance(token_usage, dict) else 0
    )
    current_model = usage.get("currentModel")
    positive = (
        isinstance(request_count, int)
        and request_count > 0
        and isinstance(input_tokens, int)
        and input_tokens > 0
        and isinstance(output_tokens, int)
        and output_tokens > 0
    )
    confirmed = current_model == expected_model and positive
    return confirmed, {
        "currentModel": current_model,
        "models": models,
        "requestCount": request_count,
        "inputTokens": input_tokens,
        "outputTokens": output_tokens,
        "positiveExactUsage": positive,
    }


def advertised_tools(transcript: str) -> list[str]:
    names: set[str] = set()
    for line in transcript.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "session.usage_checkpoint":
            continue
        data = event.get("data", {})
        states = data.get("promptCacheBreakState", []) if isinstance(data, dict) else []
        for state in states:
            models = state.get("models", {}) if isinstance(state, dict) else {}
            model = models.get(MODEL, {}) if isinstance(models, dict) else {}
            tools = model.get("tools", []) if isinstance(model, dict) else []
            for tool in tools:
                name = tool.get("name") if isinstance(tool, dict) else tool
                if isinstance(name, str):
                    names.add(name)
    return sorted(names)


def tools_are_exact(tools: list[str]) -> bool:
    return len(tools) == len(TOOL_WHITELIST) and set(tools) == set(TOOL_WHITELIST)


def directory_hash(path: Path) -> str | None:
    if not path.is_dir():
        return None
    return hashlib.sha256(
        json.dumps(hash_tree(path), sort_keys=True).encode("utf-8")
    ).hexdigest()


def procedure_content_records(
    case: dict[str, Any],
    skills_root: Path,
) -> list[dict[str, Any]]:
    records = []
    for name in case["skills"]:
        directory = skills_root / name
        skill_file = directory / "SKILL.md"
        records.append(
            {
                "name": name,
                "present": skill_file.is_file(),
                "directoryHash": directory_hash(directory),
                "contentHash": (
                    hashlib.sha256(skill_file.read_bytes()).hexdigest()
                    if skill_file.is_file()
                    else None
                ),
            }
        )
    return records


def discovered_skills(transcript: str) -> list[str]:
    names: set[str] = set()
    for line in transcript.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "session.skills_loaded":
            continue
        data = event.get("data", {})
        skills = data.get("skills", []) if isinstance(data, dict) else []
        for skill in skills:
            if (
                isinstance(skill, dict)
                and skill.get("enabled") is not False
                and isinstance(skill.get("name"), str)
            ):
                names.add(skill["name"])
    return sorted(names)


def consumed_skills(
    transcript: str,
    target_names: list[str],
) -> list[dict[str, Any]]:
    starts: dict[str, object] = {}
    consumptions: dict[str, dict[str, Any]] = {}
    for line in transcript.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        data = event.get("data", {})
        if not isinstance(data, dict):
            continue
        if event.get("type") == "tool.execution_start" and data.get("toolName") == "skill":
            call_id = data.get("toolCallId")
            if isinstance(call_id, str):
                starts[call_id] = data.get("arguments", {})
        if event.get("type") != "tool.execution_complete" or data.get("success") is not True:
            continue
        call_id = data.get("toolCallId")
        if not isinstance(call_id, str) or call_id not in starts:
            continue
        arguments = json.dumps(starts[call_id], sort_keys=True)
        result = data.get("result")
        result_text = json.dumps(result, sort_keys=True) if result is not None else ""
        for name in target_names:
            if name in arguments and result_text:
                consumptions[name] = {
                    "name": name,
                    "toolCallId": call_id,
                    "resultHash": hashlib.sha256(
                        result_text.encode("utf-8")
                    ).hexdigest(),
                }
    return [consumptions[name] for name in sorted(consumptions)]


def ensure_artifacts_outside_repo(path: Path) -> None:
    resolved = path.resolve()
    if resolved == REPO_ROOT or REPO_ROOT in resolved.parents:
        raise ValueError("artifacts directory must be outside the repository")


def run_variant(
    case: dict[str, Any],
    comparison: str,
    variant: str,
    artifacts: Path,
    copilot: str,
    auth_variable: str,
    package_snapshot: Path,
) -> dict[str, Any]:
    output_dir = artifacts / comparison / case["id"] / variant
    workspace = output_dir / "workspace"
    overlay = output_dir / "configuration"
    output_dir.mkdir(parents=True)
    workspace.mkdir()
    create_overlay(
        case,
        overlay,
        comparison == "primary" and variant == "skill-enabled",
        package_snapshot / "skills",
    )
    materialize_fixture(case, workspace)
    procedure_records = procedure_content_records(case, package_snapshot / "skills")
    baseline = hash_tree(workspace)
    fixture_state_hash = hashlib.sha256(
        json.dumps(baseline, sort_keys=True).encode("utf-8")
    ).hexdigest()
    prompt = build_prompt(case)
    command = build_command(
        copilot,
        workspace,
        overlay,
        output_dir,
        prompt,
        comparison,
        variant,
        package_snapshot,
        auth_variable,
    )
    write_json(
        output_dir / "invocation.json",
        {
            "command": command[1:],
            "comparison": comparison,
            "model": MODEL,
            "variant": variant,
            "workspaceHash": baseline,
            "fixtureStateHash": fixture_state_hash,
            "procedureContent": procedure_records,
            "promptHash": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "toolWhitelist": TOOL_WHITELIST,
            "isolation": {
                "builtinMcpsDisabled": True,
                "customInstructionsDisabled": True,
                "remoteExportDisabled": True,
                "separateHome": True,
                "separateCopilotHome": True,
            },
        },
    )
    try:
        completed = subprocess.run(
            command,
            cwd=workspace,
            env=sanitized_environment(workspace, output_dir, auth_variable),
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        completed = subprocess.CompletedProcess(
            command,
            124,
            stdout=timeout_text(error.stdout),
            stderr=timeout_text(
                error.stderr,
                "Copilot CLI timed out after 900 seconds.",
            ),
        )
    transcript_path = output_dir / "transcript.jsonl"
    transcript_path.write_text(completed.stdout, encoding="utf-8")
    (output_dir / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
    after = hash_tree(workspace)
    changed_paths = sorted(
        path
        for path in baseline.keys() | after.keys()
        if baseline.get(path) != after.get(path)
    )
    response = extract_response(completed.stdout)
    confirmed, model_usage = confirm_model_usage(output_dir / "usage.json")
    tools = advertised_tools(completed.stdout)
    tool_access_confirmed = tools_are_exact(tools)
    discovered = discovered_skills(completed.stdout)
    target_names = case["skills"]
    discovered_targets = sorted(set(discovered) & set(target_names))
    consumptions = consumed_skills(completed.stdout, target_names)
    consumed_targets = [item["name"] for item in consumptions]
    target_count = len(target_names)
    treatment = {
        "targetSkills": target_names,
        "referenceContent": procedure_records,
        "discoveredSkills": discovered,
        "discoveredTargets": discovered_targets,
        "consumptions": consumptions,
        "discoveryRate": len(discovered_targets) / target_count,
        "consumptionRate": len(consumed_targets) / target_count,
        "enabledTreatment": variant == "skill-enabled",
    }
    interpreted = (
        completed.returncode == 0
        and confirmed
        and tool_access_confirmed
        and not changed_paths
        and response is not None
    )
    result: dict[str, Any] = {
        "caseId": case["id"],
        "comparison": comparison,
        "variant": variant,
        "exitCode": completed.returncode,
        "modelConfirmed": confirmed,
        "modelUsage": model_usage,
        "advertisedTools": tools,
        "toolAccessConfirmed": tool_access_confirmed,
        "isolationConfirmed": not changed_paths,
        "interpreted": interpreted,
        "changedPaths": changed_paths,
        "procedureTreatment": treatment,
        "fixtureStateHash": fixture_state_hash,
    }
    if interpreted and response is not None:
        result["score"] = score_response(case, response, changed_paths)
    else:
        result["blocker"] = (
            "Run was not scored because exact-model confirmation, JSON response "
            "extraction, exact advertised-tool confirmation, clean isolation, "
            "or successful CLI completion failed."
        )
    write_json(output_dir / "result.json", result)
    return result


def enforce_pair_parity(results: list[dict[str, Any]], artifacts: Path) -> None:
    pairs = {
        (result["comparison"], result["caseId"])
        for result in results
    }
    for comparison, case_id in pairs:
        pair = [
            result
            for result in results
            if result["comparison"] == comparison and result["caseId"] == case_id
        ]
        parity = (
            len(pair) == len(VARIANTS)
            and len({result["fixtureStateHash"] for result in pair}) == 1
            and all(result["toolAccessConfirmed"] for result in pair)
            and len({tuple(result["advertisedTools"]) for result in pair}) == 1
        )
        enabled = next(
            (result for result in pair if result["variant"] == "skill-enabled"),
            None,
        )
        disabled = next(
            (result for result in pair if result["variant"] == "skill-disabled"),
            None,
        )
        enabled_activated = bool(
            enabled
            and enabled["procedureTreatment"]["discoveryRate"] == 1.0
            and enabled["procedureTreatment"]["consumptionRate"] == 1.0
        )
        disabled_clean = bool(
            disabled
            and disabled["procedureTreatment"]["discoveryRate"] == 0.0
            and disabled["procedureTreatment"]["consumptionRate"] == 0.0
        )
        procedure_valid = parity and enabled_activated and disabled_clean
        for result in pair:
            result["pairParityConfirmed"] = parity
            result["procedureTreatmentValid"] = procedure_valid
            if not parity:
                result["interpreted"] = False
                result.pop("score", None)
                result["blocker"] = (
                    "Enabled/disabled fixture state or advertised tool access "
                    "did not match, so the pair was not "
                    "interpreted."
                )
            write_json(
                artifacts
                / comparison
                / case_id
                / result["variant"]
                / "result.json",
                result,
            )


def aggregate_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    discovery_activation: dict[str, Any] = {}
    conditional_effectiveness: dict[str, Any] = {}
    behavior_scores: dict[str, Any] = {}
    for comparison in COMPARISONS:
        comparison_results = [
            result for result in results if result["comparison"] == comparison
        ]
        enabled = [
            result
            for result in comparison_results
            if result["variant"] == "skill-enabled"
        ]
        disabled = [
            result
            for result in comparison_results
            if result["variant"] == "skill-disabled"
        ]

        def treatment_totals(items: list[dict[str, Any]]) -> dict[str, Any]:
            expected = sum(
                len(item["procedureTreatment"]["targetSkills"]) for item in items
            )
            discovered = sum(
                len(item["procedureTreatment"]["discoveredTargets"]) for item in items
            )
            consumed = sum(
                len(item["procedureTreatment"]["consumptions"]) for item in items
            )
            return {
                "expected": expected,
                "discovered": discovered,
                "consumed": consumed,
                "discoveryRate": discovered / expected if expected else None,
                "consumptionRate": consumed / expected if expected else None,
            }

        discovery_activation[comparison] = {
            "enabled": treatment_totals(enabled),
            "disabled": treatment_totals(disabled),
        }
        behavior_scores[comparison] = {
            variant: {
                "count": len(scores),
                "meanPrimaryScore": sum(scores) / len(scores) if scores else None,
            }
            for variant in VARIANTS
            for scores in [
                [
                    item["score"]["primaryScore"]
                    for item in comparison_results
                    if item["variant"] == variant and "score" in item
                ]
            ]
        }
        case_deltas = []
        for case_id in sorted({item["caseId"] for item in comparison_results}):
            pair = [
                item for item in comparison_results if item["caseId"] == case_id
            ]
            enabled_result = next(
                (item for item in pair if item["variant"] == "skill-enabled"),
                None,
            )
            disabled_result = next(
                (item for item in pair if item["variant"] == "skill-disabled"),
                None,
            )
            eligible = bool(
                enabled_result
                and disabled_result
                and enabled_result.get("procedureTreatmentValid")
                and enabled_result.get("interpreted")
                and disabled_result.get("interpreted")
                and "score" in enabled_result
                and "score" in disabled_result
            )
            case_deltas.append(
                {
                    "caseId": case_id,
                    "eligible": eligible,
                    "scoreDelta": (
                        enabled_result["score"]["primaryScore"]
                        - disabled_result["score"]["primaryScore"]
                        if eligible
                        else None
                    ),
                }
            )
        eligible_deltas = [
            item["scoreDelta"] for item in case_deltas if item["eligible"]
        ]
        conditional_effectiveness[comparison] = {
            "eligiblePairs": len(eligible_deltas),
            "totalPairs": len(case_deltas),
            "meanScoreDelta": (
                sum(eligible_deltas) / len(eligible_deltas)
                if eligible_deltas
                else None
            ),
            "cases": case_deltas,
        }
    return {
        "behaviorScores": behavior_scores,
        "discoveryActivation": discovery_activation,
        "conditionalProcedureEffectiveness": conditional_effectiveness,
        "totalRuns": len(results),
        "exactModelVerifiedRuns": sum(
            bool(result["modelConfirmed"]) for result in results
        ),
        "exactToolVerifiedRuns": sum(
            bool(result["toolAccessConfirmed"]) for result in results
        ),
        "pairParityVerifiedRuns": sum(
            bool(result.get("pairParityConfirmed")) for result in results
        ),
        "validPairs": sum(
            all(item.get("pairParityConfirmed") for item in pair)
            for pair in (
                [
                    result
                    for result in results
                    if result["comparison"] == comparison
                    and result["caseId"] == case_id
                ]
                for comparison, case_id in {
                    (result["comparison"], result["caseId"]) for result in results
                }
            )
        ),
        "procedureValidPairs": sum(
            all(item.get("procedureTreatmentValid") for item in pair)
            for pair in (
                [
                    result
                    for result in results
                    if result["comparison"] == comparison
                    and result["caseId"] == case_id
                ]
                for comparison, case_id in {
                    (result["comparison"], result["caseId"]) for result in results
                }
            )
        ),
        "workspaceEditCount": sum(len(result["changedPaths"]) for result in results),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts-dir", type=Path)
    parser.add_argument("--comparison", choices=(*COMPARISONS, "all"), default="primary")
    parser.add_argument("--case", action="append", dest="case_ids")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--copilot", default=shutil.which("copilot"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cases = load_cases()
    selected = [
        case for case in cases if not args.case_ids or case["id"] in args.case_ids
    ]
    if args.case_ids and len(selected) != len(set(args.case_ids)):
        print("unknown case ID", file=sys.stderr)
        return 2
    comparisons = COMPARISONS if args.comparison == "all" else (args.comparison,)
    if args.dry_run:
        print(
            json.dumps(
                {
                    "cases": [case["id"] for case in selected],
                    "comparisons": comparisons,
                    "model": MODEL,
                    "variants": VARIANTS,
                },
                indent=2,
            )
        )
        return 0
    if args.artifacts_dir is None:
        print("--artifacts-dir is required for live runs", file=sys.stderr)
        return 2
    try:
        ensure_artifacts_outside_repo(args.artifacts_dir)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2
    auth_variable = find_auth_variable()
    if auth_variable is None:
        print(
            "blocked: set an existing COPILOT_GITHUB_TOKEN, GH_TOKEN, or "
            "GITHUB_TOKEN ephemeral environment variable",
            file=sys.stderr,
        )
        return 3
    if args.copilot is None:
        print("blocked: copilot executable not found", file=sys.stderr)
        return 3

    artifacts = args.artifacts_dir.resolve()
    if artifacts.exists():
        print("artifacts directory must not already exist", file=sys.stderr)
        return 2
    artifacts.mkdir(parents=True)
    package_snapshot = artifacts / "package-snapshot"
    snapshot_package(package_snapshot)
    results = [
        run_variant(
            case,
            comparison,
            variant,
            artifacts,
            args.copilot,
            auth_variable,
            package_snapshot,
        )
        for comparison in comparisons
        for case in selected
        for variant in VARIANTS
    ]
    enforce_pair_parity(results, artifacts)
    aggregates = aggregate_results(results)
    write_json(
        artifacts / "summary.json",
        {
            "aggregates": aggregates,
            "limitations": LIMITATIONS,
            "model": MODEL,
            "results": results,
            "usageIsSecondary": True,
            "validity": (
                "Corrected blind-prompt evaluation. Conditional procedure "
                "effectiveness includes only pairs with verified discovery and "
                "skill-tool consumption."
            ),
        },
    )
    valid = all(
        result["interpreted"] and result.get("procedureTreatmentValid")
        for result in results
    )
    return 0 if valid else 4


if __name__ == "__main__":
    raise SystemExit(main())
