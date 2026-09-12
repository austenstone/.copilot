---
name: actions-workflow-toolkit
description: "Shared read-only procedures and portable helpers for evidence-backed GitHub Actions work on GitHub.com. Use when: inspect or validate workflow YAML, collect an exact run attempt, inventory a bounded workflow scope, trace a reusable workflow contract, interpret Actions cost, or find the canonical GitHub documentation for a claim. Load it with actions-debug or a review skill. Excludes standalone diagnosis, broad unsolicited repository scans, workflow mutation, reruns, cancellations, dispatches, approvals, and runner administration."
---

# Actions Workflow Toolkit

This is shared infrastructure, not a standalone report. Pair it with the skill
that owns the question:

- Runtime state or failure: `actions-debug`
- Security posture: `actions-security-review`
- Runtime or cost optimization: `actions-optimization`
- Estate design: `actions-architecture-review`

## Authority and modes

Default to read-only. Reading repository content and Actions metadata is
allowed when access exists. Editing YAML, changing settings, dispatching,
rerunning, cancelling, approving, enabling, or deleting anything requires
explicit authority in the current request.

**Full mode** requires a shell and authenticated `gh` access to the exact
GitHub.com scope. Use the portable helpers and preserve their JSON envelope.

**Static-only mode** applies when there is no shell, authenticated `gh` is
unavailable, or the target runtime evidence is inaccessible. Analyze only the
provided files. Start the answer with `Static-only analysis` and do not claim
that a run, setting, callee, secret, environment, or runner pool was verified.

GitHub Enterprise Server and other CI systems are out of scope.

## Establish the scope

Before collecting data, record only selectors needed by the request:

- Repository: exact `OWNER/REPO`
- Workflow: path and, when relevant, ref
- Runtime: run ID and attempt number
- Review: local path or explicit remote ref
- Inventory: repository/organization/input plus a caller-provided bound

Do not infer an attempt, silently switch to the default branch, or expand a
single-workflow question into a whole-repository scan.

## Use the portable helpers

The helper interface, envelope, coverage states, and exit behavior are
authoritative: [`references/helper-contract.md`](references/helper-contract.md).
Run each helper with `--help` before first use in an unfamiliar checkout.

| Need | Helper |
|---|---|
| Validate a local path or exact remote workflow scope | `scripts/scan-workflows.py` |
| Collect metadata, jobs, steps, and bounded logs for one attempt | `scripts/collect-run-data.py` |
| Build a bounded workflow inventory | `scripts/inventory-workflows.py` |

Examples:

```bash
TOOLKIT=/path/to/actions-workflow-toolkit
python3 "$TOOLKIT/scripts/scan-workflows.py" \
  --path .github/workflows/ci.yml --pretty
python3 "$TOOLKIT/scripts/collect-run-data.py" \
  --repository OWNER/REPO --run-id RUN_ID --attempt ATTEMPT --pretty
python3 "$TOOLKIT/scripts/inventory-workflows.py" \
  --repository OWNER/REPO --max-workflows 100 --pretty
```

Treat `coverage.status`, `coverage.limitations`, `diagnostics`, and
`provenance` as evidence. Partial, unavailable, timed-out, or inaccessible
input is never a clean result. Findings use exit `0`; helper execution failures
use the contract's nonzero exit codes.

If a helper is unavailable, use the bounded direct commands in
[`references/tools.md`](references/tools.md). State the degraded coverage.

## Evidence rules

Minimum evidence depends on the request:

- Static correctness: file, line, finding, tool/provenance, and coverage.
- Runtime diagnosis: repository, run, attempt, event, head SHA/ref, workflow
  path, job/step, timestamps, and the smallest relevant log or condition.
- Reusable workflows: every caller-to-callee edge and pinned ref until the
  relevant owner is found or an access boundary is reached.
- Cost: complete jobs for the selected attempt, runner identity/SKU evidence,
  execution durations, and the live rate source.

Separate facts from hypotheses. Missing access proves only that evidence is
unavailable. It does not prove a workflow, runner, secret, or setting is absent.

## Procedures and live sources

- Tool and fallback commands: [`references/tools.md`](references/tools.md)
- Canonical GitHub documentation map: [`references/docs-map.md`](references/docs-map.md)
- Required checks and event semantics: [`references/required-checks-and-events.md`](references/required-checks-and-events.md)
- Reusable workflow contracts: [`references/reusable-contracts.md`](references/reusable-contracts.md)
- Cost interpretation: [`references/cost-interpretation.md`](references/cost-interpretation.md)

Fetch the linked GitHub page before quoting limits, prices, runner labels,
retention, or other values that change. Do not copy volatile catalogs into a
report.

## Step 3 — Get real performance data

For optimization questions, separate queue time, execution time, reruns, and
billed usage. Start with Actions metrics when available, then use the exact
attempt's jobs for runner and duration evidence. The calculation and degraded
cases are in [`references/cost-interpretation.md`](references/cost-interpretation.md).

## Output and stopping condition

Answer the question asked. A narrow question may need one cause, one evidence
block, and one correction. A requested review may justify a ranked list.

Always include:

1. Exact scope and mode
2. Observed evidence and coverage limitations
3. Conclusion, with confidence or unresolved boundary
4. Smallest safe next step

Stop when the requested claim is supported or the exact missing authority or
evidence is identified. Do not continue scanning for unrelated findings.
