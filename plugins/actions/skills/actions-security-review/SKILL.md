---
name: actions-security-review
description: "Reviews GitHub Actions workflows with actionlint and zizmor, then ranks findings by exploitable data flow and proposes behavior-aware fixes. Use when: reviewing Actions security, privileged triggers, expression or environment-file injection, token permissions, action pinning, vulnerable actions, reusable-workflow secrets, OIDC boundaries, artifacts, or self-hosted runners."
---

# Actions Security Review

Use `actionlint` and `zizmor` directly. The toolkit's
[native-tool procedures](../actions-workflow-toolkit/references/tools.md#static-validation)
cover commands and interpretation; no custom scanner interface is needed.

## Procedure

1. Select one explicit scope. A local scope stays local; do not add a remote
   default-branch pass unless the request separately authorizes that repository
   context. For remote input, select the exact ref and preserve relevant
   configuration. Run the tools as separate commands; a findings exit from
   one must not prevent the other from running.

2. Read native output, exit status, and stderr before interpreting findings:
   - Findings are successful evidence: actionlint exits `1`; zizmor defaults
     to `11`-`14`.
   - Treat no inputs, timeout, invalid output, tool crash, missing executable,
     and online failure as distinct outcomes. Never translate one into clean.
   - Record examined files/refs, skipped audits, tool versions, and relevant
     configuration. If tools are unavailable, label manual inspection static
     and unscanned rather than installing dependencies.
   - Remote zizmor collection cannot use `--offline`. If online audits are
     unavailable, `--no-online-audits` is a limited alternative, not equivalent
     coverage. Do not retry at the default branch or expand scope.

3. Triage actionlint before security ranking:
   - Schema, expression, dependency, matrix, event, and action diagnostics are
     correctness findings.
   - `runner-label` is configuration/version-dependent. Validate custom labels
     against the recorded config and runner inventory before calling it invalid.
   - Read each ShellCheck code in context. Severity alone is insufficient:
     an `info` word-splitting diagnostic can affect behavior, while a
     style-only rewrite is hygiene.

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
     then rerun the applicable native tools.

7. Report with [`report-template.md`](references/report-template.md). Layer 1
   uses consequence language; Layer 2 includes file:line, rule, evidence,
   minimal diff, citation, and behavior impact. Policy or cloud evidence that
   is unavailable is **not checked**, never clean or compliant. Use
   [`org-controls.md`](references/org-controls.md) for those boundaries. Cite
   each zizmor finding's `url` and use the toolkit
   [`docs-map.md`](../actions-workflow-toolkit/references/docs-map.md) for
   GitHub documentation.

Use scale mode from the report template above 25 workflows or 100 findings.
