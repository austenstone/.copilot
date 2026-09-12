#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${0}")/.."

command -v gh >/dev/null 2>&1 || {
  echo "gh is required" >&2
  exit 1
}

refs="$(
  python3 - <<'PY'
import pathlib
import re

pattern = re.compile(
    r"(?:^|[^A-Za-z0-9_./-])"
    r"([A-Za-z0-9][\w.-]*/[A-Za-z0-9][\w.-]*)@"
    r"([A-Za-z0-9][A-Za-z0-9._/-]*)"
)
found = {
    f"{repository}@{ref}"
    for path in pathlib.Path("skills").rglob("*.md")
    for repository, ref in pattern.findall(path.read_text(encoding="utf-8"))
}
print("\n".join(sorted(found)))
PY
)"

[[ -n "${refs}" ]] || {
  echo "no action references found" >&2
  exit 1
}

intent() {
  case "${1}" in
    OWNER/ACTION@*|OWNER/REPO@*|owner/repo@*)
      echo "placeholder"
      ;;
    tj-actions/changed-files@v45)
      echo "historical vulnerable example"
      ;;
    *)
      echo "supported example"
      ;;
  esac
}

fail=0
count=0
while IFS= read -r reference; do
  [[ -n "${reference}" ]] || continue
  count=$((count + 1))
  repository="${reference%@*}"
  ref="${reference#*@}"
  policy="$(intent "${reference}")"

  if [[ "${policy}" == "placeholder" ]]; then
    printf 'skip  %-48s %s\n' "${reference}" "${policy}"
    continue
  fi

  if ! gh api "repos/${repository}" --silent >/dev/null 2>&1; then
    printf 'FAIL  %-48s unreadable repository (%s)\n' "${reference}" "${policy}"
    fail=1
    continue
  fi

  if ! gh api "repos/${repository}/commits/${ref}" --silent >/dev/null 2>&1; then
    printf 'FAIL  %-48s unresolved ref (%s)\n' "${reference}" "${policy}"
    fail=1
    continue
  fi

  printf 'ok    %-48s %s\n' "${reference}" "${policy}"
done <<<"${refs}"

echo
if [[ "${fail}" -ne 0 ]]; then
  echo "action references must resolve or have an explicit example policy" >&2
  exit 1
fi
echo "all ${count} action references are valid for their documented intent"
