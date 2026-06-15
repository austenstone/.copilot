# copilot-hooks

A clean, reusable reference for building **Copilot CLI hooks** — the little scripts
Copilot runs at key moments (a tool runs, a prompt arrives, the session starts or
stops). Distilled from a production hook system, with the **heartbeat coverage gate**
as the flagship worked example.

> [!IMPORTANT]
> **This plugin is parked DORMANT. Nothing here loads.**
> The wiring files are named `hooks.example.json` (not `hooks.json`), so even if this
> plugin were enabled, no hook would fire. This is reference material, not an active
> hook install. See [Activating](#activating) to turn it on deliberately.

## What's a hook?

Copilot fires a hook at six lifecycle moments and pipes a JSON payload to your script
on **stdin**. The payload has **no event-name field** — you infer the event from which
keys are present. `lib.sh` does that for you and hands back clean accessors.

A hook is literally:

```bash
#!/usr/bin/env bash
. "${BASH_SOURCE[0]%/*}/../lib.sh" 2>/dev/null || true
# ...read the payload via hook_* accessors, optionally print one JSON object...
exit 0
```

## The six events

| event | fires | trigger key | extras |
|---|---|---|---|
| `sessionStart` | session boots | `initialPrompt` | `hook_source` (new\|resume) |
| `userPromptSubmitted` | user submits a prompt | `prompt` | `hook_prompt` |
| `preToolUse` | **before** every tool | `toolName` | `hook_tool_args` — **fail-closed** |
| `postToolUse` | after a tool **succeeds** | `toolName`+`toolResult` | `hook_tool_result`, `hook_result_type` |
| `postToolUseFailure` | after a tool **errors** | `toolName`+`error` | `hook_error` |
| `agentStop` | agent about to stop | `stopReason` | `hook_stop_reason` |

Full payload + output contract details in [`docs/EVENTS.md`](docs/EVENTS.md).
Safety, performance, and portability rules in [`docs/WRITING-HOOKS.md`](docs/WRITING-HOOKS.md).

## Layout

```
copilot-hooks/
├── plugin.json              # dormant manifest (wires nothing)
├── lib.sh                   # the reusable library — source it, never run it
├── hooks.example.json       # canonical wiring (rename to hooks.json to use)
├── events/                  # six generic stubs — clean starting points
│   ├── session-start.sh
│   ├── user-prompt.sh
│   ├── pre-tool.sh          # fail-closed safe stub
│   ├── post-tool.sh
│   ├── post-tool-failure.sh
│   └── agent-stop.sh
├── tools/
│   ├── dump.sh              # universal payload dumper (your #1 debug tool)
│   └── dump.example.json    # wiring to send every event to dump.sh
├── docs/
│   ├── EVENTS.md            # the six events, payloads, output contract
│   └── WRITING-HOOKS.md     # safety, performance, portability, recipes
└── examples/
    ├── 01-context-injection/   # sessionStart → inject git/branch context
    ├── 02-guardrail-deny/      # preToolUse → block dangerous shell commands
    └── 03-heartbeat-coverage/  # THE example: a full "not done yet" gate
```

## The flagship example: heartbeat coverage gate

[`examples/03-heartbeat-coverage/`](examples/03-heartbeat-coverage/) is a complete,
real feature spread across five event hooks. It forces a scheduled `/heartbeat`
session to actually **check its inbound sources** (Slack, Teams, Email, GitHub)
before it's allowed to stop — `agentStop` blocks termination and re-prompts the
agent until every required source has a successful read/search/list call on record.

It's the best demonstration of the whole pattern: **seed** state up front, **mark**
progress on each tool call, **enforce** at stop. Read its
[README](examples/03-heartbeat-coverage/README.md).

## Activating

This is dormant on purpose. To actually run these hooks, pick one:

**A. In a repo (proven path).** Copy `lib.sh`, `events/`, and a `hooks.json` into
your repo's `.github/hooks/`. Rename `hooks.example.json` → `hooks.json`. Copilot
auto-discovers `.github/hooks/hooks.json` for trusted folders.

**B. As an enabled plugin.** Rename `hooks.example.json` → `hooks.json`, switch its
command paths to `${COPILOT_PLUGIN_ROOT}/events/*.sh`, and add `copilot-hooks` to
`enabledPlugins` in `~/.copilot/settings.json`. The CLI auto-loads a plugin-root
`hooks.json` when the plugin is enabled.

Either way: **start with `dump.sh`** wired to every event so you can see exactly what
Copilot sends before you write real logic.

## Requirements

- `bash` (targets macOS system bash 3.2 — no associative arrays / `mapfile` / `${var^^}`)
- `jq` or [`jaq`](https://github.com/01mf02/jaq) (faster). Override with `HOOK_JQ=/path`.
  With neither present, every helper degrades to a safe no-op.

## License

MIT
