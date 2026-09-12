from __future__ import annotations

import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TOOLKIT = Path(__file__).resolve().parents[1]
TOOLS = TOOLKIT / "references" / "tools.md"
FALLBACK = re.compile(
    r"<!-- scanner-fallback:start -->\s*```bash\n(.*?)\n```\s*"
    r"<!-- scanner-fallback:end -->",
    re.DOTALL,
)


def executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


class DocumentedScannerFallbackTests(unittest.TestCase):
    def setUp(self) -> None:
        match = FALLBACK.search(TOOLS.read_text(encoding="utf-8"))
        self.assertIsNotNone(match, "documented scanner fallback block is missing")
        self.script = match.group(1)

    def run_fallback(
        self, actionlint_output: str
    ) -> tuple[subprocess.CompletedProcess[str], set[str], list[str]]:
        with tempfile.TemporaryDirectory(dir=TOOLKIT / "tests") as directory:
            work = Path(directory)
            bin_dir = work / "bin"
            bin_dir.mkdir()
            executable(bin_dir / "timeout", "#!/bin/sh\nshift\nexec \"$@\"\n")
            executable(
                bin_dir / "actionlint",
                "#!/bin/sh\n"
                "touch actionlint.called\n"
                f"printf '%s\\n' '{actionlint_output}'\n"
                "exit 1\n",
            )
            executable(
                bin_dir / "zizmor",
                "#!/bin/sh\n"
                "touch zizmor.called\n"
                "printf '%s\\n' '[]'\n"
                "exit 13\n",
            )
            executable(
                bin_dir / "jq",
                f"#!{sys.executable}\n"
                "import json, sys\n"
                "value = json.load(open(sys.argv[-1], encoding='utf-8'))\n"
                "assert isinstance(value, list)\n"
                "with open('validated.txt', 'a', encoding='utf-8') as output:\n"
                "    output.write(sys.argv[-1] + '\\n')\n",
            )
            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
            result = subprocess.run(
                ["bash", "-c", self.script],
                cwd=work,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            calls = {
                path.name.removesuffix(".called") for path in work.glob("*.called")
            }
            validated = (
                (work / "validated.txt").read_text(encoding="utf-8").splitlines()
                if (work / "validated.txt").exists()
                else []
            )
        return result, calls, validated

    def test_findings_exits_survive_errexit_and_both_outputs_are_validated(self) -> None:
        result, calls, validated = self.run_fallback("[]")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, {"actionlint", "zizmor"})
        self.assertEqual(validated, ["actionlint.json", "zizmor.json"])

    def test_invalid_actionlint_json_fails_before_zizmor_is_accepted(self) -> None:
        result, calls, validated = self.run_fallback("not-json")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, {"actionlint"})
        self.assertEqual(validated, [])


if __name__ == "__main__":
    unittest.main()
