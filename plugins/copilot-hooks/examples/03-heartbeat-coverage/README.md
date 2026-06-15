# Example: heartbeat coverage gate

The flagship example. A complete, real feature built from five event hooks that forces
a scheduled `/heartbeat` session to **check its inbound sources** (Slack, Teams, Email,
GitHub) before it's allowed to stop.

This is the best demonstration of the **seed → mark → enforce** state-machine pattern
that underpins any "make the agent actually finish X before stopping" hook.

## How it works

```
seed     events/session-start.sh  (on /heartbeat)   ─┐
         events/user-prompt.sh    (on /heartbeat)    ├─► cov_seed → writes state file
         events/pre-tool.sh       (skill==heartbeat) ─┘   (required:[teams,slack,mail,github], covered:[])

mark     events/post-tool.sh  ──► cov_classify_read <tool> <args>  ──► cov_mark
         every time a READ/SEARCH/LIST tool succeeds, credit its source

enforce  events/agent-stop.sh ──► cov_missing
         if any required source is still unchecked: {"decision":"block","reason":...}
         re-prompts the agent. Capped by max_block_iterations (escape valve).
```

All the domain logic lives in [`coverage.sh`](coverage.sh). The event hooks are thin:
each sources `lib.sh` + `coverage.sh` and calls one function.

## State

`~/.copilot/heartbeat-state/coverage-<session-id>.json`:

```json
{
  "required": ["teams", "slack", "mail", "github"],
  "covered": ["slack", "github"],
  "block_iterations": 1,
  "max_block_iterations": 3,
  "status": "open",
  "started": "2026-06-15T16:20:00Z"
}
```

Plus an append-only `~/.copilot/heartbeat-state/coverage.log` for tracing.

## Why "read" only

A Slack *send* or a `gh issue create` is not "checking notifications". Only
read/search/list calls count toward coverage, so the gate measures **intent** (did the
agent look?) not side effects. `cov_classify_read` encodes exactly which tool-name
patterns count — and excludes the write variants.

## Customizing for your own sources

Two things, both in `coverage.sh`:

1. `COV_REQUIRED="teams slack mail github"` — the set of sources to require.
2. `cov_classify_read <tool> <args>` — map a successful tool call to one of those
   sources, **only** when it's a read. This is the entire domain-specific surface;
   everything else is generic state machinery.

## Install

Copy into a repo's `.github/hooks/` so the layout is:

```
.github/hooks/
├── lib.sh                 # from the plugin root
├── coverage.sh            # from this example
├── hooks.json             # rename from hooks.example.json here
└── events/
    ├── session-start.sh
    ├── user-prompt.sh
    ├── pre-tool.sh
    ├── post-tool.sh
    └── agent-stop.sh      # from this example's events/
```

Note `lib.sh` comes from the **plugin root**; the rest come from this example folder.
The event scripts source `../lib.sh` and `../coverage.sh`, so all three must sit
together at `.github/hooks/`.

## Safety notes baked in

- `pre-tool.sh` is the fail-closed skeleton (trap + `exit 0` + captured stdout).
- Every `coverage.sh` function is best-effort: a missing engine or a write race
  degrades to "did not mark", which can only cause one extra harmless block.
- `agent-stop.sh` has an **escape valve**: after `max_block_iterations` it logs and
  allows the stop, so a genuinely unreachable source can't loop forever. (Wire your own
  alert there — e.g. `gh issue create` — if you want a paper trail.)
