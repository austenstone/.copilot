# Run-state triage

Start with one exact repository, run/attempt when one exists, event, head SHA,
workflow path, and timestamps. Use the smallest branch below that matches the
observed state.

## Absent

An absent run has no run ID. Prove whether one should have been created.

1. Identify the exact event delivery or user action, target/base branch, head
   SHA, activity type, and time window.
2. Read the workflow at the ref GitHub uses for that event. Do not substitute
   the current default-branch file without checking event semantics.
3. Evaluate event, activity type, branch/tag, path, and commit-message filters.
4. Check workflow state and whether the event requires the workflow to exist
   on the default branch.
5. Search a narrow run window by workflow/event/SHA.

Conclude `not triggered`, `workflow unavailable/disabled`, or `unresolved
event evidence`. Do not scan every repository workflow to explain one absence.

## Waiting

Waiting means GitHub created work but has not made it runnable.

Check, in order:

1. Job/environment status and pending deployment metadata
2. Required reviewers, wait timers, branch/tag deployment rules, and custom
   protection rules
3. Workflow/job concurrency and an older in-progress holder
4. Explicit delays or dependent jobs that have not completed

Name the holding rule and its owner. Do not recommend bypassing a protection
rule unless explicitly requested and authorized.

## Queued

Queued means runnable work has not acquired a runner. It does not identify why.

1. Record requested and resolved `runs-on` labels and runner group.
2. Classify the intended target: standard GitHub-hosted, larger runner,
   self-hosted, or unresolved expression.
3. Verify repository access to larger/self-hosted runner groups.
4. For self-hosted/ARC, verify a matching online/idle runner or scale-set
   evidence when access exists.
5. Check org/repo concurrency and GitHub service evidence if relevant.

Possible conclusions are label mismatch, group-access denial, no matching
online runner, verified capacity pressure, service issue, or unresolved. Never
assume capacity from queue duration alone.

## Skipped

Distinguish an absent workflow from a skipped job or step.

1. Evaluate the exact `if` expression with the recorded contexts.
2. Inspect upstream `needs.<job>.result` values and default success gating.
3. Inspect matrix generation, `include`/`exclude`, and no-work outputs.
4. Check whether cancellation or failure propagated through dependencies.
5. For required checks, determine whether the workflow was filter-skipped
   before creation or a stable in-workflow gate reported a result.

An expected no-work skip is valid only when a stable required gate still
reports the intended conclusion.

## Failed

1. Find the earliest failed job on the causal path.
2. Find the first causal failed step, action, service, or runner setup stage.
3. Read the smallest useful log region plus exit code/error annotation.
4. Separate application/test failure from workflow contract, permission,
   environment, action, runner, or GitHub service failure.
5. Trace downstream failures only if they obscure or compound the first cause.

Do not treat a final aggregation job as root cause when it correctly reports an
earlier failure.

## Cancelled

Use run/job metadata and concurrency configuration to distinguish:

- Manual or API cancellation
- `concurrency.cancel-in-progress`
- A superseding run or merge-queue update
- Parent/upstream cancellation propagated to dependent work
- Shutdown caused by a timeout or platform incident

For a concurrency hold or supersession, identify whether the affected work was
running or pending using the toolkit's
[concurrency procedure](../../actions-workflow-toolkit/references/concurrency.md).

Preserve cancellation in any replacement gate. `always()` makes evaluation
possible; it does not mean the gate should turn cancellation into success.

## Timed out

1. Compare timestamps with step-level command timeouts, job
   `timeout-minutes`, and applicable platform bounds.
2. Identify the job or step active at termination.
3. Fetch the live platform limit before claiming it was reached.
4. Separate execution timeout from environment wait, queue wait, log loss, or
   an external command's own timeout.

Recommend extending a timeout only after explaining why the work is expected
to complete safely. A hang usually needs a bounded command or root-cause fix,
not a larger number.
