# Actions behavioral evaluations

This directory is an independent, public, synthetic behavioral corpus for the
Actions plugin. It does not reuse `test-corpus/`, contact GitHub repositories,
or execute workflows.

## Corpus

[`corpus/cases.json`](corpus/cases.json) contains isolated fixture files,
fixture-backed `gh` responses, evidence IDs, and private-to-the-scorer
case-specific `must`/`mustNot` rules. Model prompts use generic natural-language
response fields. Required and forbidden claims, labels, abstention tokens,
patterns, and decoys remain scorer-only and are never copied into a fixture,
configuration overlay, or prompt. The corpus covers:

- checked-out YAML that differs from execution evidence;
- a failure confined to an earlier run attempt;
- deployment approval wait versus runner queue time;
- missing required context and skipped jobs;
- a safe metadata-only privileged workflow;
- scanner hard failure;
- runs with more than 30 jobs and prior attempts;
- free or unknown-rate compute without invented savings;
- string `environment` and `concurrency` forms;
- an unreadable reusable-workflow callee;
- justified extraction that preserves contracts; and
- a healthy small estate that should remain unchanged.

## Deterministic validation

No model authentication is needed:

```bash
python3 -m unittest discover -s plugins/actions/evals/tests -v
python3 plugins/actions/evals/harness/run_eval.py --dry-run
```

## Paired exact-model runs

Live runs require an existing ephemeral `COPILOT_GITHUB_TOKEN`, `GH_TOKEN`, or
`GITHUB_TOKEN`. The harness never invokes login, reads credential files, emits
the token, or places it in command arguments. It refuses artifact paths inside
the repository.

```bash
python3 plugins/actions/evals/harness/run_eval.py \
  --artifacts-dir "$HOME/.copilot/session-state/<session>/files/actions-evals-full" \
  --comparison all
```

The exact model is fixed to `gpt-5.6-sol-fast`; there is no model override or
fallback. Each enabled/disabled pair gets:

- a fresh, separately isolated `HOME` and `COPILOT_HOME`;
- a workspace materialized from the same case fixture;
- the same explicit variadic `bash view rg glob skill` tool whitelist and
  permission flags;
- the same strict fake `gh`;
- custom instructions and built-in MCPs disabled;
- `ask_user`, Bash environment loading, temporary-directory access, and remote
  export disabled; and
- JSONL output plus separate usage JSON.

`primary` compares a case-targeted skill overlay against an empty overlay with
identical fixtures and tool access. `full-package` is separately labelled
and compares a package snapshot against no package. Use `--comparison all` to
run all 12 cases in both comparisons. Comparison and enabled/disabled labels
are recorded in artifacts but never included in the model prompt, keeping
treatment assignment blind.

The scenarios use native `gh` command fixtures and captured scanner output.
Neither arm receives a runtime wrapper or a custom tool-output schema.

Every prompt asks the agent to invoke the case's relevant Actions procedures
through the supported `skill` tool when available. The harness records
discovered skill names, successful skill-tool consumption, result hashes, and
the frozen `SKILL.md` and directory hashes. Discovery and activation rates are
reported separately. A pair contributes to conditional procedure-effectiveness
scoring only when every intended enabled procedure was discovered and consumed,
the disabled side remained uncontaminated, and fixture/model/tool parity passed.
Discoverable-but-unconsumed procedures are not treated as an enabled treatment.

A command restricted with `--case` is only a harness pilot. It is not a
completed paired-corpus evaluation. Only an all-case run with valid treatment
activation and pair parity qualifies. This repository intentionally contains
no raw live transcripts or usage data.

The prior 48-run artifact at `actions-evals-full-20260912` is invalid for
diagnostic or procedure-uplift conclusions: its prompts exposed rubric-derived
vocabulary and procedure consumption was not verified. It may be retained only
as harness-debugging history.

The corrected `actions-evals-corrected-20260912` comparison predates removal
of the runtime wrappers. Its scores do not establish effectiveness of the
current native-tool procedures; a fresh comparison is needed for that claim.

The fake `gh` accepts only exact argument arrays declared by the case. Unknown
calls, write methods, workflow dispatches, reruns, cancellations, deletions,
and clones fail locally. It contains no network client or fallback to a real
`gh` binary.

Raw transcripts, stderr, logs, usage, copied workspaces, and result JSON remain
under the external artifact directory. Nothing writes behavioral output into
public source. A result is not interpreted or scored unless the CLI exits
successfully, a response object is extracted, the exact model is confirmed from
the structured usage `modelMetrics` as the only positively used model, and
usage-checkpoint metadata advertises exactly the requested tool whitelist. Text
mentions of the model are ignored. Missing, mixed, fallback, or zero-usage model
records fail confirmation. Pair parity also requires identical advertised
tools. Usage is reported as secondary data.

## Scoring

Primary scoring gives equal weight to:

1. diagnosis;
2. completeness;
3. abstention;
4. behavior preservation;
5. unauthorized edits; and
6. unsupported claims.

Filesystem hashes detect edits. Natural-language findings are graded offline
against scorer-only patterns; evidence IDs outside each fixture fail
unsupported-claim scoring. Proposed changes are expected only for the extraction
case; they remain proposals and must not alter fixtures.
