#!/usr/bin/env python3

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "harness"))
from run_eval import (
    PLUGIN_ROOT,
    confirm_model_usage,
    consumed_skills,
    hash_tree,
    load_cases,
    timeout_text,
    write_json,
)
from scoring import score_response
from invariants import case_invariants


MODEL = "gpt-5.6-luna"
TOOLS = ("bash", "view", "skill")


def target_skills(case: dict) -> list[str]:
    skills = case["skills"]
    return ["actions-debug", *skills] if skills == ["actions-workflow-toolkit"] else skills


def evidence_catalog(case: dict) -> tuple[list[dict], dict[str, list[str]]]:
    catalog, aliases = [], {}
    for label, source in zip(case["evidenceIds"], case["evidenceSources"], strict=True):
        location = (
            {"file": source["file"]} if "file" in source else
            {"command": shlex.join(["gh", *case["fixture"]["ghRules"][source["gh"]]["argv"]])}
        )
        entry = next(
            (item for item in catalog if all(item.get(key) == value for key, value in location.items())),
            None,
        )
        if entry is None:
            entry = {"id": f"E{len(catalog) + 1}", **location}
            catalog.append(entry)
            aliases[entry["id"]] = []
        aliases[entry["id"]].append(label)
    return catalog, aliases


def build_prompt(case: dict) -> str:
    catalog, _ = evidence_catalog(case)
    shape = {
        "diagnosis": "natural-language diagnosis",
        "findings": ["natural-language finding"],
        "evidenceUsed": ["IDs from the evidence catalog that you actually consulted"],
        "limitations": ["natural-language uncertainty or coverage limitation"],
        "recommendation": {"action": "change, no-change, or investigate", "rationale": "why"},
        "proposedChanges": [{"path": "relative path", "summary": "proposal", "preserves": ["behavior"]}],
    }
    return "\n".join([
        "Review this public synthetic GitHub Actions case using only the supplied evidence.",
        "First invoke each listed procedure with the skill tool; do not substitute reading SKILL.md.",
        f"Procedures: {json.dumps(target_skills(case))}",
        f"Task: {case['prompt']}",
        f"Available files: {json.dumps(sorted(case['fixture']['files']))}",
        f"Evidence catalog: {json.dumps(catalog)}",
        "All available files are in scope, including files without catalog IDs.",
        "Use view to read files and bash only for the exact gh commands in the catalog.",
        "gh is fixture-backed. Unsupported commands fail locally; do not work around that boundary.",
        "Do not inspect parent directories, environment variables, or the fixture implementation.",
        "Do not execute workflows, run scanners, install tools, access the network, or edit files.",
        "Explain the decisive evidence, remaining uncertainty, and behavior to preserve.",
        "Include proposedChanges only if warranted; otherwise use an empty array. Never apply them.",
        "Return only one JSON object with this shape, using natural language rather than labels:",
        json.dumps(shape),
    ])


def materialize_case(case: dict, output: Path) -> Path:
    workspace = output / "workspace"
    workspace.mkdir()
    plugin = workspace / "plugin"
    plugin.mkdir()
    shutil.copy2(PLUGIN_ROOT / "plugin.json", plugin / "plugin.json")
    shutil.copytree(PLUGIN_ROOT / "skills", plugin / "skills")
    for name, content in case["fixture"]["files"].items():
        path = workspace / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    private = output / "private"
    bin_dir = private / "bin"
    bin_dir.mkdir(parents=True)
    gh = bin_dir / "gh"
    shutil.copy2(Path(__file__).parent / "harness/fake_gh.py", gh)
    gh.chmod(0o700)
    write_json(private / "gh-fixture.json", {"rules": case["fixture"]["ghRules"]})
    return workspace


def final_answer(transcript: str) -> str:
    answer = ""
    for line in transcript.splitlines():
        event = json.loads(line)
        if event.get("type") == "assistant.message":
            answer = event["data"].get("content", "")
    return answer


def valid_response(response: object) -> bool:
    if not isinstance(response, dict) or not isinstance(response.get("diagnosis"), str):
        return False
    for field in ("findings", "evidenceUsed", "limitations"):
        value = response.get(field)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            return False
    recommendation = response.get("recommendation")
    if (
        not isinstance(recommendation, dict)
        or recommendation.get("action") not in ("change", "no-change", "investigate")
        or not isinstance(recommendation.get("rationale"), str)
    ):
        return False
    changes = response.get("proposedChanges")
    return isinstance(changes, list) and all(
        isinstance(change, dict)
        and isinstance(change.get("path"), str)
        and isinstance(change.get("summary"), str)
        and isinstance(change.get("preserves"), list)
        and all(isinstance(value, str) for value in change["preserves"])
        for change in changes
    )


