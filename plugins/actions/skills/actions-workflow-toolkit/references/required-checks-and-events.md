# Required checks and event semantics

Use this when a check is missing/pending, path selection skips work, a matrix
can be empty, failures or cancellations disappear, or merge queue behaves
differently from pull requests.

## Establish the contract

1. Read the repository/ruleset required-check configuration when authorized.
2. Record the exact required check name and expected event paths.
3. Map that name to the workflow and stable reporting job.
4. Check for duplicate job/check names that make the source ambiguous.
5. Record whether merge queue is enabled.

If rules are unreadable, say the required-check contract is unverified.

## Event coverage

Evaluate each required path separately:

- `pull_request` validates the proposed PR state.
- `merge_group` validates the temporary merge-queue candidate.
- `push` validates the resulting branch update.

When merge queue is used, a required PR workflow normally needs the relevant
`merge_group` trigger and must avoid assumptions that only exist in the
`pull_request` payload. Fetch the live event documentation before mapping
fields.

Top-level branch/path filters can prevent the entire workflow from being
created. When that workflow supplies a required check, the check can remain
pending. Prefer an always-created workflow with internal change detection and
a stable reporting gate when selective execution must coexist with required
checks.

## Stable always-evaluated gate

Make one lightweight job the required check. It should:

1. Have a stable workflow/job name across PR and merge-queue events.
2. Depend on the detector and all required work.
3. Use `if: ${{ always() }}` so upstream failure, cancellation, or skip does
   not prevent the gate from running.
4. Fail when required upstream work failed or was cancelled.
5. Accept `skipped` only when the detector explicitly proved no work was
   required.
6. Succeed when all required work succeeded, including a legitimate no-work
   case.

Example shape:

```yaml
on:
  pull_request:
  merge_group:
    types: [checks_requested]

jobs:
  detect:
    runs-on: ubuntu-latest
    outputs:
      work_required: ${{ steps.changes.outputs.work_required }}
      matrix: ${{ steps.changes.outputs.matrix }}
    steps:
      - id: changes
        run: ./detect-changes

  test:
    needs: detect
    if: ${{ needs.detect.outputs.work_required == 'true' }}
    strategy:
      matrix: ${{ fromJSON(needs.detect.outputs.matrix) }}
    runs-on: ubuntu-latest
    steps:
      - run: ./test

  required:
    name: required
    if: ${{ always() }}
    needs: [detect, test]
    runs-on: ubuntu-latest
    env:
      DETECT_RESULT: ${{ needs.detect.result }}
      TEST_RESULT: ${{ needs.test.result }}
      WORK_REQUIRED: ${{ needs.detect.outputs.work_required }}
    steps:
      - shell: bash
        run: |
          [[ "$DETECT_RESULT" == success ]]
          case "$WORK_REQUIRED" in
            true) [[ "$TEST_RESULT" == success ]] ;;
            false) [[ "$TEST_RESULT" == skipped ]] ;;
            *) echo "invalid work_required output" >&2; exit 1 ;;
          esac
```

Adapt the gate to the real job graph. Do not copy it without validating the
matrix JSON and all required jobs.

## Empty matrices

Do not rely on accidental behavior from `fromJSON('[]')`. Make the detector
emit:

- An explicit `work_required` boolean string
- Valid matrix JSON for the work-required case
- A reason or selected-target count for evidence

Guard the matrix job with `work_required`. Let the stable gate decide whether
its `skipped` result was expected. If detection fails or produces invalid
output, the gate must fail.

## Failure and cancellation propagation

Jobs with `needs` are skipped after an upstream failure/cancellation unless
their condition permits evaluation. `always()` restores evaluation; the gate
must then inspect `needs.*.result`. Never use an unconditional successful
placeholder that masks `failure` or `cancelled`.

Validate the final workflow with the toolkit scanner and, for a real incident,
one PR path, one no-work path, one failure path, one cancellation path, and one
merge-queue path when applicable.
