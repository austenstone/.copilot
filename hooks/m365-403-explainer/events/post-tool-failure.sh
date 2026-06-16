#!/usr/bin/env bash
# postToolUseFailure — fires when a tool returns resultType:"failure". For MCP
# tools that is exactly when the server replies isError:true (how m365 surfaces
# a 403). This is the PRIMARY channel: the CLI reads top-level "additionalContext"
# from our stdout and injects it into the agent's context.
#
# CLI contract (verified against the installed @github/copilot bundle):
#   stdin  : {sessionId,timestamp,cwd,toolName,toolArgs,error}
#   stdout : top-level {"additionalContext": "<text>"}   (NOT hookSpecificOutput)
set +e
trap 'exit 0' EXIT

DIR="$HOME/.copilot/hooks/m365-403-explainer"

main() {
  . "$DIR/playbook.sh" 2>/dev/null || return 0

  JQ="${HOOK_JQ:-$(command -v jaq 2>/dev/null || command -v jq 2>/dev/null)}"
  payload="$(cat)"
  [ -n "$payload" ] || return 0

  if [ -n "$JQ" ]; then
    tool="$("$JQ" -r '.toolName // ""' <<<"$payload" 2>/dev/null)"
    err="$("$JQ" -r '(.error // "") | if type=="object" then tojson else tostring end' <<<"$payload" 2>/dev/null)"
  else
    # Degraded: no JSON engine. Best-effort scrape; treat whole payload as error text.
    tool="$(printf '%s' "$payload" | grep -oE '"toolName"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*:"//; s/"$//')"
    err="$payload"
  fi

  m365_403_is_m365_tool "$tool" || return 0
  printf '%s' "$err" | grep -qiE '(\b403\b|forbidden|unauthorized|accessdenied|authorization_requestdenied)' || return 0

  # Organizer hint, if the joinUrl rode along in the error text.
  org_oid="$(m365_403_extract_oid "$err")"
  text="$(m365_403_playbook "$tool" "$org_oid")"

  if [ -n "$JQ" ]; then
    "$JQ" -n --arg c "$text" '{additionalContext:$c}'
  else
    # Hand-roll minimal JSON (escape backslash, quote, newline).
    esc="$(printf '%s' "$text" | sed 's/\\/\\\\/g; s/"/\\"/g' | awk 'BEGIN{ORS="\\n"}{print}')"
    printf '{"additionalContext":"%s"}' "$esc"
  fi

  # Best-effort local log for observability.
  d="$HOME/.copilot/m365-403-state"; mkdir -p "$d" 2>/dev/null \
    && printf '%s\t%s\t%s\n' "$(date -u +%FT%TZ 2>/dev/null)" "$tool" "$(printf '%s' "$err" | tr '\t\n\r' '   ')" >> "$d/failures.log" 2>/dev/null
  return 0
}

OUT="$(main 2>/dev/null)"
[ -n "$OUT" ] && printf '%s' "$OUT"
exit 0
