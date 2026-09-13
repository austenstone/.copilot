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

## Enabled-only live Actions matrix

[`Actions Copilot eval matrix`](../../../.github/workflows/actions-copilot-smoke.yml)
runs all 12 existing corpus cases, one [`smoke.py`](smoke.py) invocation per
`ubuntu-slim` matrix job. Model work is remote and these jobs need little local
CPU. There is no custom parallelism cap; `fail-fast: false` lets every case
produce evidence. Short pilots do not guarantee every case finishes under a
minute. Each CLI session has a 120-second timeout inside a six-minute job.

Every case uses exact `gpt-5.6-luna` at low effort, with no Auto selection or
fallback, consistent with the [model comparison](https://docs.github.com/en/copilot/reference/ai-models/model-comparison).
The manual paired harness below keeps its existing Sol Fast default.
Each case must successfully consume its target procedures through native
**skill-tool calls**, not merely discover their directories. Runtime cases add
`actions-debug` alongside their corpus-declared toolkit target; together the
matrix exercises all five skills without changing the manual harness's targets.
One CLI session may make several model requests to load skills and read evidence.

Only public fixture files and the real plugin manifest/skills enter the agent
workspace. The prompt contains the task, available files, exact native commands,
a generic response shape, and neutral evidence IDs (`E1`, `E2`, ...). Case
IDs/titles, scorer labels/rules, source-to-rubric mappings, and the fake-gh
response manifest stay outside that workspace and prompt. `evidenceSources` in
the corpus maps neutral citations back to the existing scorer, including
deduplication when two labels refer to the same source.

The agent receives only `view`, `skill`, and a shell preapproval for `gh`.
The existing strict [fake gh](harness/fake_gh.py) is first on its PATH and
serves only exact fixture commands, with no network fallback. Its optional
evaluator-owned trace records matched and rejected argument arrays, not response
fixtures. Successful file-read events and matched fixture commands independently
prove evidence access, including expected nonzero responses such as the callee
404. Unrelated instructions, MCPs, general shell commands, edits, URL access,
remote session export, and parent-directory access are unavailable. Every case
gets a fresh home and workspace; authentication is stripped from tool subprocesses.

### Assertions and outcomes

A **PASS** requires successful CLI completion, exclusive positive native Luna
usage, all target skill activations, an unchanged workspace/plugin, valid final
response structure, actual reads of all catalog sources, only observed
citations of every required catalog source, and no unsupported fixture commands.
The [case-specific invariants](harness/invariants.py), not an average score or
all-perfect legacy dimensions, decide behavioral pass/fail:

| Case | Required facts or behavior |
| --- | --- |
| Executed versus current YAML | Distinguish revisions, identify the test failure, avoid blaming current YAML. |
| Earlier attempt failure | Separate the failed first attempt from the successful latest attempt. |
| Approval wait | Identify reviewer/environment approval, not a capacity shortage. |
| Skipped publish | Identify the missing input and skipped job without claiming publication. |
| Metadata-only privileged trigger | Recognize metadata work and the untrusted-execution boundary. |
| Scanner failure | Recognize incomplete analysis and withhold clean/security assurance. |
| Large run | Account for 42 jobs, the attempt history, and both observed pages. |
| Free/unknown-rate compute | Preserve sample time units, zero hosted billing, and unknown rates; invent no money. |
| Scalar configuration | Accept scalar syntax and never guarantee preservation/order of pending runs. |
| Inaccessible callee | Respect the retrieval boundary and withhold contract assurance. |
| Extraction | Propose reuse while explicitly preserving all required contracts. |
| Healthy estate | Recognize healthy evidence without proposing unsupported changes. |

An `investigate` recommendation with no proposed edits is not itself a workflow
change. Unsafe recommendations still fail. Extraction checks use the existing
structured `proposedChanges[].preserves` lists: mentioning secrets elsewhere
does not demonstrate preserving the secret contract. No new answer envelope or
model-based judge is used. Always answering "No" cannot pass the suite.

**FAIL** means a skill, response, evidence-access, safety, or scoring assertion
failed after a valid Luna invocation. **SETUP_BLOCKED** means CLI/runtime,
authentication/service, native-output, or exact-model verification prevented a
trustworthy evaluation. Both fail the job. Missing setup artifacts or a job
timeout also remain a failed job, never an eval pass.

The original [paired scorer](harness/scoring.py) remains unchanged. Its
`legacyScore` is diagnostic only in matrix results. The revised checks are
bounded English fact/invariant checks, not exhaustive semantic adjudication:
unrecognized paraphrases or claims outside their coverage still need inspection.
Independent gold paraphrases and contradictory near misses cover clean-scan
assurance, pending-run ordering, time units, invented costs, required secret
contracts, and unsafe changes. Do not expose expected values, skip failed gates,
or reroll behavioral failures until green.

### Fixture revisions and offline regrading

Two fixtures are now revision **2**. The billing workflow uses checked-out,
Node-configured `npm` test/integration steps instead of dummy waits; its sample
durations remain explicitly in `durations.json`, not executable command
arguments. The healthy-estate workflows now include checkout, Node setup,
dependency installation, a package/lockfile/source, and scoped GitHub Packages
authentication. That repairs a genuinely incomplete original no-change control.
These workflow examples are still only read, never executed by the evaluation.
There are no artificial delays, retry loops, or spin waits in the runner/workflow.

Results record the exact grader/fixture source commit, grader hash, fixture hash,
and fixture revision. Old responses can be passed to `assertions_for` locally
using the original case definition and saved access/activation evidence. Label
that **offline regrading**, write it to a separate artifact, and preserve all
original verdicts and files. A replay does not acquire new model evidence or
retroactively make an old answer a response to a revised fixture. The original
0/12 run is unchanged. This matrix is enabled-only, not A/B evidence or a
general quality/performance benchmark.

The runner probes `command -v copilot`, records `copilot --version` and live
`--help`, and uses the preinstalled binary when available. Only a missing
executable triggers the documented `npm install --global @github/copilot`
fallback. The runner checks its flags against that runner's help before invoking
the model. It uses the short-lived built-in `GITHUB_TOKEN` with
`copilot-requests: write`, as documented in
[Copilot CLI Actions authentication](https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli-in-actions).
No PAT, login, or repository secret is created. Authentication or model-access
failure fails the job; it is never a skipped green eval.
The [actionlint configuration](../../../.github/actionlint.yaml) suppresses only
its outdated unknown-scope diagnostic for this workflow's documented
`copilot-requests` permission.

Each job writes a concise summary and a unique three-day artifact named
`actions-copilot-smoke-<case-id>`. These retain version/help, native events,
stderr, usage, command trace, and `result.json` with individual assertions,
diagnostic legacy scores, provenance, activation evidence, response, and duration. The artifact
allowlist excludes the home, logs, private fixture manifest, and authentication
state. Timeout handling retains partial stdout/stderr. Preserve failed evidence.

Execution is restricted to manual runs on `main` or
`austenstone-actions-copilot-smoke-eval`, plus scoped pushes to that bootstrap
branch. There are no PR/fork triggers and default unit CI remains independent of
model credentials. Until the workflow is registered, a scoped branch push starts
the first run without modifying `main`. Dispatch supports the full matrix or
one existing case for an explicitly authorized follow-up:

```bash
gh workflow run actions-copilot-smoke.yml --repo austenstone/.copilot \
  --ref austenstone-actions-copilot-smoke-eval -f case=all

gh workflow run actions-copilot-smoke.yml --repo austenstone/.copilot \
  --ref austenstone-actions-copilot-smoke-eval -f case=scanner-hard-failure
```

Local tests cover matrix/dispatch membership, unique artifact naming, case
validation, oracle isolation, evidence consumption, and positive/negative
assertion controls, and the absence of delay commands in current fixtures.
These are deterministic checks, **not live evals**. Use the
paired harness below only when that larger experiment is explicitly requested.

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
