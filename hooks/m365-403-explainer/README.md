# m365-403-explainer

Translates the useless "403 Forbidden" returned by m365 MCP tools (especially Teams
meeting transcript / recording calls) into an actionable playbook for the agent —
in **both VS Code Copilot Chat and the Copilot CLI**.

## Why

m365 / Microsoft Graph throws a bare `403 Forbidden` for a long list of things that
are not actually permission failures from the caller's perspective:

- The Teams meeting transcript caller isn't the organizer.
- Transcription was never enabled for the meeting.
- The meeting wasn't recorded.
- The resource lives in another mailbox the caller doesn't have delegate access to.
- The caller isn't (or wasn't) a member of the Teams chat/channel.

Without context, the agent reads `403 Forbidden` and tends to retry, escalate, or
tell the user "you don't have access" — none of which is useful. This hook injects
the real likely-causes playbook so the agent asks for an alternative source or skips.

## Files

- `playbook.sh` — **single source of truth** for the explanation text. Sourced by
  every entry point below. Defines `m365_403_playbook`, `m365_403_is_m365_tool`,
  `m365_403_is_transcript_tool`, `m365_403_extract_oid`.
- `explain.sh` — the **VS Code** hook (PostToolUse). Emits the VS Code schema
  (`hookSpecificOutput.additionalContext`).
- `events/pre-tool.sh` — **CLI** preToolUse hook.
- `events/post-tool-failure.sh` — **CLI** postToolUseFailure hook.
- `self-oid` — your Entra object id, used to detect "not the organizer". Override
  with the `M365_SELF_OID` env var.

## Wiring

### VS Code
`~/.copilot/hooks/m365-403-explainer.json` registers `explain.sh` for `PostToolUse`
(the location listed in `chat.hookFilesLocations`).

### Copilot CLI
Wired **globally** via the top-level `hooks` block in `~/.copilot/settings.json`:

```json
"hooks": {
  "preToolUse":         [ { "type": "command", "command": "<abs>/events/pre-tool.sh",         "timeoutSec": 10 } ],
  "postToolUseFailure": [ { "type": "command", "command": "<abs>/events/post-tool-failure.sh", "timeoutSec": 10 } ]
}
```

Hooks load at **session start** — restart the CLI for changes to take effect.

## Why the CLI needs different wiring than VS Code

The two runtimes do **not** share a hook contract. Verified against the installed
`@github/copilot` bundle:

| CLI event             | reads stdout?               | output schema (top-level, **not** `hookSpecificOutput`) |
| --------------------- | --------------------------- | ------------------------------------------------------- |
| `preToolUse`          | yes — can **deny** the call | `{ "permissionDecision": "deny", "permissionDecisionReason": "…" }` |
| `postToolUseFailure`  | yes — injects context       | `{ "additionalContext": "…" }` |
| `postToolUse`         | **ignored** (`a => {}`)     | — |
| `userPromptSubmitted` | **ignored** (`a => {}`)     | — |

Key facts that shaped this design:

1. The CLI reads **top-level** keys. It has **zero** references to
   `hookSpecificOutput` / `hookEventName` — that's the VS Code schema. So the CLI
   scripts emit raw top-level JSON.
2. An MCP tool that returns `isError: true` (how m365 surfaces a 403) becomes
   `resultType: "failure"`, which fires **`postToolUseFailure`** — the primary
   inject channel. `postToolUse` never sees it, and its stdout is ignored anyway.
3. `preToolUse` is **fail-closed** (nonzero exit / crash / timeout DENIES the
   tool). The script never uses `set -e`, always `exit 0`, and only an explicit
   `deny` JSON blocks.
4. `${COPILOT_PLUGIN_ROOT}` is **not** set by this CLI version — commands use
   absolute paths instead.

## What the CLI hooks do

- **pre-tool.sh** — for transcript/recording/recap/insight/attendance tools, parses
  the organizer `Oid` out of `joinWebUrl` and compares it to `self-oid`. If it's
  someone else's meeting (and `organizerUserId` wasn't explicitly passed), it
  **denies** the call up front with the playbook — saving the doomed round-trip.
- **post-tool-failure.sh** — catches any m365 403/Forbidden/Unauthorized that slips
  through and injects the playbook via `additionalContext`. Also appends a line to
  `~/.copilot/m365-403-state/failures.log` for observability.

## Testing (offline payload replay)

```bash
cd events

# preToolUse — someone else's meeting → expect a deny JSON
printf '{"toolName":"m365-calendar-GetOnlineMeetingTranscripts","toolArgs":{"joinWebUrl":"https://teams.microsoft.com/...Oid%%22%%3a%%2247e2c6c1-909f-421a-8703-4d5d86bb42cd%%22..."}}' | ./pre-tool.sh

# postToolUseFailure — m365 403 → expect {"additionalContext":"…"}
printf '{"toolName":"m365-teams-GetChat","toolArgs":{},"error":"403 Forbidden"}' | ./post-tool-failure.sh
```

For non-m365 tools, non-403 errors, your own meetings, or malformed stdin, the
scripts exit 0 with no output (allow / no-op).
