---
name: actions-debug
description: "Diagnoses GitHub.com Actions workflows or jobs that are absent, waiting, queued, skipped, failed, cancelled, or timed out. Use when: why did this workflow not run, why is this job pending or queued, why was a job skipped, debug this failed run, who cancelled it, why did it time out, why is a required check stuck, or trace a runtime failure through reusable workflows, environments, permissions, outputs, and runner access. Excludes broad security/architecture reviews, speculative capacity claims, workflow mutation, reruns, cancellations, dispatches, approvals, and non-GitHub Actions CI."
---

# Actions Debug

Load [`actions-workflow-toolkit`](../actions-workflow-toolkit/SKILL.md) for the
helper contract, exact commands, reusable contracts, and live docs.

## Authority and mode

Default to read-only. Collect metadata, jobs, bounded logs, workflow content,
and settings the authenticated user can read. Rerunning, cancelling,
dispatching, approving a deployment, editing YAML, or changing runner,
environment, branch, or repository settings requires explicit authority.

Full diagnosis requires a shell and authenticated `gh` access to GitHub.com.
Without either, perform static-only analysis and label it. Do not claim a
runtime cause from YAML alone.

## Pin the incident

Use the exact repository, run ID, and attempt. If the request gives a run URL,
parse those values from it. Do not default to the latest run or latest attempt.

Collect with:

```bash
TOOLKIT=/path/to/actions-workflow-toolkit
python3 "$TOOLKIT/scripts/collect-run-data.py" \
  --repository OWNER/REPO --run-id RUN_ID --attempt ATTEMPT --pretty
```

Minimum runtime evidence:

- Event, workflow path, head SHA/ref, run status/conclusion, and timestamps
- Jobs, resolved runner labels, step conclusions, and relevant bounded logs
- Conditions, `needs` results, matrix inputs, environment, concurrency, or
  reusable-workflow edges relevant to the observed state
- Coverage limitations, inaccessible settings, missing logs, and provenance

Redact secret values. Missing access is `unresolved`, not `absent`.

## Classify before explaining

Use [`references/run-states.md`](references/run-states.md).

| Observed state | First question |
|---|---|
| Absent | Did the exact event/ref satisfy trigger and filter semantics? |
| Waiting | Is an environment, approval, timer, or concurrency rule holding it? |
| Queued | What runner labels/group are requested, and is routing/access known? |
| Skipped | Which job condition, upstream result, filter, or matrix decision skipped it? |
| Failed | What is the first causal failed step/job, not the loudest downstream error? |
| Cancelled | Was it manual/API, concurrency, supersession, or propagated cancellation? |
| Timed out | Which configured/platform bound ended which job or run? |

Never translate `queued` directly to "not enough runners." Capacity is one
hypothesis among label mismatch, group access, concurrency, service state, and
routing configuration.

## Follow the causal chain

1. Start at the observed state and exact attempt.
2. Find the earliest evidence that made the outcome inevitable.
3. Read only the workflow paths, callees, settings, and logs needed to test
   that cause.
4. For caller/callee failures, use the
   [reusable contract procedure](../actions-workflow-toolkit/references/reusable-contracts.md).
5. For required checks, path filters, merge queue, empty matrices, or gate
   propagation, use
   [the toolkit procedure](../actions-workflow-toolkit/references/required-checks-and-events.md).
6. Separate repo-editable YAML from repository/org-owned policy, environment,
   secret, or runner-group corrections.

Prefer a directly observed cause. If evidence supports multiple causes, rank
the hypotheses and name the single next observation that distinguishes them.

## Minimal correction

Recommend the smallest change that fixes the observed incident without
weakening required checks, permissions, environment protections, supported
matrix coverage, or cancellation semantics.

Examples:

- Correct one trigger/filter or add `merge_group`.
- Make one stable gate always evaluate and accurately propagate upstream
  failure, cancellation, expected skip, and no-work matrix outcomes.
- Add the narrow missing caller/callee permission or direct-hop secret mapping.
- Correct one output mapping.
- Grant the caller repository access to the intended runner group, if verified
  as the cause.

Do not solve a narrow failure with a whole-repository rewrite.

## Request-appropriate output

For a narrow question, return:

```text
Scope: OWNER/REPO, run RUN_ID, attempt N (full or static-only)
Observed: state plus exact job/step/event/ref evidence
Cause: fact, or ranked hypothesis with missing evidence
Correction: smallest safe change and its owner
Limitations: inaccessible or partial evidence
```

Add a timeline or exact diff only when it helps the request. Do not force a
long incident report for a one-line cause.

Stop when the observed state has a supported cause and minimal correction, or
when the exact missing evidence/authority is identified. Do not continue into
an unsolicited security, cost, or architecture review.
