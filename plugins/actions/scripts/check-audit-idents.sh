#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${0}")/.."

docs="https://docs.zizmor.sh/audits/"
live="$(mktemp)"
referenced="$(mktemp)"
trap 'rm -f "${live}" "${referenced}"' EXIT

curl -sS -L --max-time 30 "${docs}" |
  sed -n 's/.*id="\([a-z][a-z0-9-]*\)".*/\1/p' |
  grep -vE '^(after|before|configuration|audit-rules|remediation|rules[a-z-]*|.*-configuration)$' |
  sort -u >"${live}"

[[ "$(wc -l <"${live}" | tr -d ' ')" -ge 20 ]] || {
  echo "could not parse the upstream zizmor audit list" >&2
  exit 1
}

python3 - <<'PY' >"${referenced}"
import pathlib
import re

root = pathlib.Path(".")
patterns = (
    re.compile(r"https://docs\.zizmor\.sh/audits/#([a-z][a-z0-9-]+)"),
    re.compile(r"""(?:ident|rule)\s*(?:==|:|in)\s*["'`]([a-z][a-z0-9-]+)["'`]"""),
)
values = set()
for path in [*root.glob("skills/**/*.md"), *root.glob("skills/**/*.py")]:
    text = path.read_text(encoding="utf-8")
    for pattern in patterns:
        values.update(pattern.findall(text))

verify = root / "test-corpus/verify.sh"
if verify.exists():
    text = verify.read_text(encoding="utf-8")
    match = re.search(r"for rule in (.*?); do", text, re.S)
    if match:
        values.update(re.findall(r"[a-z][a-z0-9-]+", match.group(1)))

print("\n".join(sorted(values)))
PY

if [[ ! -s "${referenced}" ]]; then
  echo "no consumed zizmor identifiers found" >&2
  exit 1
fi

invented="$(comm -13 "${live}" "${referenced}")"
if [[ -n "${invented}" ]]; then
  echo "unknown referenced zizmor identifiers:" >&2
  awk '{print "  " $0}' <<<"${invented}" >&2
  exit 1
fi

echo "all $(wc -l <"${referenced}" | tr -d ' ') consumed zizmor identifiers exist upstream"
