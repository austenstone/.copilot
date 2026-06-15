# Examples

Three worked examples, increasing in complexity. Read them in order.

| # | Example | Event(s) | Teaches |
|---|---|---|---|
| 01 | [context-injection](01-context-injection/) | `sessionStart` | Inject context the agent sees before it responds (`hook_emit_context`). The gentlest hook. |
| 02 | [guardrail-deny](02-guardrail-deny/) | `preToolUse` | Block a dangerous tool call (`hook_deny`) using the fail-closed safe skeleton. |
| 03 | [heartbeat-coverage](03-heartbeat-coverage/) | all five | The full **seed → mark → enforce** state machine: force the agent to finish a checklist before it can stop. |

Each script sources `../../lib.sh` (relative to the example folder). To actually run
one, copy it into a repo's `.github/hooks/` alongside `lib.sh` and wire it in
`hooks.json` — see the top-level [README](../README.md) and [docs/EVENTS.md](../docs/EVENTS.md).

## 01 — context injection

```bash
hook_emit_context "Reminder: it's Friday, prefer low-risk changes." "SessionStart"
```
One line. On every new session the agent gets that note as context. Swap the string for
anything dynamic — git branch, open PR count, today's calendar.

## 02 — guardrail deny

A `preToolUse` hook that inspects the pending tool call and blocks it if it matches a
dangerous pattern (e.g. `rm -rf /`, force-push to `main`). Demonstrates:
- the **fail-closed** skeleton (`set +e`, `trap 'exit 0' EXIT`, captured stdout)
- reading the command out of `hook_tool_args`
- emitting `hook_deny "reason"` only on a match, default-allow otherwise

## 03 — heartbeat coverage gate

The real thing. See its [own README](03-heartbeat-coverage/README.md).
