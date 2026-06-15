---
name: github-deep-review
description: Evidence-first review of a GitHub PR or issue. Finds the real root cause, traces regression provenance, judges whether the fix is the best one, and reports in a fixed template. Use when asked to review a PR, "is this the right fix", "what is this about", "is this bug real or stale", or to deeply analyze an issue before acting.
---

# GitHub Deep Review

Review with high confidence and evidence first. The goal is not a summary. Understand the bug class, find the real cause when possible, decide the best fix after reading enough code, and say "not proven" when the trail is weak. Read code before judging.

## Pull the refs

Use `gh` (or the GitHub MCP tools) for exact refs, not web browsing. Narrow `--json` fields, don't loop one `view` per result.

```bash
gh pr view <n> --json number,title,state,author,body,comments,reviews,files,commits,statusCheckRollup,mergeStateStatus,headRefName,url
gh pr diff <n> --patch
gh issue view <n> --json number,title,state,author,body,comments,labels,updatedAt,url
```

If the repo has local instructions, issue/PR templates, test guidance, or runbooks, read those before deciding.

## Review contract

Answer these explicitly, every time:

- **Ref/surface:** PR or issue number and what it touches.
- **Bug/behavior:** what's actually being fixed or changed.
- **Root cause:** where in code and why, or what evidence is missing.
- **Provenance** (regressions): who/what introduced it and when, traceable by history.
- **Best fix:** is the current/proposed fix the right one after reading adjacent code?
- **Refactor:** would a bigger change improve correctness/clarity/maintainability?
- **Proof:** tests, live repro, CI, docs, shipped behavior.
- **Risk:** what stays unverified.

## Read past the first file

Follow the real call path, don't stop at the touched line:

- entrypoint → validation/parsing → routing → owner module → shared helper → persistence/network/runtime boundary
- config/schema/docs → runtime usage → migration/fix path
- tests around the touched surface plus adjacent regression tests

When behavior depends on a dependency, read the upstream docs/types/contract before assuming. Prefer current source and executable proof over issue comments; treat stale comments and old CI as hints until rechecked.

## Provenance

For bug/regression reviews include a compact provenance answer when feasible:

```bash
git log -S '<symbol or string>' --oneline      # when it entered
git log -G '<regex>' --oneline                  # change-level search
git blame -L <start>,<end> <file>
```

Separate author, merger, and current PR author when they differ. Phrase as `introduced by`, `made visible by`, or `carried forward by`, with confidence `clear` / `likely` / `unknown`. For features/docs/untraceable bugs write `N/A`.

## Fix quality bar

Good fixes usually: live at the ownership boundary where the bug belongs; preserve backward-compatible behavior unless retiring it is the point; add a regression test at the smallest meaningful seam; avoid broad special cases and hidden migrations; update docs/changelog on user-visible change; fail clearly in runtime paths.

Call out symptom-level fixes. If a slightly larger refactor makes the invariant obvious and kills a bug class, recommend it. If a refactor widens risk without improving the bug, say so.

## Output template

```text
Ref: #123 / PR #456
Surface: <runtime/CLI/workflow/docs>
Bug: <1-2 sentences>
Cause: <code path + confidence>
Provenance: <introduced/made visible/carried forward by commit/PR/date, or N/A>
Best fix: <what should change and why>
Refactor: <yes/no, specific shape>
Proof: <tests/live/CI/source>
Risk: <remaining uncertainty>
```

For PR reviews, lead with findings. Every finding needs a file/line/symbol reference and a concrete failure mode. Skip vague "consider" comments. If nothing blocks: say no blocking correctness issues found, list the strongest proof checked, name the residual risk, and answer whether the design is the best available shape.

Do not approve, comment, close, merge, or push unless explicitly asked.
