# Writing hooks

Everything here is learned from running a hook system in anger. The rules are not
style preferences — breaking the safety ones can brick your sessions.

## Safety: `preToolUse` is fail-closed

`preToolUse` fires before **every** tool call. If its hook **exits nonzero, errors,
or times out**, the tool is **DENIED**. Get it wrong and *every* tool call is blocked
until you fix the file and restart Copilot. The cardinal rules:

1. **Never `set -e`** in a hook.
2. **Always end with `exit 0`.**
3. Put logic in a guarded subroutine, capture its stdout, and only print an explicit
   `hook_deny`/`hook_allow` JSON. Empty stdout = the default allow.
4. **Editing a live hook?** Write a temp file, validate it (`bash -n`, run it against a
   sample payload), then `mv` it into place. **Never edit a live `preToolUse` hook or
   `lib.sh` in place** — the hook can fire against a half-written file mid-save.
5. Source the lib defensively: `. ".../lib.sh" 2>/dev/null || true`. A broken lib then
   can't block tools — the hook still reaches `exit 0`.

The safe `preToolUse` skeleton (see `events/pre-tool.sh`):

```bash
#!/usr/bin/env bash
set +e
trap 'exit 0' EXIT
_main() {
  . "${BASH_SOURCE[0]%/*}/../lib.sh" 2>/dev/null || return 0
  # ...decide...
  # hook_deny "reason"   # to block
  return 0
}
_OUT="$(_main 2>/dev/null)"
[ -n "$_OUT" ] && printf '%s' "$_OUT"
exit 0
```

The other five events are not fail-closed — a bug there is harmless (at worst a missed
side effect), but still always `exit 0`.

## Performance

`preToolUse` runs before every tool, so **its latency is the binding constraint** on
the whole session. `lib.sh` is built for this:

- **stdin is read once** (one cheap `cat`).
- **Parsing is lazy and memoized.** A hook that reads no field forks no engine. Reading
  any core field or `toolArgs` costs **one** engine pass. The possibly-huge `toolResult`
  is a **second** pass only if you call `hook_tool_result`/`hook_result_type`/`hook_error`.
- **Engine:** `jaq` if installed (~3x faster startup than `jq`), else `jq`; override with
  `HOOK_JQ=/path`. With neither, helpers degrade to safe no-ops.

So a no-op stub and an early-outing guardrail both cost ~nothing. Only pay for what you
read. Benchmark real hooks with [hyperfine](https://github.com/sharkdp/hyperfine).

## Portability

Target is **macOS system bash 3.2**. Avoid:
- associative arrays (`declare -A`)
- `mapfile` / `readarray`
- `${var^^}` / `${var,,}` case conversion
- GNU-only `date` flags (`%3N` millis — fall back like `tools/dump.sh` does)

## Debugging

Wire `tools/dump.sh` to every event (`tools/dump.example.json`). For each firing it
appends the raw stdin payload, argv, and full environment to:

- `~/.copilot/hook-dumps/dump.log` — human-readable, all events
- `~/.copilot/hook-dumps/dump.jsonl` — one JSON object per firing, replayable
- `~/.copilot/hook-dumps/<event>.json` — latest payload per event

Replay a captured payload straight into a hook to test it offline:

```bash
jq -r 'select(.event=="preToolUse") | .stdin_raw' ~/.copilot/hook-dumps/dump.jsonl \
  | tail -1 | ./events/pre-tool.sh; echo "exit=$?"
```

## The state-machine pattern (seed → mark → enforce)

The heartbeat coverage gate is the canonical shape for any "make the agent actually do
X before stopping" feature. It's worth internalizing:

1. **Seed** — at the start (sessionStart / userPromptSubmitted, with a preToolUse
   backstop), write a per-session state file describing what must happen.
2. **Mark** — on each `postToolUse`, classify the tool call and record progress into
   that state file (under a portable `mkdir` lock for concurrency safety).
3. **Enforce** — on `agentStop`, read the state. If incomplete, emit
   `{"decision":"block","reason":...}` to force another turn. Cap the number of blocks
   with an **escape valve** so a genuinely unreachable dependency can't loop forever.

State lives in `~/.copilot/<feature>-state/<session-id>.json`. Keep every state write
best-effort (a failed write should cause at most one extra harmless block, never a
brick). See `examples/03-heartbeat-coverage/coverage.sh` for the full implementation.

## Idempotency & sessions

- The same `session-id` can be reused across runs. **Seed = reset** so stale state from
  a prior run can't leak in. Use a separate "seed only if absent" path for mid-run
  backstops so you don't reset an in-progress run.
- Hooks can fire concurrently. Any read-modify-write of a shared file needs a lock
  (`mkdir` is the portable choice — atomic on every filesystem).
