# GitHub Actions documentation map

Use this as a selective map to canonical GitHub.com documentation. Fetch the
linked page before making a load-bearing claim. Do not duplicate live limits,
prices, runner catalogs, or retention values in local references.

## Syntax and semantics

| Question | Canonical source |
|---|---|
| Workflow/job/step syntax, `if`, `needs`, `permissions`, `concurrency`, filters | [Workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax) |
| Event payloads and activity types | [Events that trigger workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows) |
| Expressions and status functions | [Evaluate expressions](https://docs.github.com/en/actions/reference/workflows-and-actions/expressions) |
| `github`, `needs`, `matrix`, `runner`, and other contexts | [Contexts reference](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts) |
| Variables, environment files, and outputs | [Variables reference](https://docs.github.com/en/actions/reference/workflows-and-actions/variables) |
| Current Actions limits | [Actions limits](https://docs.github.com/en/actions/reference/limits) |

## Limits

Use the [Actions limits](https://docs.github.com/en/actions/reference/limits)
page for every hard number. Fetch it at answer time.

## Runs, checks, and deployments

| Question | Canonical source |
|---|---|
| View run history, jobs, logs, and reruns | [Viewing workflow run history](https://docs.github.com/en/actions/how-tos/monitor-workflows/view-workflow-run-history) |
| Enable runner and step debug logging | [Enable debug logging](https://docs.github.com/en/actions/how-tos/monitor-workflows/enable-debug-logging) |
| REST fields for runs, attempts, jobs, logs, and pending deployments | [Workflow runs REST API](https://docs.github.com/en/rest/actions/workflow-runs) |
| Required status checks and merge requirements | [About protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches) |
| Troubleshoot required checks | [Required status check troubleshooting](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks) |
| Merge queue and `merge_group` | [Managing a merge queue](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue) |
| Environments, reviewers, wait timers, and deployment protection | [Managing environments](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments) |

## Reusable workflows and security

| Question | Canonical source |
|---|---|
| Inputs, secrets, outputs, nesting, matrix calls, and access | [Reuse workflows](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows) |
| Caller/callee syntax and supported keywords | [Reusing workflow configurations](https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations) |
| `GITHUB_TOKEN` permissions | [Authenticate with `GITHUB_TOKEN`](https://docs.github.com/en/actions/tutorials/authenticate-with-github_token) |
| Secrets behavior and redaction | [Secrets reference](https://docs.github.com/en/actions/reference/security/secrets) |
| Environments and environment secrets | [Environments reference](https://docs.github.com/en/actions/reference/deployments-and-environments) |
| Actions hardening and trust boundaries | [Secure use reference](https://docs.github.com/en/actions/reference/security/secure-use) |

## Performance and cost

| Question | Canonical source |
|---|---|
| Cache lookup, scope, and restore keys | [Dependency caching](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching) |
| Workflow/job concurrency and cancellation | [Control workflow concurrency](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency) |
| Matrix include/exclude, failure, and parallelism | [Run job variations](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/run-job-variations) |
| GitHub-hosted labels and current specifications | [GitHub-hosted runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners) |
| Larger runner groups, access, and capabilities | [Larger runners](https://docs.github.com/en/actions/reference/runners/larger-runners) |
| Self-hosted labels, groups, routing, and access | [Self-hosted runners](https://docs.github.com/en/actions/reference/runners/self-hosted-runners) |
| Autoscaling and Actions Runner Controller | [Autoscaling with ARC](https://docs.github.com/en/actions/tutorials/use-actions-runner-controller) |
| Queue time, run time, and failure-rate dashboards | [View Actions metrics](https://docs.github.com/en/actions/how-tos/administer/view-metrics) |
| Current runner prices and billing units | [Actions runner pricing](https://docs.github.com/en/billing/reference/actions-runner-pricing) |
| Included usage, storage, and billing ownership | [Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions) |

## Measurement and troubleshooting

Use [View Actions metrics](https://docs.github.com/en/actions/how-tos/administer/view-metrics)
for queue time, run time, and failure rate. Use
[Workflow runs REST API](https://docs.github.com/en/rest/actions/workflow-runs)
for exact run-attempt jobs and logs, and
[Enable debug logging](https://docs.github.com/en/actions/how-tos/monitor-workflows/enable-debug-logging)
only when existing evidence is insufficient.

## External tool authority

- [`actionlint` checks](https://github.com/rhysd/actionlint/blob/main/docs/checks.md)
- [`zizmor` audit documentation](https://docs.zizmor.sh/audits/)

These tools are evidence sources, not GitHub product documentation. Prefer the
GitHub links above for platform semantics.
