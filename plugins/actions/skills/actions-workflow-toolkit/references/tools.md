# Tooling procedures

Use `gh`, `actionlint`, and `zizmor` directly. Consult their `--help` for flags;
these procedures cover interpretation mistakes rather than replacing the
tools' interfaces. Use only the tools needed for the question.

## Exact run attempt

Keep the repository, run, and attempt explicit. If the attempt is unknown,
inspect run metadata first and state the selection.

```bash
gh run view RUN_ID --repo OWNER/REPO --attempt ATTEMPT \
  --json databaseId,attempt,workflowName,event,status,conclusion,headBranch,headSha,createdAt,startedAt,updatedAt,jobs
gh api repos/OWNER/REPO/actions/runs/RUN_ID/attempts/ATTEMPT/jobs \
  --paginate
```

Compare returned jobs with `total_count`. If collection stops before all
pages arrive, report a partial sample, not complete totals. When comparing
attempts, deduplicate job IDs and identify jobs reused from earlier attempts;
do not charge their execution time to a rerun.

Fetch logs only when needed for a specific failure:

```bash
gh run view RUN_ID --repo OWNER/REPO --attempt ATTEMPT --log-failed
```

Inspect only the relevant log region and redact secrets. Expired or denied
logs are an evidence boundary, not success. A run's head SHA/ref does not by
itself establish the executed workflow definition.

## Static validation

[`actionlint`](https://github.com/rhysd/actionlint) checks workflow syntax,
expressions, matrices, `needs`, event filters, and embedded shell/Python.
[`zizmor`](https://docs.zizmor.sh/) checks Actions-specific security patterns.

Run these as separate commands so a findings exit from one does not prevent
the other from running. Keep each command's exit status and stderr.

```bash
actionlint -format '{{json .}}' .github/workflows/ci.yml
```

```bash
zizmor --format json .github/workflows/ci.yml
```

| Tool | Completed analysis | Failure |
|---|---|---|
| actionlint | `0` with no findings, `1` with findings | Other nonzero status; read stderr |
| zizmor (default exit behavior) | `0` with no findings, `11`-`14` with findings | Other nonzero status; read stderr |

Do not chain these unguarded under `set -e`, use a findings exit to trigger a
replacement scan, pipe a scanner directly to `jq`, or discard stderr. Empty
stdout after a crash is not an empty findings array. If saving JSON, capture
stderr separately and validate the saved output before reading findings.

Use the executor's timeout for long scans. If shell linting or online audits
are skipped, say so. Do not install missing tools unless authorized.

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

## Remote scope and repository reads

```bash
gh workflow list --repo OWNER/REPO --all --json id,name,path,state
gh api --method GET repos/OWNER/REPO/contents/.github/workflows/ci.yml \
  -f ref=REF --jq '.content' | base64 -d
gh run list --repo OWNER/REPO --workflow .github/workflows/ci.yml \
  --limit 20 --json databaseId,attempt,event,status,conclusion,headBranch,headSha,createdAt
```

Do not use an unbounded code search to prove absence. Repository contents,
workflow lists, and exact run selectors are stronger evidence.

For a repository-wide security review at an explicit ref, zizmor accepts
`OWNER/REPO@REF` as its input. This is broader than a single-file review.
For actionlint, use an existing checkout or fetch the selected files and
relevant configuration at that ref; do not substitute the local default
branch. Never execute retrieved workflow code.

If remote zizmor audits fail because online checks are unavailable,
`--no-online-audits` retains remote collection but skips those checks.
`--offline` cannot fetch a remote repository. Report the reduced coverage;
do not silently retry at a different ref or call an empty collection clean.

## Mutating commands

`gh run rerun`, `gh run cancel`, `gh workflow run`, workflow enable/disable,
deployment approval, repository edits, and settings changes are outside the
read-only default. Use them only when the current request explicitly grants
that authority, and restate the exact target before execution.
