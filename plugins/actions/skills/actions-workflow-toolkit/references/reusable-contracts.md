# Reusable workflow contract procedure

Trace the contract before blaming or changing either side. A reusable workflow
call is a chain of versioned interfaces, permissions, secrets, outputs, runner
access, and billing ownership.

## 1. Record the exact edge

For each relevant `jobs.<id>.uses`, record:

- Caller repository, path, and executed ref/SHA
- Literal callee `OWNER/REPO/.github/workflows/FILE@REF`
- Inputs, secrets, `permissions`, and `with` values supplied by the caller
- Event and head SHA of the run being diagnosed

Follow only edges relevant to the question. Resolve the literal callee ref; do
not substitute its default branch or assume it matches the caller's head SHA.

## 2. Read and validate the callee

With authenticated `gh`, fetch the exact file at the exact ref. Confirm
`on.workflow_call` declares every supplied input and secret with compatible
types and requiredness. Repeat for nested calls until ownership is found or an
access boundary is reached.

If the callee or ref is unreadable:

1. Preserve the exact edge and API error.
2. Mark the callee internals unavailable.
3. Continue using caller-visible job/run evidence.
4. Ask for the file or access only if it is necessary to answer the question.

Do not infer missing permissions, secrets, runner labels, or implementation
from an unreadable callee.

## 3. Compute permissions transitively

Treat the caller's token permissions as an upper bound. Along a nested chain,
`GITHUB_TOKEN` permissions can be maintained or reduced, not elevated.

For each hop:

1. Record workflow- and job-level `permissions`.
2. Determine the effective permission required by the failing operation.
3. Find the first hop where that permission is absent or reduced.
4. Propose the smallest permission at the narrowest practical job.

Do not recommend a broad write token merely because a downstream API returned
`403`; repository policy, fork context, and resource authorization also need
evidence.

## 4. Trace secrets and environments

Secrets pass only to the directly called workflow. In a chain `A -> B -> C`,
`B` must explicitly pass a secret to `C`; the fact that `A` supplied it does
not make it transitively available.

Workflow-level `env` from the caller does not propagate to the called workflow,
and callee workflow-level `env` does not propagate back. Pass non-secret values
through declared `workflow_call` inputs and return values through outputs.
Use repository, organization, or environment variables only when that shared
scope is intentional and independently verified.

`secrets: inherit` is still a direct-hop decision and does not prove that a
named secret exists. Record scope and availability without revealing values.

Environment secrets are selected by the callee job's `environment`. A caller
cannot pass an environment through `on.workflow_call`, and a callee
environment secret can take precedence over a same-named passed secret.
Environment reviewers, wait timers, and branch rules can also explain a
waiting job. Verify them only with appropriate repository access.

## 5. Trace outputs end to end

Follow the complete chain:

```text
step writes GITHUB_OUTPUT
  -> job outputs maps steps.<id>.outputs.<name>
  -> on.workflow_call.outputs maps jobs.<id>.outputs.<name>
  -> caller reads needs.<job>.outputs.<name>
```

At each mapping, check exact IDs, names, conditions, and whether the producing
step/job actually ran. For matrix-called reusable workflows, fetch the live
reuse documentation before asserting which leg supplies the final value.

## 6. Establish runner ownership and access

Record the resolved `runs-on` labels for the job that owns execution.

- GitHub-hosted usage and reusable-workflow billing belong to the caller.
- Larger runner groups must allow the caller repository.
- For self-hosted runners, verify the caller-context access rules, including
  same-owner requirements for a callee to use caller-available runners.
- A visible label does not prove an online matching runner or available
  capacity.
- An unreadable organization runner setting is an evidence boundary, not a
  capacity diagnosis.

Separate a callee-owned YAML correction from caller/org-owned runner-group or
policy changes.

## Result

Return the first broken contract edge, its evidence, owner, and minimal
correction. Stop when the requested failure is explained; do not audit every
nested workflow unless the request asks for it.
