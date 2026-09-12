# Tooling procedures

Prefer the toolkit helpers because they normalize selectors, provenance,
coverage, diagnostics, and exit behavior. Their interface is defined in
[`helper-contract.md`](helper-contract.md).

## Portable helpers

Run from the toolkit directory or use absolute script paths.

```bash
TOOLKIT=/path/to/actions-workflow-toolkit
python3 "$TOOLKIT/scripts/scan-workflows.py" --help
python3 "$TOOLKIT/scripts/collect-run-data.py" --help
python3 "$TOOLKIT/scripts/inventory-workflows.py" --help
```

Common bounded calls:

```bash
python3 "$TOOLKIT/scripts/scan-workflows.py" \
  --path .github/workflows/ci.yml --pretty
python3 "$TOOLKIT/scripts/scan-workflows.py" \
  --repository OWNER/REPO --ref REF --pretty
python3 "$TOOLKIT/scripts/collect-run-data.py" \
  --repository OWNER/REPO --run-id RUN_ID --attempt ATTEMPT --pretty
python3 "$TOOLKIT/scripts/inventory-workflows.py" \
  --repository OWNER/REPO --max-workflows 100 --pretty
```

Do not discard the JSON envelope. In particular:

- A finding is a successful result, not a helper failure.
- `coverage.status: partial` is not clean coverage.
- A bound reached must remain visible in `coverage.limitations`.
- Diagnostics belong on stderr and in the safe structured document.

## Direct fallback: exact run attempt

Use only when `collect-run-data.py` is unavailable. Keep the run and attempt
explicit.

```bash
gh run view RUN_ID --repo OWNER/REPO --attempt ATTEMPT \
  --json databaseId,attempt,workflowName,event,status,conclusion,headBranch,headSha,createdAt,startedAt,updatedAt,jobs
gh run view RUN_ID --repo OWNER/REPO --attempt ATTEMPT --log-failed
gh api repos/OWNER/REPO/actions/runs/RUN_ID/attempts/ATTEMPT/jobs \
  --paginate
```

Capture only the relevant failed or diagnostic log region. Do not publish
tokens, authorization headers, or secret values. If logs expired or access is
denied, record that boundary instead of treating the absence as success.

## Direct fallback: static validation

[`actionlint`](https://github.com/rhysd/actionlint) checks workflow syntax,
expressions, matrices, `needs`, event filters, and embedded shell/Python.
[`zizmor`](https://docs.zizmor.sh/) checks Actions-specific security patterns.

The fallback deliberately requires `timeout` or GNU `gtimeout`; without one,
stop and use the helper rather than running an unbounded scan.

<!-- scanner-fallback:start -->
```bash
set -euo pipefail

TIMEOUT="$(command -v timeout || command -v gtimeout || true)"
if [[ -z "$TIMEOUT" ]]; then
  echo "bounded scanner fallback requires timeout or gtimeout" >&2
  exit 4
fi

if "$TIMEOUT" 120 actionlint -format '{{json .}}' \
  .github/workflows/ci.yml >actionlint.json 2>actionlint.err; then
  actionlint_rc=0
else
  actionlint_rc=$?
fi
case "$actionlint_rc" in
  0|1) ;;
  124|137) echo "actionlint timed out" >&2; exit 4 ;;
  *) cat actionlint.err >&2; exit 5 ;;
esac
jq -e 'type == "array"' actionlint.json >/dev/null

if "$TIMEOUT" 120 zizmor --format json \
  .github/workflows/ci.yml >zizmor.json 2>zizmor.err; then
  zizmor_rc=0
else
  zizmor_rc=$?
fi
case "$zizmor_rc" in
  0|11|12|13|14) ;;
  124|137) echo "zizmor timed out" >&2; exit 4 ;;
  *) cat zizmor.err >&2; exit 5 ;;
esac
jq -e 'type == "array"' zizmor.json >/dev/null
```
<!-- scanner-fallback:end -->

Never pipe a scanner directly to `jq` or discard stderr. A scanner can hard
fail with empty stdout, which otherwise looks clean. Bound long scans; if
shell linting or online audits are skipped, say so. Do not install a missing
tool unless the request authorizes it or existing project setup requires it.

Useful output fields:

- `actionlint`: `filepath`, `line`, `column`, `kind`, `message`, `snippet`
- `zizmor`: `ident`, `determinations`, `locations`, `fixes`, `url`, `ignored`

Qualify `actionlint` results by the scanned file set, scanner version,
`actionlint.yaml`/explicit configuration, ignore rules, and available action
metadata. Custom runner labels must be declared in actionlint configuration
before interpreting `runner-label` findings. Non-`shellcheck` findings are
strong parser/static-analysis evidence, not unconditional platform facts;
confirm version/configuration and newly shipped GitHub syntax when material.
`kind: shellcheck` can contain correctness, security, portability, or style
findings. Triage the specific ShellCheck code and severity in workflow context
instead of labelling the entire class as hygiene.
For `zizmor`, cite the finding's `url`; scanner severity is not business
priority. A suggested fix marked `unsafe` is proposal-only.

## Direct fallback: bounded repository reads

```bash
gh workflow list --repo OWNER/REPO --all --json id,name,path,state
gh api --method GET repos/OWNER/REPO/contents/.github/workflows/ci.yml \
  -f ref=REF --jq '.content' | base64 -d
gh run list --repo OWNER/REPO --workflow .github/workflows/ci.yml \
  --limit 20 --json databaseId,attempt,event,status,conclusion,headBranch,headSha,createdAt
```

Do not use an unbounded code search to prove absence. Repository contents,
workflow lists, and exact run selectors are stronger evidence.

## Mutating commands

`gh run rerun`, `gh run cancel`, `gh workflow run`, workflow enable/disable,
deployment approval, repository edits, and settings changes are outside the
read-only default. Use them only when the current request explicitly grants
that authority, and restate the exact target before execution.
