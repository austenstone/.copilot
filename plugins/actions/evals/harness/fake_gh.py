#!/usr/bin/env python3

import json
import os
import sys
from pathlib import Path


DANGEROUS_PREFIXES = (
    ("workflow", "run"),
    ("run", "rerun"),
    ("run", "cancel"),
    ("run", "delete"),
    ("repo", "clone"),
)
DANGEROUS_API_METHODS = {"DELETE", "PATCH", "POST", "PUT"}


def load_rules(path: Path) -> list[dict[str, object]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    rules = document.get("rules")
    if not isinstance(rules, list):
        raise ValueError("fixture must contain a rules array")
    return rules


def is_dangerous(argv: tuple[str, ...]) -> bool:
    if any(argv[: len(prefix)] == prefix for prefix in DANGEROUS_PREFIXES):
        return True
    if argv[:1] != ("api",):
        return False
    methods = {
        argv[index + 1].upper()
        for index, value in enumerate(argv[:-1])
        if value in {"-X", "--method"}
    }
    return bool(methods & DANGEROUS_API_METHODS)


def main() -> int:
    argv = tuple(sys.argv[1:])
    fixture_path = os.environ.get("ACTIONS_EVAL_GH_FIXTURE")
    if not fixture_path:
        print("fake gh: ACTIONS_EVAL_GH_FIXTURE is required", file=sys.stderr)
        return 64
    if is_dangerous(argv):
        print(f"fake gh: mutating or execution call rejected: {list(argv)!r}", file=sys.stderr)
        return 64

    try:
        rules = load_rules(Path(fixture_path))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"fake gh: invalid fixture: {error}", file=sys.stderr)
        return 65

    rule = next((item for item in rules if tuple(item.get("argv", [])) == argv), None)
    trace_path = os.environ.get("ACTIONS_EVAL_GH_TRACE")
    if trace_path:
        with Path(trace_path).open("a", encoding="utf-8") as trace:
            trace.write(json.dumps({"argv": argv, "matched": rule is not None}) + "\n")
    if rule is None:
        print(f"fake gh: unsupported call rejected: {list(argv)!r}", file=sys.stderr)
        return 64

    stdout = rule.get("stdout", "")
    stderr = rule.get("stderr", "")
    if stdout:
        print(stdout, end="" if str(stdout).endswith("\n") else "\n")
    if stderr:
        print(stderr, end="" if str(stderr).endswith("\n") else "\n", file=sys.stderr)
    return int(rule.get("exitCode", 0))


if __name__ == "__main__":
    raise SystemExit(main())
