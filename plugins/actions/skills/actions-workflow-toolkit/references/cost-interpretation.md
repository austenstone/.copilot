# Cost interpretation procedure

Use this procedure for an exact run attempt or a bounded sample. Cost and
latency are different measurements.

## Required evidence

Collect:

- Exact repository, run ID, and attempt
- Complete job list for that attempt
- Each job's status, conclusion, `started_at`, `completed_at`, and runner labels
- Evidence identifying the runner class/SKU and billing owner
- Current rate and billing-unit rules from the
  [Actions runner pricing](https://docs.github.com/en/billing/reference/actions-runner-pricing)
  and [Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
  pages

If the job list is partial, labels are ambiguous, or a current rate cannot be
verified, return durations and an unpriced estimate boundary. Do not guess.

## Interpret the timeline

- Queue duration is before a job starts. It affects latency, not executed
  runner time.
- Job execution duration is `completed_at - started_at`.
- Workflow wall-clock duration is useful for critical-path latency, not direct
  billing arithmetic.
- Steps can overlap across jobs. Do not sum step durations as workflow latency.
- A rerun creates another attempt. Account for each executed attempt instead
  of replacing it with the latest result.

Waiting for an environment or concurrency slot is not proof of runner
consumption. A cancelled or timed-out job may still have consumed runner time
before termination. Use its timestamps.

## Calculate only with live billing rules

1. Group executed jobs by verified runner class/SKU.
2. Apply the current billing unit and rounding rule to each job independently.
3. Sum within the attempt, then across explicitly selected attempts/runs.
4. Apply the current price or included-usage rule for the repository/account.
5. Show the formula, rate-source date, and any excluded jobs.

Do not hardcode rates, OS multipliers, included minutes, or runner catalogs.
Do not use the legacy `/actions/runs/{id}/timing` response for cost: it can be
incomplete and does not provide the job-level runner identity needed for
reliable interpretation.

Reusable workflow jobs are billed in the caller's context. For larger or
self-hosted runner arrangements, verify the current product billing rules and
the runner group's ownership before assigning cost.

## Savings claims

Label evidence:

- **Measured:** comparable before/after usage or billing data.
- **Sampled:** bounded target-run data.
- **Static:** configuration suggests a candidate only.
- **Estimated:** measured inputs plus explicit assumptions.

Do not extrapolate monthly savings without verified run frequency and a
representative event/branch mix. Queue reduction is a latency benefit unless
it also changes executed jobs. A skipped job saves execution only when the
required-check and coverage semantics remain correct.

## Output

Return the selected scope, formula, live source, amount or unpriced boundary,
and confidence. Stop once the requested run/sample is explained.
