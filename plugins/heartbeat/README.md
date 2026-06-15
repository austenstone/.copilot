# heartbeat

A real, working use case for Copilot CLI hooks: an **inbound-coverage gate**, built
from a **single, stateless `agentStop` hook**.

A scheduled `/heartbeat` session is supposed to sweep your inbound sources (Slack,
Teams, Email, GitHub) before it reports back. Agents, being eager, sometimes declare
victory after checking one or two. This plugin makes that impossible: when the agent
tries to stop, the hook reads the session transcript, checks whether every required
source got a successful read, and **blocks the stop** (re-prompting the agent) until
they have.

> **Inert until enabled.** Like every plugin in this repo, `hooks.json` only loads when
> the plugin is listed in `enabledPlugins` (see [Enabling](#enabling)). Until then it
> does nothing. Even once enabled, it only acts on real `/heartbeat` runs — ordinary dev
> sessions fall straight through.

## One hook, no state

Earlier versions used five hooks (`sessionStart`/`userPromptSubmitted`/`preToolUse` to
seed, `postToolUse` to mark, `agentStop` to enforce) plus a per-session JSON **state
file** to carry progress between them. That meant `preToolUse` and `postToolUse` fired
on **every tool call in every session** — exactly the kind of hot-path hook abuse worth
avoiding — and left state files littering `~/.copilot/heartbeat-state/`.

This version collapses all of that into **`agentStop` alone**. Nothing fires on the tool
hot path. Nothing is written to coordinate events. At stop time the hook **derives**
everything it needs from the session transcript
(`~/.copilot/session-state/<sid>/events.jsonl`):

| Question | How it's derived |
|---|---|
| Is this a `/heartbeat` run? | `skill.invoked` with `name=="heartbeat"`, or a `skill` tool call selecting heartbeat, or a `user.message` that is the literal `/heartbeat` command. |
| Which sources got checked? | Join `tool.execution_start` (toolName + args) to `tool.execution_complete` (`success==true`) by `toolCallId`, then run each successful call through `cov_classify_read`. |
| How many times have we blocked already? | Count a distinctive sentinel string in non-assistant transcript events (replaces the old `block_iterations` counter). |

**Trade-off:** this depends on Copilot's transcript schema, so it's **less portable**
than the state-file design. That's an accepted trade for a one-hook, zero-state system.
If the schema changes, the jq in `coverage.sh` is the one place to update.

## Flow

```
agent tries to stop
        │
        ▼
  agentStop hook reads ~/.copilot/session-state/<sid>/events.jsonl
        │
        ├─ not a /heartbeat run?            → allow stop (exit 0)
        ├─ all required sources read?       → allow stop (exit 0)
        ├─ already blocked COV_MAX_BLOCKS×? → escape valve: log + allow
        └─ otherwise → {"decision":"block","reason": "...still UNCHECKED: <missing>..."}
                       which re-prompts the agent for another turn
```

## Why "read" only

A Slack *send* or a `gh issue create` is not "checking notifications." Only
read/search/list calls earn credit, so the gate can't be satisfied by the agent merely
*doing* things — it has to *look*. `cov_classify_read` encodes which tool-name patterns
count and excludes the write variants (e.g. `m365-mail-SendMail` credits nothing).

## Customizing

Two knobs, both in [`coverage.sh`](coverage.sh):

1. `COV_REQUIRED="teams slack mail github"` — the sources to require.
2. `cov_classify_read <tool> <args>` — map a successful tool call to one of those
   sources, only when it's a read. This is the entire domain-specific surface.

Also tunable: `COV_MAX_BLOCKS` (default 3, the escape-valve cap).

## Enabling

The hook won't fire until the plugin is enabled. Add it to `~/.copilot/settings.json`:

```json
{ "enabledPlugins": { "heartbeat": true } }
```

Then restart Copilot. To turn it off, remove that entry (or set it to `false`).

> Heads up: once enabled, `agentStop` will block any `/heartbeat` session until coverage
> completes. That's the intended behavior, but it's why this ships disabled. Try it on a
> throwaway session first.

## Layout

```
heartbeat/
├── plugin.json          # manifest (not in enabledPlugins → inert)
├── hooks.json           # one hook: agentStop. Loads only when enabled.
├── lib.sh               # shared payload-accessor library
├── coverage.sh          # stateless derivation: is_heartbeat / covered / missing / block_count  ← customize here
├── events/
│   └── agent-stop.sh    # the entire gate
└── README.md
```

Diagnostics: the gate appends a line per allow/block/escape to
`~/.copilot/heartbeat-state/coverage.log` (purely informational — not coordination
state, safe to delete).

## See also

[`copilot-hooks`](../copilot-hooks/) — the reference library and docs this was built
from: the six events, the output contract, and the fail-closed safety rules.
