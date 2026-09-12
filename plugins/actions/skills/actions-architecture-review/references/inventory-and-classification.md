# Inventory and classification

Load the toolkit and its [helper contract](../../actions-workflow-toolkit/references/helper-contract.md) first.
The inventory helper uses the repository's existing PyYAML ecosystem with an
Actions-safe loader. If PyYAML is unavailable, it returns structured
`missing_dependency` evidence; do not install dependencies during a review.

## Bounded inventory

Repository:

```bash
python3 ../actions-workflow-toolkit/scripts/inventory-workflows.py \
  --repository OWNER/REPO \
  --max-workflows 100 \
  --max-depth 3 \
  --max-callees 100 \
  --max-comparisons 5000 \
  --pretty
```

Use `--ref REF` only when the requested evidence is at that ref. It is provenance, not proof that runs executed that definition.

Organization:

```bash
python3 ../actions-workflow-toolkit/scripts/inventory-workflows.py \
  --organization ORG \
  --max-repositories 200 \
  --max-workflows 1000 \
  --max-depth 3 \
  --max-callees 500 \
  --max-comparisons 20000 \
  --pretty
```

Manifest:

```bash
python3 ../actions-workflow-toolkit/scripts/inventory-workflows.py \
  --input repositories.json \
  --max-repositories 50 \
  --max-workflows 500 \
  --pretty
```

The manifest is a JSON array, `{"repositories": [...]}`, or one `OWNER/REPO[@REF]` per line. Bounds are examples, not defaults to copy blindly. Pick the smallest defensible scope.

## Read coverage before findings

| Evidence | Interpretation |
|---|---|
| `coverage.status: complete` | The requested bounded collection completed. It is not proof about callers outside scope. |
| `partial` | Use collected evidence, but repeat every material limitation in the conclusion. |
| `unavailable` | Do not make an architecture claim from the inventory. |
| `rate_limited` | Collection stopped or degraded because GitHub throttled it. |
| `forbidden_or_rate_limited` | A `403` cannot safely distinguish policy, authorization, or unreported throttling. |
| `not_found_or_inaccessible` | A `404` cannot safely distinguish absence from hidden content. |
| caller coverage `scoped` or `limited` | Incoming edges are only calls found in examined workflow files. |

The helper follows reusable calls transitively within all supplied bounds. Each remote edge reports whether its own ref is a full commit SHA. For local `./.github/workflows/...` calls, it resolves one immutable repository SHA and uses it for caller and callee reads. If that resolution is unavailable, the local edge is explicitly unverified and unpinned. An inaccessible callee is evidence of incomplete contract review, not evidence that the callee does not exist.

## Review candidate families

Use exact canonical groups first. For similarity pairs, inspect the original jobs and compare:

- trigger, condition, matrix, dependencies, runner, services, container, and timeout;
- string or object `environment` and `concurrency`;
- permissions and secret flow;
- inputs, outputs, artifacts, caches, and side effects;
- action and reusable-workflow refs.

Similarity means “worth comparing.” Never say two jobs are equivalent because their score is high.

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
2. exact versus similarity-only evidence;
3. known callers and caller-coverage limitations;
4. transitive input, secret, output, permission, environment, concurrency, runner, and ref contracts;
5. required checks, `merge_group`, and ruleset impact;
6. inaccessible consumers or callees;
7. canary cohort, rollback signal, and next expansion gate.
