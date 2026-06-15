#!/usr/bin/env bash
# ============================================================================
#  lib.sh - the Copilot CLI hooks library.  SOURCE it; never run it directly.
# ============================================================================
#
#  WHAT A HOOK IS
#    Copilot fires a hook at key moments (a tool runs, a prompt arrives, the
#    session starts or stops).  Each hook is a tiny script wired in hooks.json.
#    Copilot pipes a JSON payload to the script on stdin.  That payload has NO
#    event-name field, so you infer the event from which keys are present.
#    This library does that for you and hands back clean accessors.
#
#    A hook script is literally this:
#        #!/usr/bin/env bash
#        . "${BASH_SOURCE[0]%/*}/../lib.sh" 2>/dev/null || true
#        ... your logic, reading the payload via the hook_* functions ...
#        exit 0
#
#  THE SIX EVENTS                 (hook_event prints one of these)
#    event                payload key that triggers it   what else is populated
#    -------------------  ----------------------------   ----------------------
#    sessionStart         initialPrompt                  hook_source (new|resume)
#    userPromptSubmitted  prompt                         hook_prompt
#    preToolUse           toolName (no result yet)       hook_tool_name, hook_tool_args
#    postToolUse          toolName + toolResult          + hook_tool_result, hook_result_type
#    postToolUseFailure   toolName + error               + hook_error
#    agentStop            stopReason                     hook_stop_reason
#    Always available, every event: hook_event, hook_session_id, hook_cwd.
#
#  THE API                        (each accessor prints to stdout; use "$(...)")
#    core       hook_event  hook_session_id  hook_cwd  hook_tool_name
#               hook_source  hook_stop_reason  hook_prompt
#    payload    hook_tool_args      compact JSON of the tool's arguments
#               hook_tool_result    compact JSON of the tool's result
#               hook_result_type    "success" | "error" | ""
#               hook_error          the error string (postToolUseFailure)
#    emit       hook_emit_context "text" [Event]    inject context the model sees
#               hook_allow ["reason"]               preToolUse: force allow
#               hook_deny  "reason"                 preToolUse: BLOCK the tool
#
#  OUTPUT CONTRACT
#    Exit 0 with no stdout = allow / do nothing.  This is the default and is
#    what every stub does.  To act, print exactly ONE JSON object on stdout
#    using an emit helper:
#      sessionStart / userPromptSubmitted -> hook_emit_context adds model context
#      preToolUse                         -> hook_deny blocks, hook_allow allows
#      agentStop                          -> print {"decision":"block","reason":...}
#                                            to force another turn (see WRITING-HOOKS.md)
#    Copilot ignores stdout from the remaining events.
#
#  SAFETY            (a broken preToolUse hook can brick the whole session)
#    preToolUse is fail-closed: if its hook exits nonzero or errors (including a
#    timeout), the tool is DENIED.  Get it wrong and EVERY tool call is blocked
#    until you fix the file and restart Copilot.  Therefore: never `set -e`,
#    always end a hook with `exit 0`, and when editing a live hook or this lib,
#    write a temp file, validate it, then mv it into place (never edit in place).
#    Each stub sources this lib with `2>/dev/null || true`, so even a broken lib
#    cannot block tools - the hook still reaches its `exit 0`.
#
#  PERFORMANCE
#    stdin is read once (one cheap `cat`).  Parsing is lazy and memoized: a hook
#    that reads no field forks no engine pass; reading any core field or toolArgs
#    costs ONE engine pass; the possibly-large toolResult is a SECOND pass only
#    if you ask for it.  Engine is jaq if installed (~3x faster startup than jq),
#    else jq; override with HOOK_JQ=/path/to/engine.  With neither present, every
#    helper degrades to a safe no-op.
#
#  PORTABILITY       target is macOS system bash 3.2: no associative arrays, no
#    mapfile, no ${var^^}.  Keep any additions 3.2-clean.
# ============================================================================

# Read stdin once (safe when empty). `cat` is one cheap fork and robust for
# large postToolUse payloads.
HOOK_INPUT="$(cat 2>/dev/null || true)"

# Core fields, populated lazily by the single-pass parse below.
HOOK_EVENT="unknown"
HOOK_SID="unknown"
HOOK_CWD=""
HOOK_TOOL=""
HOOK_SOURCE=""
HOOK_STOP=""
HOOK_PROMPT=""
HOOK_ARGS="{}"
_HOOK_PARSED=""

# Result-family fields (the toolResult can be large), populated by a separate
# lazy pass so a postToolUse hook that only needs the tool name never pays to
# serialize a multi-megabyte result.
HOOK_RESULT="{}"
HOOK_RTYPE=""
HOOK_ERR=""
_HOOK_RESULT_PARSED=""

# JSON engine. Prefer jaq (Rust jq clone, ~3x faster startup) when installed,
# else fall back to stock jq. Override with HOOK_JQ=/path/to/engine. Filters
# used here are jq/jaq-compatible. Empty if neither is present, in which case
# every helper degrades safely to a no-op.
_HOOK_JQ="${HOOK_JQ:-$(command -v jaq 2>/dev/null || command -v jq 2>/dev/null || true)}"

