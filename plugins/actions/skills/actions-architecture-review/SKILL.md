---
name: actions-architecture-review
description: "Reviews a GitHub Actions estate across workflows or repositories, including duplication, reusable-workflow contracts, migration debt, required-check safety, monorepo blast radius, and governance. Use when: reviewing CI architecture, standardizing workflows, choosing reusable workflows vs composite actions, reducing duplicated pipelines, designing monorepo CI, or planning cross-repository Actions refactors. Load actions-workflow-toolkit first."
---

# Actions Architecture Review

Load [`../actions-workflow-toolkit/SKILL.md`](../actions-workflow-toolkit/SKILL.md) first. Treat workflow validation as prerequisite evidence, not architecture analysis.

## Procedure

1. **Bound the estate.** Record repository, organization, or repository-manifest scope and caller-provided limits. Do not infer a wider scope.
2. **Inventory.** List and read workflows with native `gh` commands from [`references/inventory-and-classification.md`](references/inventory-and-classification.md). Record examined files/refs, limits, and inaccessible callees.
3. **Validate.** Run `actionlint` and `zizmor` against directly reviewed workflows as appropriate. Scanner floods may indicate a duplicated platform pattern, but findings are not proof of duplication.
4. **Trace contracts.** Follow reusable calls transitively within the requested depth using the toolkit's [`reusable-contracts.md`](../actions-workflow-toolkit/references/reusable-contracts.md). At every edge compare inputs, secrets, outputs, permissions, environment, concurrency, runner choice, and ref pinning. A pinned first edge does not pin a nested edge.
5. **Classify.** Choose `healthy`, `monolith`, `sprawl`, `monorepo-blast-radius`, `mixed`, or `inconclusive`. Partial inventory can support a scoped finding; it cannot prove estate-wide absence.
6. **Decide once.** Make one architecture decision with the strongest consequence and evidence. Do not return a platform wish list. Use [`references/decision-matrices.md`](references/decision-matrices.md) and say “leave it alone” when healthy.
7. **Roll out safely.** Give one canary-to-default sequence from [`references/refactoring-playbooks.md`](references/refactoring-playbooks.md). Preserve required checks and name every consumer contract that could break.

## Evidence rules

- Repeated text identifies review candidates; compare the actual job contracts before calling workflows equivalent.
- Scalar `environment` and `concurrency` values are valid shorthand, not missing objects. Preserve their meaning when reviewing or refactoring.
- For deployment concurrency, distinguish **running** cancellation from **pending** replacement. An omitted or false `cancel-in-progress` protects running work, not every pending run; the default pending policy can supersede older pending work. Do not infer retention or ordering from serialization. Apply the toolkit's [concurrency procedure](../actions-workflow-toolkit/references/concurrency.md) before describing queue behavior or proposing a policy change.
- Preserve permissions, runner labels, outputs, conditions, matrices, services, and timeouts rather than normalizing them away.
- `403` may mean policy, authorization, or rate limiting. `404` may mean absent or inaccessible. Keep that ambiguity explicit.
- Incoming caller discovery covers only examined workflow files. Dynamic references, callers outside scope, and bounded or inaccessible repositories remain unknown.
- For `A > B > C`, inspect every edge. Inputs and outputs need mapping at each boundary; secrets pass only to the next workflow; permissions cannot be assumed to increase; environments and runners are chosen where the job is defined; each remote `@ref` has its own drift risk.

## Required-check and consumer safety

Before recommending extraction, renaming, path filtering, or event changes, capture:

- current required check contexts and merge-queue use;
- caller job/workflow names that produce those checks;
- every caller and pinned version found within scope;
- required inputs, secrets, output names, permissions, environment approvals, concurrency groups, runner availability, and artifact expectations;
- inaccessible or out-of-scope consumers that prevent a safe blast-radius claim.

Keep a stable always-running required check during selective monorepo execution. Do not rename or remove checks until branch protection or rulesets are intentionally updated.

For an extraction, turn this inventory into an explicit before/after mapping for
each changed caller and new callee. Secret and credential flows are interfaces,
not an implementation detail: include their source scope, consumer, and
forwarding boundary even when supplied evidence describes them outside the YAML.
Use the toolkit's [secret and environment tracing](../actions-workflow-toolkit/references/reusable-contracts.md#4-trace-secrets-and-environments).
If names or bindings are unavailable, preserve the existing boundary and make
that part of the proposal conditional; do not invent names, expose values, or
claim compatibility has been verified.

## Output

Return two layers:

1. **Consequence:** one screen-shareable paragraph.
2. **Evidence and rollout:** scope and coverage; classification; one decision; exact supporting workflows/edges; affected contracts and consumers; required-check preservation; canary, cohort, default, and rollback signals.

Each refactor proposal must say how its applicable inputs, secret/credential
forwarding, token permissions, outputs, and environment approvals remain intact.
Carry those interfaces into the proposed change itself, not only an earlier
inventory or a generic "preserve contracts" statement. Keep intentional named
or inherited forwarding unchanged unless a separately justified change is in
scope; do not substitute `secrets: inherit` for an unresolved mapping.

If coverage cannot support a decision, classify `inconclusive`, state the smallest additional bounded collection needed, and stop. If the estate is small, valid, distinct, and cheap, classify `healthy` and recommend no refactor.
