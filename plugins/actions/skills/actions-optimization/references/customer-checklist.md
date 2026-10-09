# Customer Optimization Checklist

A 15-item checklist for an optimization or cost conversation with a GitHub Actions customer. Work it top to bottom: the early items find where the minutes go; the later items change them. Each item names what to check, the evidence to pull, and the usual lever. Detail lives in [`optimization-catalog.md`](optimization-catalog.md), [`decision-tree.md`](decision-tree.md), and [`fix-patterns.md`](fix-patterns.md).

Frame the goal as the cost-to-performance sweet spot, not the cheapest runner. Faster feedback that costs slightly more can be the right answer. Say which one you are optimizing.

## How GitHub-hosted billing works (say this first)

- Each job gets its own fresh, ephemeral machine. GitHub absorbs provisioning; billing starts when the job starts running.
- Each job is rounded up to the whole minute separately. Many tiny jobs pay a rounding tax.
- Usage is metered per runner SKU. Fetch current rates, included minutes, and storage rules from the live pages in [`docs-map.md#performance-and-cost`](../../actions-workflow-toolkit/references/docs-map.md#performance-and-cost). Never quote a remembered price.
- Reusable-workflow usage bills to the caller.

## The checklist

| # | Item | What to check | Evidence | Usual lever |
|---|---|---|---|---|
| 1 | **Find the top spenders** | Which repos, workflows, and runner SKUs hold most minutes and cost | Usage Metrics; billing usage report or REST; cost centers | Focus the rest of the list on the top 5-10 workflows |
| 2 | **Measure before touching** | Baseline queue, p50/p90 duration, failure rate, cost/run | Performance Metrics; 30-day window | Freeze a baseline so wins are measured, not claimed |
| 3 | **Kill unnecessary runs** | Triggers on every push, docs-only changes, bot pushes, duplicate `push` + `pull_request` | Workflow `on:` blocks; run counts by event | Path/branch filters, internal change detection, tighter event types |
| 4 | **Cancel superseded runs** | PR pushes leave old runs running | Runs per PR head; cancelled vs. completed | PR-scoped `concurrency` with `cancel-in-progress` |
| 5 | **Tame schedules** | Cron jobs at peak hours, on weekends, or doing nothing new | `schedule` triggers; scheduled run outcomes | Weekday-only, off-the-hour, or reactive triggers |
| 6 | **Stop runaway jobs** | Jobs hitting the default timeout or hanging | Max job durations; cancelled-by-timeout runs | Explicit `timeout-minutes` per job |
| 7 | **Fail fast and cheap** | Expensive jobs start before lint/typecheck; matrix legs keep running after a decisive failure | Job graph; failed-run minutes | Fast gate job first, `needs:` to heavier work; PR-only `fail-fast` |
| 8 | **Fix flakes and reruns** | Same SHA fails then passes; rerun minutes | Run attempts per SHA; failure rate by job | Stabilize or quarantine; reruns are paid twice |
| 9 | **Right-size the runner** | CPU/memory headroom; does the tool actually parallelize | Repeated A/B runs (~30) on 2-96 cores; rounded minutes by SKU | Pick the size where minute reduction beats the rate multiplier, or latency matters more |
| 10 | **Move to the right runner family** | Linux x64 jobs that could run on ARM64; tiny jobs on full VMs; Intel macOS by accident | Runner labels by minutes; architecture blockers | ARM64, `ubuntu-slim` for light jobs, correct macOS label |
| 11 | **Cache and prebuild** | Dependency install, toolchain setup, or Docker build dominates step time; cache hit rate | Step timings; cache hit/miss in logs | `setup-*` cache, package-store cache, `buildx` GHA cache, custom images |
| 12 | **Right-shape the job graph** | Many 1-minute jobs (rounding tax) or one huge serial job | Jobs per run; per-job rounded minutes | Consolidate tiny jobs; split or shard long independent phases |
| 13 | **Trim checkout, artifacts, and storage** | Full-history clones, LFS/submodules not needed, duplicate per-leg artifacts, long retention | Checkout step time; artifact and cache storage usage | Shallow/sparse checkout, `retention-days`, upload once |
| 14 | **Check network and capacity** | Private networking egress/NAT cost, registry pulls through NAT, queue on one label | VNET config; NAT/egress bill; queue by label | Registry mirror near the runners, subnet sizing, diagnose queue before raising concurrency |
| 15 | **Govern and keep it optimized** | Who owns spend; alerts before surprises; regressions creeping back | Cost centers, budgets, alerts; scheduled review | Cost centers + budgets, monthly top-N review, Data Stream or usage exports for trend |

## Running the call

1. Items 1-2 decide the agenda. Don't tune YAML before you know which workflows matter.
2. Pull the three biggest levers for the top workflows, size each with [`savings-math.md`](savings-math.md), and grade the evidence.
3. Propose one canary per lever with a rollback condition. See SKILL.md section 6.
4. Leave the customer with owners and a 30-day plan, not a list of 40 ideas. A template plan is in [`optimization-catalog.md#30-day-assessment-plan`](optimization-catalog.md#30-day-assessment-plan).

## Discovery questions

- What hurts more today: the bill, developer wait time, or flaky reruns?
- Which workflows are required checks, and who owns them?
- Do you run on a fixed schedule anything that could run on an event instead?
- Has anyone measured a larger or ARM64 runner on your slowest job?
- Do you use private networking? Where do images and packages come from?
- Who gets alerted when Actions spend jumps, and how fast?
