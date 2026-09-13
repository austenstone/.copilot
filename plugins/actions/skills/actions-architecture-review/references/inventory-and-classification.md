# Inventory and classification

Use native `gh` commands to inspect the agreed scope. Record the repositories,
workflow paths, refs, and limits examined; no normalized inventory format is
required.

## Bounded inventory

For a repository, resolve the requested ref once, then use that returned
commit SHA for file reads:

```bash
gh api repos/OWNER/REPO/commits/REF --jq .sha
gh api --method GET repos/OWNER/REPO/contents/.github/workflows \
  -f ref=SHA --jq '.[] | [.path, .sha] | @tsv'
gh api --method GET repos/OWNER/REPO/contents/.github/workflows/ci.yml \
  -f ref=SHA --jq .content | base64 -d
```

Use the default branch only when that is the intended scope, and state it.
The commit SHA identifies this source snapshot, not necessarily the workflow
definition executed by a particular run.

For an organization, agree a repository/workflow budget before listing:

```bash
gh repo list ORG --limit 50 --json nameWithOwner
```

This is at most 50 visible repositories, not proof of the entire estate.
Choose a limit appropriate to the request. If given a repository list, use
only those entries. Stop at the budget and describe unexamined work rather
than silently expanding the review.

## Establish coverage before findings

| Evidence | Interpretation |
|---|---|
| All files in the agreed scope inspected | Conclusions apply to that scope, not callers elsewhere. |
| Budget reached, truncated listing, or failed read | Use collected evidence, but disclose unexamined files and avoid complete totals or absence claims. |
| Rate-limit response | Stop or defer; do not treat an empty result as no workflows. |
| `403` | May be policy, authorization, or throttling; inspect the API response. |
| `404` | May be absent or inaccessible; do not infer deletion. |
| Incoming caller search | Covers only examined files and visible search results. |

Follow reusable calls only as far as needed for the decision and within the
agreed depth. For local `./.github/workflows/...` calls, read the callee at the
same resolved commit as the caller. For each remote `@ref`, record whether
the reference itself is an immutable SHA; resolving a tag today does not pin
the workflow's future calls. If a callee cannot be read, leave that edge
unverified. Use the toolkit's
[contract procedure](../../actions-workflow-toolkit/references/reusable-contracts.md)
at every edge.

## Review candidate families

Use repeated steps or text as candidates, then inspect original jobs and compare:

- trigger, condition, matrix, dependencies, runner, services, container, and timeout;
- string or object `environment` and `concurrency`;
- permissions and secret flow;
- inputs, outputs, artifacts, caches, and side effects;
- action and reusable-workflow refs.

Similarity means “worth comparing,” not semantic equivalence. If using a YAML
parser, ensure it preserves Actions' `on` key and scalar/list forms; do not
normalize away meaningful differences or write a custom parser for the review.

## Classification

| State | Required evidence | Defensible response |
|---|---|---|
| `healthy` | Complete enough scoped inventory; distinct workflows; clear ownership; tolerable cost; no unsafe contract drift | Leave it alone. |
| `monolith` | One workflow crosses real ownership or dependency boundaries; long accidental sequencing or rebuilds dominate | Split one proven seam. |
| `sprawl` | Repeated job contracts create coordinated patch, audit, runner, or credential work across consumers | Extract one high-consequence shared contract. |
| `monorepo-blast-radius` | Unaffected services run broadly, or required-check design prevents selective execution | Add detection plus a stable required check. |
| `mixed` | Two shapes have independent, material consequences | Name both, but choose one first decision. |
| `inconclusive` | Bounds, rate limits, inaccessible workflows/callees, or unknown required checks block a safe conclusion | Request the smallest additional bounded evidence. |

File length, duplication, or scanner counts alone do not decide the state.

## Decision evidence record

For the one recommended decision, record:

1. workflows, jobs, and reusable edges supporting it;
2. verified shared behavior versus text-only similarity;
3. known callers and caller-coverage limitations;
4. transitive input, secret, output, permission, environment, concurrency, runner, and ref contracts;
5. required checks, `merge_group`, and ruleset impact;
6. inaccessible consumers or callees;
7. canary cohort, rollback signal, and next expansion gate.
