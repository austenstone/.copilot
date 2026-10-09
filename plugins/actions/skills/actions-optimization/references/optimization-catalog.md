# Actions Optimization Catalog

The full menu of cost and performance levers, grouped by where they act. Use [`customer-checklist.md`](customer-checklist.md) to run a conversation and [`decision-tree.md`](decision-tree.md) to choose a lever from evidence. This file is the "what else could we try" list.

Rules that apply to every row:

- Measure first. Each lever needs a baseline and a canary (SKILL.md sections 2 and 6).
- Fetch prices, limits, runner specs, and retention values live through [`docs-map.md`](../../actions-workflow-toolkit/references/docs-map.md). This file deliberately carries none.
- Default to GitHub-hosted compute. Pick the cost-to-performance sweet spot, not the cheapest SKU.

Priority order when everything looks possible: **stop unnecessary work → stop wasted work → right-size compute → speed up the work that remains → govern so it stays fixed.** Removing a run beats making it faster.

## 1. Stop unnecessary work (triggers)

| Lever | Look for | Watch for |
|---|---|---|
| Path and branch filters | Docs-only or unrelated-package changes running full CI | Filtered workflows can leave required checks pending; path filters have documented diff limits (very large pushes always run; only a bounded window of changed files is evaluated). See [troubleshooting](https://docs.github.com/en/actions/how-tos/troubleshoot-workflows) |
| Internal change detection | Required workflows that must always report | Use the stable-gate pattern in [`fix-patterns.md`](fix-patterns.md) so "skip" is an explicit, successful result |
| Duplicate `push` + `pull_request` | Every PR commit runs twice | Keep default-branch `push` validation |
| Activity types | `pull_request` on `labeled`, `edited`, `assigned` | Restrict `types:` to what the workflow needs |
| Bot and generated commits | Dependency bots, release tooling, or workflows that commit and retrigger | Avoid loops; [skip instructions](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/skip-workflow-runs) only cover some events |
| Schedules | Hourly or nightly crons that rarely find anything new; weekend runs; jobs on the hour | Weekday working-hours crons, off-the-hour minutes, or event triggers instead |
| Reactive over polling | Jobs that loop and sleep waiting for an external system | Trigger on `workflow_run`, `repository_dispatch`, or a webhook; never pay to wait |
| Monorepo affected-only builds | Every package built for a one-package change | Dynamic matrix of changed packages plus shared-dependency fan-in; keep global contract tests |
| Validate locally first | Lint/format failures discovered in CI | Pre-commit hooks or local scripts that mirror the CI gate |

## 2. Stop wasted work (cancellation, failures, rounding)

| Lever | Look for | Watch for |
|---|---|---|
| Cancel superseded runs | Old PR runs finishing after a new push | Scope the `concurrency` group by workflow and PR; never cancel default-branch or deploy runs blindly. Measure cancellation latency too: minutes before cancellation still bill |
| `timeout-minutes` | Hung jobs running to the default ceiling | Set per job from observed p99 plus headroom |
| Fail-fast ordering | Heavy build/test starts before cheap lint/typecheck | Fast gate job, then `needs:` fan-out |
| Matrix `fail-fast` | Remaining legs keep running after a decisive failure | Enable on PRs; keep full diagnostics on the default branch if needed |
| Flake and rerun reduction | Same SHA fails then passes; rerun minutes | Detect flakes by same-commit retry outcome; fix isolation, readiness, or dependency fetches before runtime tuning |
| Per-job rounding tax | Many jobs under a minute, metadata/notify jobs, visual-only job splits | Consolidate when isolation, permissions, and failure boundaries allow. Don't merge a long critical-path job to save seconds |
| Fewer, fatter jobs | Fan-out where setup dominates each leg | Parallelism must beat repeated setup + rounding |
| Prefer `run` over heavy actions | Marketplace actions that download large bundles or containers per job | Use preinstalled tools or a short script when the action adds only overhead |

## 3. Right-size compute (runners)

Runner moves worth testing. Fetch current specs and rates from [GitHub-hosted runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners) and the pricing page before quoting.

| Current workload | Candidate | Why test it | Watch for |
|---|---|---|---|
| Short, light Linux automation | `ubuntu-slim` | Lower rate for jobs that don't need a full VM | Runs in a container; no Docker-in-Docker or low-level host access |
| x64 Linux job | `ubuntu-24.04-arm` or ARM64 larger runner | Lower ARM64 rate, often equal or better speed | Native binaries, container image architecture, third-party actions |
| Oversized runner | Next smaller tier | Lower rate when CPU/memory sit idle | Runtime increase can erase savings |
| CPU-bound compile/test | Next larger tier | Shorter wall clock; can be cheaper per run | Only if the tool parallelizes enough to beat the rate multiplier |
| Memory-bound job | Higher-memory tier | Avoid paging, OOM, and throttled parallelism | Don't buy CPU just to get memory |
| Windows x64 job | `windows-11-arm` | ARM64 economics for compatible Windows work | Visual Studio, native deps, installers |
| macOS | `macos-*-xlarge` vs `macos-*-large` | Different architectures (xlarge is Apple silicon, large is Intel), not just sizes | Benchmark exact Xcode, simulator, and signing workload |
| CPU-only job on GPU runner | CPU runner | Stop paying for an idle GPU | Hidden GPU dependency |
| Public-only job on a VNET pool | Non-VNET runner | Avoid private-network provisioning and data-path overhead | Allowlist or compliance needs |

Sizing method: run the same commit about 30 times per candidate (2 cores up to 96), compare p50/p90 duration and rounded minutes by SKU, and compute runner efficiency in [`savings-math.md`](savings-math.md). Check hardware utilization in the job (CPU, memory, I/O) before guessing.

## 4. Speed up the work that remains

| Lever | Look for | Watch for |
|---|---|---|
| `setup-*` cache inputs | Dependency install dominates step time | Branch-scoped cache lookup; feature branches can't read sibling caches |
| Package-store cache | Caching `node_modules` or build output directly | Cache the content-addressed store, then install cleanly |
| Cache value check | Restore time close to (or above) a fresh download | Compare restore vs. download; drop caches that don't pay; watch cache churn and eviction |
| Docker layer cache | Image builds rebuild every layer | `buildx` with `type=gha` scoped cache; order layers stable → volatile |
| Custom images | Same toolchain installed in every job | [Custom images](https://docs.github.com/en/actions/how-tos/manage-runners/larger-runners/use-custom-images) for larger runners, or container jobs with a prebuilt image |
| Package once, reuse | Each job rebuilds the same output | Build once, pass an artifact or image to downstream jobs |
| Checkout | Full history, LFS, or submodules nobody uses | Shallow (default) or sparse checkout; skip LFS/submodules unless needed |
| Test splitting and sharding | One long serial test job | Shard by timing data; balance shards |
| Parallel steps within a job | Independent steps waiting on each other on the same runner | Step-level `background`/`wait` keywords in [workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax); doesn't replace job-level parallelism |
| Matrix shape | Legs nobody needs on every PR | Run the full matrix on default branch or merge queue; dropping a supported leg is a product decision |

## 5. Network, storage, and capacity

| Lever | Look for | Watch for |
|---|---|---|
| Private networking cost | [Azure private networking](https://docs.github.com/en/enterprise-cloud@latest/admin/configuring-settings/configuring-private-networking-for-hosted-compute-products/about-azure-private-networking-for-github-hosted-runners-in-your-enterprise) runners pulling public images or packages through NAT | NAT, firewall, peering, and egress charges land on the customer's cloud bill, not GitHub's |
| Registry mirror | Large image pulls through NAT | Mirror registries/packages close to the runners |
| Subnet sizing | Pool runs out of addresses or is oversized | Size from configured pool maximum plus buffer, not observed average |
| Artifact retention | Default retention on throwaway artifacts | `retention-days` at the shortest acceptable value; see [store and share data](https://docs.github.com/en/actions/tutorials/store-and-share-data) |
| Duplicate artifacts | Every matrix leg uploads the same output | Upload once from one leg |
| Cache storage | Old or churned caches crowding the quota | [Manage caches](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manage-caches) and the cache REST API |
| Queue before concurrency | Long waits on one label | Diagnose label scarcity, matrix floods, and superseded runs before buying more concurrency |

## 6. Observe and govern

| Lever | What it gives | Notes |
|---|---|---|
| Actions Usage and Performance Metrics | Minutes, queue, run time, failure rate by repo/workflow/job/runner | First stop; see [View Actions metrics](https://docs.github.com/en/actions/how-tos/administer/view-metrics) |
| Billing usage reports and REST | Billed usage by SKU, repo, and cost center | [Usage reports](https://docs.github.com/en/billing/reference/usage-reports), [billing usage REST](https://docs.github.com/en/rest/billing/usage). Per-job cost is derived, not returned |
| Actions Data Stream | Near-real-time workflow and job events at enterprise scale | Preview at time of writing; check the [roadmap item](https://github.com/github/roadmap/issues/1193). Reconcile with billing reports |
| `workflow_run` / `workflow_job` webhooks | Event fallback when Data Stream isn't available | [Webhook payloads](https://docs.github.com/en/webhooks/webhook-events-and-payloads) |
| Cost centers | Spend attributed to teams or business units | [Cost centers](https://docs.github.com/en/billing/concepts/cost-centers) |
| Budgets and alerts | Warning before spend surprises | [Set up budgets](https://docs.github.com/en/billing/how-tos/set-up-budgets) |
| Owners and reviews | Regressions creeping back | Named owner per top-10 workflow; monthly top-N review |

Metrics worth tracking: cost per successful run, cost per merged PR, p50/p95 duration, queue time, first-attempt success rate, flake rate, time to first feedback, rounding tax, and waste ratio. Formulas live in [`savings-math.md`](savings-math.md).

## 30-day assessment plan

| Week | Focus | Exit criteria |
|---|---|---|
| 1. Baseline | 30 days of usage/billing; inventory triggers, runners, matrices, concurrency; rank by cost, waste, queue, and count | Top-N list with cost per successful run |
| 2. Remove waste | Duplicate triggers, loops, cancellation, timeouts, failure ordering, retention, rounding tax, dead caches | Waste levers canaried |
| 3. Experiment | Runner architecture and size, cache and custom-image candidates, matrix rebalance, checkout, registry/VNET latency | Measured A/B results |
| 4. Roll out and govern | Canary → expand, verify against billing, rollback thresholds, owners, dashboards, monthly review | Owners and budgets in place |

## Field lessons

Anonymized observations from customer work. Treat them as hypotheses to test, not benchmarks to quote.

- An ARM64 migration measured roughly 25% lower invoice-equivalent spend while run volume grew; cost per run fell 34-51% across the moved workflows. The win came from rate plus equal-or-better runtime, and it was measured, not estimated.
- In one large monorepo, about half of all runs did no useful work: they were triggered by changes the workflow didn't care about. Trigger hygiene beat every compute lever.
- Two private-networking customers paid thousands per month in NAT charges by pulling registry images through the NAT gateway. A registry mirror next to the runners removed most of it.
- VNET subnet sizing must follow the configured pool maximum plus buffer. Sizing from average load caused address exhaustion at peak.
- A widely repeated "20-40% savings from right-sizing" figure had no measured source. Never quote a generic percentage; measure the customer's workload.
