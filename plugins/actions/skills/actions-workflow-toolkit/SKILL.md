---
name: actions-workflow-toolkit
description: "Shared procedures for using gh, actionlint, and zizmor directly on GitHub.com Actions. Use when: inspect or validate workflow YAML, inspect an exact run attempt, inventory a bounded workflow scope, trace a reusable workflow contract, interpret Actions cost, or find canonical GitHub documentation. Load relevant references with actions-debug or a review skill. Excludes broad unsolicited scans, workflow mutation, reruns, dispatches, approvals, and runner administration."
---

# Actions Workflow Toolkit

Use the native tools directly. Read only the references needed for the
question; there is no runtime wrapper or custom output format to learn.
Pair these procedures with the skill that owns the question:

- Runtime state or failure: `actions-debug`
- Security posture: `actions-security-review`
- Runtime or cost optimization: `actions-optimization`
- Estate design: `actions-architecture-review`

## Authority and modes

Default to read-only. Reading repository content and Actions metadata is
allowed when access exists. Editing YAML, changing settings, dispatching,
rerunning, cancelling, approving, enabling, or deleting anything requires
explicit authority in the current request.

Use installed `actionlint` and `zizmor` for local scans. Authenticated `gh`
access is needed only for remote evidence, not local validation. Do not
install missing tools or initiate login unless authorized.

Without runtime access, label conclusions **static-only**. Analyze the files
and scanner output available, but do not claim that a run, setting, callee,
secret, environment, or runner pool was verified.

GitHub Enterprise Server and other CI systems are out of scope.

## Establish the scope

Before collecting data, record only selectors needed by the request:

- Repository: exact `OWNER/REPO`
- Workflow: path and, when relevant, ref
- Runtime: run ID and attempt number
- Review: local path or explicit remote ref
- Inventory: repository/organization/input plus a caller-provided bound

If the attempt is unspecified, inspect run metadata and state which attempt
you selected. Do not silently switch refs or expand a single-workflow
question into a whole-repository scan.

## Native-tool gotchas

- Use `gh api --paginate` for job lists. The first page is not the entire run;
  an attempt-specific endpoint avoids silently mixing reruns.
- Scanner findings can exit nonzero. Read the native exit status, stdout,
  and stderr before deciding whether analysis succeeded.
- A failed, empty, timed-out, inaccessible, or partial scan is not clean.
  State what was examined and what remains unknown.
- A run's head SHA is not automatically proof of its executed workflow
  definition, especially for privileged triggers and reusable workflows.
- Use the command executor's timeout for long calls and stop when the agreed
  scope or collection budget is reached.

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

- Native commands and result interpretation: [`references/tools.md`](references/tools.md)
- Canonical GitHub documentation map: [`references/docs-map.md`](references/docs-map.md)
- Required checks and event semantics: [`references/required-checks-and-events.md`](references/required-checks-and-events.md)
- Reusable workflow contracts: [`references/reusable-contracts.md`](references/reusable-contracts.md)
- Cost interpretation: [`references/cost-interpretation.md`](references/cost-interpretation.md)

Fetch the linked GitHub page before quoting limits, prices, runner labels,
retention, or other values that change. Do not copy volatile catalogs into a
report.

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
