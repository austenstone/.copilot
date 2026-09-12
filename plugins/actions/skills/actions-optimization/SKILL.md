---
name: actions-optimization
description: "Makes GitHub Actions workflows faster and cheaper by separating queue delay, execution wall clock, rounded job minutes, rerun waste, and billed cost before proposing a bounded change. Use when: CI is slow, reduce Actions minutes or cost, diagnose queueing or flakes, improve caches, tune matrices, right-size runners, or reduce unnecessary runs. Load actions-workflow-toolkit for helper contracts, scanners, and live documentation links."
---

# Actions Optimization

Load [`actions-workflow-toolkit`](../actions-workflow-toolkit/SKILL.md). Optimize from evidence, not YAML aesthetics.

## 1. Define the question and guardrails

Record the exact repository, workflow/run, branch or SHA, attempt, observation window, and whether the goal is latency, reliability, rounded minutes, or invoice cost.

Before changing triggers, job names, matrices, runners, or reusable workflows:

- Record required check contexts from the applicable ruleset or branch protection. If inaccessible, mark this unknown and do not claim a filter or rename is safe.
- Record the supported OS, architecture, runtime/version, service, and integration matrix. Dropping a leg is a product decision, never an optimization assumption.
- Trace `jobs.<id>.uses` to the file/ref that owns the configuration and behavior, and list known callers. Reusable-workflow usage is billed to the caller, so attribute billing to the calling repository while keeping configuration ownership with the pinned callee.
- Separate repo-editable YAML from org settings such as runner groups, concurrency limits, capacity, and spending policy.

## 2. Collect the smallest sufficient evidence

Use this order and stop when the question is answered:

1. Actions Performance Metrics for queue time, run time, and failure rate.
2. Actions Usage Metrics or billing export for minutes/cost concentration.
3. One or more exact run attempts for job/step timing:

   ```bash
   python3 ../actions-workflow-toolkit/scripts/collect-run-data.py \
     --repository OWNER/REPO --run-id RUN_ID --attempt ATTEMPT --pretty
   ```

   Omit `--attempt` only when "latest attempt" is intentional; use
   `--all-attempts --max-attempts N` for the latest bounded repeated-attempt
   range. Logs are not fetched by default. Probe only named jobs with repeated
   `--log-job-id ID` options.
   Check per-attempt `coverage`, `total_count`, counted/reused IDs, and
   provenance before using the result. A bounded run sample is **Sampled**
   evidence, not frequency, usage, or invoice truth.

4. Static workflow inspection only when the question depends on configuration.

Scanner use is conditional:

- Telemetry-only diagnosis: do not run `actionlint` or `zizmor`.
- Proposed or applied YAML edit: run `actionlint` on the affected workflow before and after.
- Security/trust question, or an edit to permissions, triggers, credentials, caches, or untrusted expressions: also run `zizmor`.
- If a scanner is unavailable, state that limitation. Do not install tools unless the caller authorized it.

Use live documentation through [`references/docs-map.md`](../actions-workflow-toolkit/references/docs-map.md). Do not copy prices, limits, or runner specifications from memory.

## 3. Keep the accounting planes separate

| Plane | Calculation | Claim |
|---|---|---|
| Run created-to-started | run `created_at` → `run_started_at` | Raw elapsed provenance only. It is not runner queue time and cannot establish capacity pressure, especially across reruns. |
| Job waiting | job `created_at` → `started_at` | Observed job delay. Use Performance Metrics and runner-label correlation before attributing it to capacity. |
| Wall clock | selected-attempt job execution span | Latency proxy. The jobs API lacks the `needs` graph, so do not call it a reconstructed dependency critical path. |
| Rounded job minutes | `ceil(job duration / 60s)` for each uniquely identified selected-attempt job | Cost-estimate input. Exclude jobs reused from another attempt and disclose unfinished/missing durations. |
| Billed cost | Billing/usage truth, or rounded minutes × a verified live SKU rate with billing assumptions | Never infer a SKU/rate from an unknown label. If visibility, included minutes, SKU, rate, or invoice treatment is unknown, cost is unavailable. |

Treat `null`, unfinished, cancelled, skipped, inaccessible, and missing-log evidence explicitly. Never convert partial coverage into a clean result.

Evidence grades:

- **Measured:** target before/after telemetry or billing; quantify the observed window.
- **Sampled:** bounded target run/job evidence; describe only the sample.
- **Static:** workflow/configuration evidence; call it a candidate or risk.
- **Estimated:** measured inputs plus an unmeasured candidate; show assumptions and require a canary.

## 4. Diagnose in order

1. **Measured queue/job waiting dominates:** investigate runner supply, org concurrency, runner-label scarcity, matrix fan-out, and superseded runs. Do not infer this from run created-to-started elapsed and do not start with cache tuning.
2. **Failures/reruns dominate:** fix flake, service readiness, dependency fetch instability, isolation, or fail-fast behavior before runtime tuning.
3. **Runs trigger unnecessarily:** consider safe path/branch filters, monorepo change detection, or PR-only cancellation. Preserve required check contexts and default-branch validation.
4. **Execution dominates:** use job and step timings to target dependency caching, checkout, Docker layers, test parallelism, runner sizing, matrix shape, or job graph overhead.

Detailed branching: [`references/decision-tree.md`](references/decision-tree.md). Exact patterns: [`references/fix-patterns.md`](references/fix-patterns.md).

## 5. Quantify honestly

Use [`references/savings-math.md`](references/savings-math.md).

```text
per_run_estimate = sum(selected unique job rounded minutes × verified live rate)
period_estimate = per_run_estimate × measured runs in the same period
```

No run frequency means no monthly/annual estimate. No measured candidate runtime means runner-sizing savings are hypothetical. Queue reduction alone is latency improvement, not cost savings. Public standard-runner samples may demonstrate latency/resource use without proving a bill reduction.

## 6. Canary and rollback

For runner, cache, trigger, matrix, reusable-workflow, or job-graph changes:

1. Freeze the baseline window and metrics: successful-run rounded minutes/cost where known, p50/p95 queue and wall clock, failure/rerun rate, required checks, artifacts, and support matrix.
2. Canary one workflow family, repository, service, or explicit cohort.
3. State the observation window and acceptance thresholds before rollout.
4. Define rollback: missing check/artifact, unsupported platform, cache correctness failure, higher failure rate, cost/run regression, or p95 outside threshold.
5. Expand only after the canary passes. Shared reusable workflows need a bounded caller cohort and a rollback ref.

## Required response

Return:

1. A short summary naming the dominant plane and first lever.
2. For each recommendation: evidence and grade, exact scope, required-check/support-matrix impact, proposed diff or org action, live citation, savings math or missing inputs, verification, canary, and rollback.

Say what was not checked. Never present sampled, partial, or static evidence as measured savings.