# Single jq pass: infer the event and pull every common scalar at once,
# including the (always-small) toolArgs. Fields are emitted one-per-line (each
# sanitized to a single line so empties are preserved positionally) and read
# back with one `read` per field. We avoid an IFS=tab split because tab is
# whitespace and `read` would collapse empty middle fields, shifting columns.
# JSON fields are emitted via tojson (compact, control chars escaped -> no raw
# newlines), so they survive the line-based reader intact.
_hook_parse() {
  [ -n "$_HOOK_JQ" ] || return 0
  local lines
  lines="$(
    "$_HOOK_JQ" -r '
      def s: (. // "") | tostring | gsub("[\t\n\r]"; " ");
      def j: (. // "{}") | (if type=="string" then (fromjson? // {}) else . end);
      ( if   has("initialPrompt") then "sessionStart"
        elif has("stopReason")    then "agentStop"
        elif (has("toolName") and has("error"))      then "postToolUseFailure"
        elif (has("toolName") and has("toolResult")) then "postToolUse"
        elif has("toolName")      then "preToolUse"
        elif has("prompt")        then "userPromptSubmitted"
        else "unknown" end ) as $ev
      | [ $ev,
          ((.sessionId // .session_id // "unknown") | s),
          (.cwd | s),
          (.toolName | s),
          (.source | s),
          (.stopReason | s),
          ((.prompt // .initialPrompt // "") | s | .[0:4000]),
          ((.toolArgs | j) | tojson)
        ] | .[]
    ' <<<"$HOOK_INPUT" 2>/dev/null
  )"
  [ -z "$lines" ] && return 0
  { IFS= read -r HOOK_EVENT
    IFS= read -r HOOK_SID
    IFS= read -r HOOK_CWD
    IFS= read -r HOOK_TOOL
    IFS= read -r HOOK_SOURCE
    IFS= read -r HOOK_STOP
    IFS= read -r HOOK_PROMPT
    IFS= read -r HOOK_ARGS
  } <<EOF
$lines
EOF
  [ -z "$HOOK_EVENT" ] && HOOK_EVENT="unknown"
  [ -z "$HOOK_SID" ]   && HOOK_SID="unknown"
  [ -z "$HOOK_ARGS" ]  && HOOK_ARGS="{}"
}

# Parse on first access, memoized. A hook that never reads a core field never
# forks jq - so a no-op stub (and a guardrail that early-outs) costs ~nothing.
_hook_ensure() { [ -n "$_HOOK_PARSED" ] && return 0; _HOOK_PARSED=1; _hook_parse; }

# Secondary lazy pass: the toolResult (potentially large) plus its derived
# resultType and the top-level error. Only forked when a hook actually reads a
# result-family field. Memoized independently of the core parse.
_hook_parse_result() {
  [ -n "$_HOOK_JQ" ] || return 0
  local lines
  lines="$(
    "$_HOOK_JQ" -r '
      def s: (. // "") | tostring | gsub("[\t\n\r]"; " ");
      ((.toolResult // "{}") | (if type=="string" then (fromjson? // {}) else . end)) as $tr
      | [ ($tr | tojson),
          ($tr | if type=="object" then (.resultType // "") else "" end | s),
          (.error | s)
        ] | .[]
    ' <<<"$HOOK_INPUT" 2>/dev/null
  )"
  [ -z "$lines" ] && return 0
  { IFS= read -r HOOK_RESULT
    IFS= read -r HOOK_RTYPE
    IFS= read -r HOOK_ERR
  } <<EOF
$lines
EOF
  [ -z "$HOOK_RESULT" ] && HOOK_RESULT="{}"
}
_hook_ensure_result() { [ -n "$_HOOK_RESULT_PARSED" ] && return 0; _HOOK_RESULT_PARSED=1; _hook_parse_result; }

# ---- core accessors (single jq fork on first call, then pure shell) ---------
hook_event()       { _hook_ensure; printf '%s' "$HOOK_EVENT"; }
hook_session_id()  { _hook_ensure; printf '%s' "$HOOK_SID"; }
hook_cwd()         { _hook_ensure; printf '%s' "$HOOK_CWD"; }
hook_tool_name()   { _hook_ensure; printf '%s' "$HOOK_TOOL"; }
hook_source()      { _hook_ensure; printf '%s' "$HOOK_SOURCE"; }
hook_stop_reason() { _hook_ensure; printf '%s' "$HOOK_STOP"; }
hook_prompt()      { _hook_ensure; printf '%s' "$HOOK_PROMPT"; }

# ---- payload accessors (no per-call fork; served from the lazy parses) -------
# toolArgs comes from the core pass; the result family from the secondary pass.
hook_tool_args()   { _hook_ensure;        printf '%s' "$HOOK_ARGS"; }
hook_tool_result() { _hook_ensure_result; printf '%s' "$HOOK_RESULT"; }
hook_result_type() { _hook_ensure_result; printf '%s' "$HOOK_RTYPE"; }
hook_error()       { _hook_ensure_result; printf '%s' "$HOOK_ERR"; }

# ---- emit helpers (fork jq only when called) --------------------------------
# sessionStart / userPromptSubmitted: inject context the model will see.
hook_emit_context() { # hook_emit_context "<text>" ["EventName"]
  [ -z "$1" ] && return 0
  [ -n "$_HOOK_JQ" ] || return 0
  "$_HOOK_JQ" -n --arg c "$1" --arg e "${2:-SessionStart}" \
    '{hookSpecificOutput:{hookEventName:$e,additionalContext:$c}}'
}

# preToolUse: explicit allow (default is also allow, so this is rarely needed).
hook_allow() { # hook_allow ["reason"]
  [ -n "$_HOOK_JQ" ] || return 0
  "$_HOOK_JQ" -n --arg r "${1:-}" \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"allow",permissionDecisionReason:$r}}'
}

# preToolUse: deny the tool. Use sparingly - this is a hard block.
hook_deny() { # hook_deny "reason"
  [ -n "$_HOOK_JQ" ] || return 0
  "$_HOOK_JQ" -n --arg r "${1:-blocked by hook}" \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
}
