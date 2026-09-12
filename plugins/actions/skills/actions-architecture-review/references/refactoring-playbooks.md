# Refactoring playbooks

Use these sequences after classification. Do not apply all of them. Pick the dominant failure shape.

## A. Monolith playbook

Goal: split only where the dependency graph is real.

1. Freeze behavior: run `actionlint`, capture current required checks, and record the slowest or most failure-prone jobs.
2. Draw the `needs:` graph. Mark edges as real dependency, artifact dependency, environment approval, or accidental sequencing.
3. Split independent validation first: lint, unit tests, type checks, and packaging should run in parallel when they do not consume each other's artifacts.
4. Create artifacts at the first stable boundary. Downstream jobs consume artifacts; they do not rebuild the same commit.
5. Move deployment into separate jobs or workflows only after build artifacts are stable.
6. Keep check names stable until branch protection is intentionally updated.

Anti-pattern: carving a huge workflow into five reusable workflows named after old stages. That preserves the migration debt with more indirection.

## B. Sprawl playbook

Goal: make the shared path safer than copy-paste.

1. Pick one repeated job with obvious operational consequence: deploy, OIDC auth, runner setup, release, or language bootstrap.
2. Extract it into a reusable workflow if it owns job-level behavior; extract a composite action if it is only a step bundle. See [`decision-matrices.md`](decision-matrices.md).
3. Publish a canary ref and migrate one repo.
4. Fix the contract until consumers do not need repo-specific hacks.
5. Tag the first supported version.
6. Migrate a cohort of similar repos.
7. Announce the default path for new repos.
8. Add CODEOWNERS/rulesets/allowed-actions policy after the paved road exists, not before.
9. Deprecate old patterns with a date and an exception path.

Do not start with a universal platform repo that handles every language and deployment target. Start with the duplicated thing that hurts today.

Before the canary, publish a compatibility table for inputs, secrets, outputs, permissions, environments, concurrency, runners, refs, check names, and artifacts. Trace nested calls to the requested bound. Keep the old path available when inaccessible or out-of-scope consumers make the blast radius incomplete.

## C. Monorepo playbook

Goal: run the right checks for the changed graph and still satisfy branch protection.

1. Identify service/package boundaries and shared-library blast radius.
2. Add a cheap detection job that emits JSON for affected services.
3. Feed that JSON into a dynamic matrix.
4. Keep a stable required check that always runs, fails on upstream failure or cancellation, and accepts a skipped matrix only when detection explicitly proved no work.
5. Add `merge_group` wherever merge queue is part of the path.
6. Revisit cache keys after selective execution exists; caching every unnecessary job is still waste.

Implement the detector, guarded matrix, and stable reporting gate with the
canonical
[`required-checks-and-events.md`](../../actions-workflow-toolkit/references/required-checks-and-events.md)
procedure. Do not copy a permissive gate that treats every skipped matrix as
success; detector failure, invalid output, required-work failure, and
cancellation must remain visible.

`dorny/paths-filter` is a pragmatic detector when the service map is path-based. Native `paths` filters are fine for skipping entire workflows, but required checks and merge queue can make skipped workflows block merges. Design the stable required check first.

Canary with current required-check names unchanged. Add `merge_group` before enabling selective execution for a merge queue, and verify the stable check on changed, unchanged, failed, and cancelled matrix paths.

## Rollout gate shared by every playbook

Use one sequence: **canary → cohort → default → deprecate**.

- Canary one representative consumer while the old path remains runnable.
- Expand only after required checks, outputs/artifacts, permissions, approvals, concurrency, and runner behavior match the recorded contract.
- Make the pattern the default only after known consumers have a pinned supported ref and ownership.
- Deprecate only with a rollback ref, support window, and treatment for inaccessible consumers.

Stop and classify the recommendation as conditional when coverage is insufficient to identify affected checks or consumers.

## CI/CD separation

Goal: deploy what you tested.

1. Build once from the reviewed ref.
2. Attach provenance or metadata to the artifact when required by policy.
3. Promote the same artifact through environments.
4. Put approvals and OIDC trust on the environment boundary.
5. Keep deployment workflows narrow: fetch artifact, authenticate, deploy, verify.

Rebuilding per environment is an anti-pattern because production may not receive the artifact that passed CI. Use the toolkit docs map for live references on artifacts, environments, OIDC, workflow syntax, and billing implications.

## Scale limits as design constraints

Do not quote hard limits from memory. Fetch the live limits page through [`../../actions-workflow-toolkit/references/docs-map.md`](../../actions-workflow-toolkit/references/docs-map.md). The architectural question is which ceiling the estate is approaching:

| Limit family | Architecture that hits it | Design response |
|---|---|---|
| Matrix fan-out | Monorepo tests every service/runtime/region combination | Detect affected services first, then build the matrix. |
| Workflow file size | Migrated monolith with every stage in one file | Split on real dependency and ownership boundaries. |
| Nesting depth | Platform team stacks reusable workflows for every concern | Flatten contracts; do not make consumers debug a call stack. |
| Concurrency | Large estate sends every repo to the same scarce runner pool | Separate capacity planning from workflow refactors. High queue time is not YAML debt. |

Fetch the current reusable-workflow nesting limit from
[reuse workflows](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows)
before approving a deeper graph. Do not preserve an old copied limit in the
review.

## Migration debt signs

Treat these as clues, not automatic findings:

- Stage names mirror Jenkins, GitLab CI, Azure Pipelines, or CircleCI.
- One `build everything` job sets up every language and deploy target.
- Shell scripts duplicate native actions for checkout, setup, cache, artifact upload, release, or cloud auth.
- Every job waits for the previous stage even when it only needs the source tree.
- Environment promotion rebuilds instead of consuming a CI artifact.

The refactor should remove one piece of migration debt at a time. A big-bang rewrite is how teams get a prettier outage.
