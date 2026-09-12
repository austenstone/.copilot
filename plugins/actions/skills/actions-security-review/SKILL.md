---
name: actions-security-review
description: "Audits GitHub Actions workflows with the toolkit scanner, then ranks security findings by exploitable data flow and proposes behavior-aware fixes. Use when reviewing Actions security, privileged triggers, expression or environment-file injection, token permissions, action pinning, vulnerable actions, reusable-workflow secrets, OIDC boundaries, artifacts, or self-hosted runners."
---

# Actions Security Review

Use the executable scanner. Do not recreate its shell wrappers.

## Procedure

1. Select one explicit scope. A local scope stays local; do not add a remote
   default-branch pass unless the request separately authorizes that repository
   context. Resolve `../actions-workflow-toolkit/scripts/scan-workflows.py`
   relative to this `SKILL.md`, then use that absolute path as `SCANNER`.

   ```bash
   python3 "$SCANNER" --path . --output scan.json --pretty
   ```

   ```bash
   python3 "$SCANNER" \
     --repository OWNER/REPO --ref REF --output scan.json --pretty
   ```

2. Read the full helper envelope before interpreting findings:
   - `coverage.status` must be `complete`, `partial`, or `unavailable`.
   - Findings exit codes are successful evidence: actionlint `1`; zizmor
     `11`–`14`.
   - Treat `no_inputs`, timeout, invalid output, tool crash, missing executable,
     and online failure as distinct outcomes. Never translate one into clean.
   - Report every limitation, skipped network audit, tool version, and loaded
     configuration recorded in provenance.
   - Remote recovery never uses zizmor `--offline`. If remote collection finds
     no inputs, the scanner's exact-repository archive is a degraded local
     recovery, not an equivalent remote pass.

3. Triage actionlint before security ranking:
   - Schema, expression, dependency, matrix, event, and action diagnostics are
     correctness findings.
   - `runner-label` is configuration/version-dependent. Validate custom labels
     against the recorded config and runner inventory before calling it invalid.
   - Use the scanner's behavior classification for ShellCheck. Severity alone
     is insufficient: an `info` word-splitting diagnostic can affect behavior,
     while a style-only rewrite is hygiene.

4. Trace attacker-controlled data through triggers, checkout/ref selection,
   artifacts, caches, action inputs, `run:`, environment files, token scopes,
   secrets, environments, and runners. Rank by reachable consequence:
   1. Privileged execution or publish/deploy paths.
   2. Injection into shell, environment files, outputs, or action inputs.
   3. Vulnerable or untrusted third-party supply chain.
   4. Permission and secret blast-radius reductions.
   5. Grouped hardening and hygiene.

5. Apply false-positive controls from
   [`privileged-triggers.md`](references/privileged-triggers.md). A tightly
   scoped metadata-only `pull_request_target` or `workflow_run` job is not
   exploitable merely because the trigger is privileged. Group GitHub-owned
   `actions/*` tag pins as first-party hardening unless they participate in an
   exploit path; do not present them like unknown third-party code.

6. Propose the smallest behavior-aware change from
   [`fix-patterns.md`](references/fix-patterns.md):
   - Preserve intentional pushes, publishing, metadata writes, and reusable
     workflow contracts.
   - Never invent a SHA. Use a scanner-provided fix or resolve it explicitly.
   - Mark trigger redesign, permission changes, secret narrowing, action
     upgrades, and credential-persistence changes as behavior-affecting unless
     the evidence proves otherwise.
   - Default to read-only. Apply changes only when the current request says to,
     then rerun this scanner.

7. Report with [`report-template.md`](references/report-template.md). Layer 1
   uses consequence language; Layer 2 includes file:line, rule, evidence,
   minimal diff, citation, and behavior impact. Policy or cloud evidence that
   is unavailable is **not checked**, never clean or compliant. Use
   [`org-controls.md`](references/org-controls.md) for those boundaries. Cite
   each zizmor finding's `url` and use the toolkit
   [`docs-map.md`](../actions-workflow-toolkit/references/docs-map.md) for
   GitHub documentation.

Use scale mode from the report template above 25 workflows or 100 findings.
