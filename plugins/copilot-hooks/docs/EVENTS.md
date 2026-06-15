# The six events

Copilot fires a hook by running its command and piping a JSON payload to **stdin**.
There is **no event-name field** in the payload — you infer the event from which
top-level keys are present. `lib.sh` does this for you; `hook_event` prints one of:
`sessionStart`, `userPromptSubmitted`, `preToolUse`, `postToolUse`,
`postToolUseFailure`, `agentStop`, or `unknown`.

> Discovered the hard way (over ~1370 firings via `tools/dump.sh`): Copilot does NOT
> send `hookEventName`. Always infer from keys. When in doubt, wire `dump.sh` to every
> event and read `~/.copilot/hook-dumps/<event>.json`.

## Payloads & accessors

Always present: `hook_event`, `hook_session_id`, `hook_cwd`.

| event | trigger key(s) | accessors that light up |
|---|---|---|
| `sessionStart` | `initialPrompt` | `hook_source` → `new`\|`resume`, `hook_prompt` |
| `userPromptSubmitted` | `prompt` | `hook_prompt` |
| `preToolUse` | `toolName` (no result) | `hook_tool_name`, `hook_tool_args` |
| `postToolUse` | `toolName` + `toolResult` | + `hook_tool_result`, `hook_result_type` |
| `postToolUseFailure` | `toolName` + `error` | + `hook_error` |
| `agentStop` | `stopReason` | `hook_stop_reason`, plus `transcriptPath` in raw payload |

Each accessor prints to stdout — capture with `$(...)`:

```bash
tool="$(hook_tool_name)"
args="$(hook_tool_args)"                       # compact JSON
cmd="$(hook_tool_args | "${_HOOK_JQ:-jq}" -r '.command // empty')"
```

## Output contract

**Exit 0 with no stdout = allow / do nothing.** This is the default and what every
stub does. To *act*, print exactly **one** JSON object on stdout via an emit helper.

### sessionStart / userPromptSubmitted — inject context

```bash
hook_emit_context "text the model should see" "SessionStart"
```
Emits `{"hookSpecificOutput":{"hookEventName":...,"additionalContext":"..."}}`.
The text becomes context the agent sees before it responds.

### preToolUse — allow or deny (fail-closed)

```bash
hook_deny  "reason the tool was blocked"   # hard block
hook_allow "reason"                         # force allow (rarely needed; default is allow)
```
A **nonzero exit, error, or timeout here DENIES the tool**. See WRITING-HOOKS.md.

### agentStop — allow or block the stop

```bash
# allow stop:
exit 0                                       # (or print {"decision":"allow"})
# force another turn — reason is fed back to the agent as a prompt:
"${_HOOK_JQ:-jq}" -n --arg r "you're not done: ..." '{decision:"block", reason:$r}'
```

### postToolUse / postToolUseFailure — stdout ignored

Use these for observation only: logging, metrics, marking state. Copilot does not
read their stdout.

## Wiring (hooks.json)

```json
{
  "$schema": "https://aka.ms/vscode-copilot-hooks.schema.json",
  "version": 1,
  "hooks": {
    "sessionStart":       [ { "type": "command", "command": "./.github/hooks/events/session-start.sh", "timeoutSec": 10 } ],
    "userPromptSubmitted":[ { "type": "command", "command": "./.github/hooks/events/user-prompt.sh", "timeoutSec": 10 } ],
    "preToolUse":         [ { "type": "command", "command": "./.github/hooks/events/pre-tool.sh", "timeoutSec": 10 } ],
    "postToolUse":        [ { "type": "command", "command": "./.github/hooks/events/post-tool.sh", "timeoutSec": 10 } ],
    "postToolUseFailure": [ { "type": "command", "command": "./.github/hooks/events/post-tool-failure.sh", "timeoutSec": 10 } ],
    "agentStop":          [ { "type": "command", "command": "./.github/hooks/events/agent-stop.sh", "timeoutSec": 15 } ]
  }
}
```

`timeoutSec` matters most for `preToolUse`: a timeout there is treated as an error and
**denies the tool**. Keep it generous and keep the hook fast.