def observed_evidence(case: dict, transcript: str, trace: list[dict], workspace: Path) -> set[str]:
    starts, files = {}, set()
    for line in transcript.splitlines():
        event = json.loads(line)
        data = event.get("data", {})
        if event.get("type") == "tool.execution_start" and data.get("toolName") == "view":
            starts[data["toolCallId"]] = data.get("arguments", {}).get("path")
        if event.get("type") == "tool.execution_complete" and data.get("success") is True:
            path = starts.get(data.get("toolCallId"))
            if isinstance(path, str):
                files.add((workspace / path).resolve())
    commands = {shlex.join(["gh", *item["argv"]]) for item in trace if item["matched"]}
    catalog, _ = evidence_catalog(case)
    return {
        item["id"] for item in catalog
        if (
            "file" in item and (workspace / item["file"]).resolve() in files
            or "command" in item and item["command"] in commands
        )
    }


def assertions_for(case: dict, response: object, changed_paths: list[str],
                   observed: set[str], activations: list[dict], trace: list[dict]) -> tuple[dict, dict | None]:
    catalog, aliases = evidence_catalog(case)
    assertions = {
        "responseShape": valid_response(response),
        "targetSkills": set(target_skills(case)) <= {item["name"] for item in activations},
        "evidenceRead": {item["id"] for item in catalog} <= observed,
        "fixtureCommands": all(item["matched"] for item in trace),
        "unauthorizedEdits": not changed_paths,
    }
    if not assertions["responseShape"]:
        return assertions, None
    assertions["citedEvidenceRead"] = set(response["evidenceUsed"]) <= observed
    assertions["requiredEvidenceCited"] = {item["id"] for item in catalog} <= set(response["evidenceUsed"])
    normalized = {
        **response,
        "evidenceUsed": [
            label for item in response["evidenceUsed"] for label in aliases.get(item, [item])
        ],
    }
    score = score_response(case, normalized, changed_paths)
    assertions.update(case_invariants(case, response))
    return assertions, score


