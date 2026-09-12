# Actions helper contract

The three executable helpers in the toolkit's `scripts/` directory share this
versioned interface.

## Invocation

```text
HELPER [selectors] [--output PATH] [--pretty]
```

- GitHub.com only.
- Structured JSON is written to stdout by default. `--output` writes the same
  document to a caller-selected file, creating parent directories only below
  the caller's current working directory.
- Diagnostics go to stderr. Credentials, authorization headers, and token
  values are never emitted.
- Helpers never install dependencies, execute retrieved workflow files, edit
  workflows, or broaden an explicit scope.
- Commands and API pagination are bounded. A bound reached is reported as
  partial coverage, never as a clean result.

## Selectors

Helpers accept only selectors relevant to their job:

- `--repository OWNER/REPO` selects an exact GitHub.com repository.
- `--path PATH` selects a local repository or workflow path.
- `--ref REF` selects a remote ref. It is not inferred to be the executed
  workflow definition.
- `--run-id ID` and `--attempt N` select run evidence.
- Inventory commands require an explicit repository, organization, or input
  file scope and a caller-provided maximum.

Mutually exclusive or incomplete selector combinations fail with a structured
document and non-zero exit. Local review never silently expands to unrelated
remote default-branch content.

## JSON envelope

Every helper returns one JSON object:

```json
{
  "schema_version": "actions-helper/v1",
  "tool": "scan-workflows",
  "scope": {},
  "provenance": {},
  "coverage": {
    "status": "complete",
    "requested": 0,
    "examined": 0,
    "limitations": []
  },
  "result": {},
  "diagnostics": []
}
```

- `scope` records the exact repository, path, ref, run, attempt, and bounds
  requested by the caller.
- `provenance` records source identifiers, API endpoints, tool versions, and
  configuration that materially affect interpretation.
- `coverage.status` is `complete`, `partial`, or `unavailable`.
- `result` contains findings or collected evidence. Findings are successful
  results, not execution failures.
- `diagnostics` entries contain `level`, `code`, and `message`, with optional
  safe metadata. Expected codes distinguish at least invalid input, no inputs,
  missing executable, timeout, tool crash, online failure, inaccessible input,
  rate limiting, missing logs, and degraded analysis.

## Exit behavior

- `0`: the helper completed its requested collection or analysis, including
  when findings exist.
- `2`: invalid invocation or unsafe output destination.
- `3`: required input was unavailable or inaccessible.
- `4`: a required executable or authenticated GitHub access was unavailable.
- `5`: the helper crashed or its underlying tool produced invalid output.

Partial or degraded results may exit `0` only when the JSON explicitly records
the limitation and still contains usable evidence. Failed, unavailable, or
partial input is never represented as clean.
