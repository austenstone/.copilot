#!/usr/bin/env python3

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "harness"))
from run_eval import MODEL, PLUGIN_ROOT, confirm_model_usage, consumed_skills, hash_tree


SKILL = "actions-security-review"
PROMPT = (
    "Interpret the captured native scanner output in CASE.md, zizmor.stdout, and "
    "zizmor.stderr. First invoke the actions-security-review skill using the skill "
    "tool. Use only the supplied evidence; do not rerun scanners or modify files. "
    "Does this captured run establish a clean security scan? Start your final "
    "answer with Yes or No, then give one sentence explaining the result."
)


def final_answer(transcript: str) -> str:
    answer = ""
    for line in transcript.splitlines():
        event = json.loads(line)
        if event.get("type") == "assistant.message":
            answer = event["data"].get("content", "")
    return answer


def rejects_clean_scan(answer: str) -> bool:
    return re.match(r"^\s*No\b", answer, re.IGNORECASE) is not None


def main() -> int:
    started = time.monotonic()
    output = Path(os.environ["RUNNER_TEMP"]) / "actions-smoke"
    workspace = output / "workspace"
    workspace.mkdir()
    plugin = workspace / "plugin"
    plugin.mkdir()
    shutil.copy2(PLUGIN_ROOT / "plugin.json", plugin / "plugin.json")
    shutil.copytree(PLUGIN_ROOT / "skills", plugin / "skills")
    corpus = json.loads((Path(__file__).parent / "corpus/cases.json").read_text())
    case = next(case for case in corpus["cases"] if case["id"] == "scanner-hard-failure")
    for name, content in case["fixture"]["files"].items():
        path = workspace / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
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
        "PATH": os.environ["PATH"],
        "GITHUB_TOKEN": os.environ["GITHUB_TOKEN"],
    }
    command = [
        "copilot", "--prompt", PROMPT, "--model", MODEL, "--effort", "low",
        "--plugin-dir", str(plugin), "--available-tools", "view", "skill",
        "--deny-tool=write", "--deny-tool=shell",
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
    failures = []
    transcript, stderr, answer = "", "", ""
    returncode = None
    if missing:
        failures.append(f"Installed CLI lacks required flags: {', '.join(missing)}")
    else:
        try:
            result = subprocess.run(
                command, cwd=workspace, env=environment,
                capture_output=True, text=True, timeout=120, check=False,
            )
            returncode = result.returncode
            transcript, stderr = result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            failures.append("Copilot exceeded the 120-second timeout; no eval pass.")
        if returncode != 0:
            failures.append(f"Copilot did not complete successfully (exit {returncode}).")

    token = environment["GITHUB_TOKEN"]
    transcript = transcript.replace(token, "[REDACTED]")
    stderr = stderr.replace(token, "[REDACTED]")
    (output / "transcript.jsonl").write_text(transcript)
    (output / "stderr.txt").write_text(stderr)
    usage_path = output / "usage.json"
    if usage_path.exists():
        usage_path.write_text(usage_path.read_text().replace(token, "[REDACTED]"))
    model_ok, model_evidence = confirm_model_usage(usage_path)
    skill_evidence = consumed_skills(transcript, [SKILL])
    if returncode == 0:
        try:
            answer = final_answer(transcript)
        except json.JSONDecodeError:
            failures.append("CLI output was not valid native JSONL.")
        if not model_ok:
            failures.append("Requested model has no confirmed positive usage.")
        if not skill_evidence:
            failures.append("No successful actions-security-review skill-tool activation.")
        if not rejects_clean_scan(answer):
            failures.append("Behavioral assertion failed: final answer must begin with No.")
        if hash_tree(workspace) != before:
            failures.append("The evaluated agent changed the read-only fixture or plugin.")

    verdict = "FAIL (not an eval pass)" if failures else "PASS"
    summary = "\n".join([
        "## Actions Copilot smoke eval",
        f"**{verdict}**",
        "",
        "- Scenario: captured zizmor parse failure (exit 1, empty stdout).",
        "- Assertion: the final answer begins with `No`, rejecting a clean scan.",
        f"- CLI: {(output / 'cli-version.txt').read_text().strip()}",
        f"- Requested model: `{MODEL}`; confirmed usage: `{model_ok}`.",
        f"- Successful `{SKILL}` activation: `{bool(skill_evidence)}`.",
        f"- CLI invocations: `{int(not missing)}`; exit: `{returncode}`.",
        f"- Runtime: `{time.monotonic() - started:.1f}s`.",
        "- One enabled-only smoke case, not a comparison or performance claim.",
        "",
        f"Answer: {answer or '(none)'}",
        *[f"\nFailure: {failure}" for failure in failures],
        "",
        f"Model evidence: `{json.dumps(model_evidence, sort_keys=True)}`",
        f"Skill evidence: `{json.dumps(skill_evidence, sort_keys=True)}`",
        "",
    ])
    (output / "summary.md").write_text(summary)
    with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as stream:
        stream.write(summary)
    print(summary)
    if stderr:
        print(stderr, file=sys.stderr)
    return int(bool(failures))


if __name__ == "__main__":
    sys.exit(main())