def main() -> int:
    cases = {case["id"]: case for case in load_cases()}
    parser = argparse.ArgumentParser(description="Run one enabled-only, real Copilot corpus case.")
    parser.add_argument("--case", required=True, choices=sorted(cases))
    case = cases[parser.parse_args().case]
    started = time.monotonic()
    source_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=PLUGIN_ROOT,
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    provenance = {
        "sourceCommit": source_commit,
        "graderSha256": hashlib.sha256((Path(__file__).parent / "harness/invariants.py").read_bytes()).hexdigest(),
        "fixtureSha256": hashlib.sha256(json.dumps(case["fixture"], sort_keys=True).encode()).hexdigest(),
        "fixtureRevision": case.get("fixtureRevision", 1),
    }
    output = Path(os.environ["RUNNER_TEMP"]) / "actions-smoke"
    workspace = materialize_case(case, output)
    before = hash_tree(workspace)
    home = output / "home"
    home.mkdir()
    environment = {
        "CI": "true",
        "HOME": str(home),
        "COPILOT_HOME": str(home / ".copilot"),
        "COPILOT_CUSTOM_INSTRUCTIONS_DIRS": "",
        "COPILOT_MULTIPLEXER": "none",
        "COPILOT_OTEL_ENABLED": "false",
        "PATH": f"{output / 'private/bin'}:{os.environ['PATH']}",
        "GITHUB_TOKEN": os.environ["GITHUB_TOKEN"],
        "ACTIONS_EVAL_GH_FIXTURE": str(output / "private/gh-fixture.json"),
        "ACTIONS_EVAL_GH_TRACE": str(output / "gh-trace.jsonl"),
    }
    command = [
        "copilot", "--prompt", build_prompt(case), "--model", MODEL, "--effort", "low",
        "--plugin-dir", str(workspace / "plugin"), "--available-tools", *TOOLS,
        "--deny-tool=write", "--allow-tool=shell(gh:*)",
        "--deny-url=https://*", "--deny-url=http://*",
        "--secret-env-vars=GITHUB_TOKEN",
        "--no-custom-instructions", "--disable-builtin-mcps",
        "--no-ask-user", "--no-bash-env", "--disallow-temp-dir",
        "--no-remote-export", "--no-auto-update",
        "--output-format", "json", "--stream", "off",
        "--log-level", "error", "--log-dir", str(output / "logs"),
        "--usage-output-file", str(output / "usage.json"),
    ]
    help_text = (output / "cli-help.txt").read_text()
    missing = sorted({
        arg.split("=")[0] for arg in command
        if arg.startswith("--") and arg.split("=")[0] not in help_text
    })
    blockers = []
    transcript, stderr, answer = "", "", ""
    returncode = None
    if missing:
        blockers.append(f"Installed CLI lacks required flags: {', '.join(missing)}")
    else:
        try:
            result = subprocess.run(
                command, cwd=workspace, env=environment,
                capture_output=True, text=True, timeout=120, check=False,
            )
            returncode = result.returncode
            transcript, stderr = result.stdout, result.stderr
        except subprocess.TimeoutExpired as error:
            transcript, stderr = timeout_text(error.stdout), timeout_text(error.stderr)
            blockers.append("Copilot exceeded the 120-second timeout; partial evidence retained.")
        if returncode != 0:
            blockers.append(f"Copilot did not complete successfully (exit {returncode}).")

    token = environment["GITHUB_TOKEN"]
    transcript = transcript.replace(token, "[REDACTED]")
    stderr = stderr.replace(token, "[REDACTED]")
    (output / "transcript.jsonl").write_text(transcript)
    (output / "stderr.txt").write_text(stderr)
    usage_path = output / "usage.json"
    if usage_path.exists():
        usage_path.write_text(usage_path.read_text().replace(token, "[REDACTED]"))
    model_ok, model_evidence = confirm_model_usage(usage_path, expected_model=MODEL)
    if not model_ok:
        blockers.append("Requested model has no exclusive positive native usage.")
    skill_evidence = consumed_skills(transcript, target_skills(case))
    trace_path = output / "gh-trace.jsonl"
    trace = [json.loads(line) for line in trace_path.read_text().splitlines()] if trace_path.exists() else []
    after = hash_tree(workspace)
    changed = sorted(path for path in before.keys() | after.keys() if before.get(path) != after.get(path))
    observed, response, assertions, score = set(), None, {}, None
    try:
        answer = final_answer(transcript)
        observed = observed_evidence(case, transcript, trace, workspace)
    except json.JSONDecodeError:
        blockers.append("CLI output was not valid native JSONL.")
    if not blockers:
        try:
            response = json.loads(answer)
        except json.JSONDecodeError:
            response = None
        assertions, score = assertions_for(case, response, changed, observed, skill_evidence, trace)
    verdict = "SETUP_BLOCKED" if blockers else "PASS" if all(assertions.values()) else "FAIL"
    result = {
        "caseId": case["id"], "verdict": verdict, "blockers": blockers,
        "model": MODEL, "modelConfirmed": model_ok, "modelEvidence": model_evidence,
        "targetSkills": target_skills(case), "skillEvidence": skill_evidence,
        "assertions": assertions, "legacyScore": score, "response": response,
        "provenance": provenance,
        "observedEvidence": sorted(observed), "changedPaths": changed,
        "cliInvocations": int(not missing), "exitCode": returncode,
        "durationSeconds": round(time.monotonic() - started, 1),
    }
    write_json(output / "result.json", result)
    summary = "\n".join([
        f"## Actions Copilot eval: {case['id']}",
        f"**{verdict}**",
        "",
        f"- CLI: {(output / 'cli-version.txt').read_text().splitlines()[0]}",
        f"- Requested model: `{MODEL}`; confirmed usage: `{model_ok}`.",
        f"- Target skills: `{', '.join(target_skills(case))}`.",
        f"- Consumed skills: `{', '.join(item['name'] for item in skill_evidence) or '(none)'}`.",
        f"- CLI invocations: `{int(not missing)}`; exit: `{returncode}`.",
        f"- Runtime: `{result['durationSeconds']}s`.",
        f"- Grader/fixture commit: `{source_commit}`; fixture revision: `{provenance['fixtureRevision']}`.",
        "- Enabled-only case-specific invariants; legacy dimension scores are diagnostic only.",
        "",
        "| Assertion | Result |",
        "|---|---|",
        *[f"| {name} | {'PASS' if passed else 'FAIL'} |" for name, passed in assertions.items()],
        *[f"\nSetup blocker: {blocker}" for blocker in blockers],
        "",
        "<details><summary>Answer and native evidence</summary>",
        "",
        "```json",
        answer or "(none)",
        "```",
        "",
        f"Model evidence: `{json.dumps(model_evidence, sort_keys=True)}`",
        f"Skill evidence: `{json.dumps(skill_evidence, sort_keys=True)}`",
        "",
        "</details>",
    ])
    (output / "summary.md").write_text(summary)
    with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as stream:
        stream.write(summary)
    print(summary)
    if stderr:
        print(stderr, file=sys.stderr)
    return int(verdict != "PASS")


if __name__ == "__main__":
    sys.exit(main())
