#!/usr/bin/env python3
"""Validate each callable skill can be copied with the toolkit."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
TOOLKIT = SKILLS / "actions-workflow-toolkit"
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def relative_targets(path: Path) -> list[Path]:
    targets = []
    for target in LINK.findall(path.read_text(encoding="utf-8")):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        file_part = target.partition("#")[0]
        if file_part:
            targets.append((path.parent / file_part).resolve())
    return targets


def main() -> int:
    failures = []
    skill_dirs = sorted(path.parent for path in SKILLS.glob("*/SKILL.md"))

    for skill in skill_dirs:
        allowed = (skill.resolve(), TOOLKIT.resolve())
        for markdown in skill.rglob("*.md"):
            for target in relative_targets(markdown):
                if not target.exists():
                    failures.append(
                        f"{markdown.relative_to(ROOT)}: missing {target}"
                    )
                    continue
                if not any(target == root or root in target.parents for root in allowed):
                    failures.append(
                        f"{markdown.relative_to(ROOT)}: copy-unsafe link {target}"
                    )

    if failures:
        print("portable layout failures:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1

    print(f"all {len(skill_dirs)} skills are portable with the bundled toolkit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
