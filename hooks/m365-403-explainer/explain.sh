#!/usr/bin/env bash
# m365-403-explainer — PostToolUse hook
#
# When an m365 MCP tool returns 403/Forbidden, the surface error tells the agent
# almost nothing useful ("Forbidden"). The real cause is almost never "you lack
# permission" — it's a domain constraint (not the organizer, transcript wasn't
# enabled, recording never ran, you're not a chat member, etc.) that the agent
# can't see in the bare error.
#
# This hook reads the PostToolUse payload, detects m365 tool 403s, and emits
# `additionalContext` that tells the agent the real likely causes so it stops
# retrying and either skips the step or asks the user for an alternative.
#
# Wired by ~/.copilot/hooks/m365-403-explainer.json. Safe to run on every
# PostToolUse — exits 0 silently for anything that doesn't match.
#
# Input shape handled (covers VS Code Copilot Chat + Copilot CLI):
#   VS Code:  { "tool_name": "...", "tool_response": "...", ... }
#   CLI:      { "toolName": "...",  "toolResult":  "...", "error": "...", ... }

set +e
trap 'exit 0' EXIT

input="$(cat 2>/dev/null || true)"
[ -z "$input" ] && exit 0

JQ="${HOOK_JQ:-$(command -v jaq 2>/dev/null || command -v jq 2>/dev/null || true)}"
[ -n "$JQ" ] || exit 0

# Shared playbook text (single source of truth, also used by the CLI hooks).
. "${BASH_SOURCE[0]%/*}/playbook.sh" 2>/dev/null || true

# Extract tool name (try VS Code snake_case first, then CLI camelCase)
tool="$("$JQ" -r '.tool_name // .toolName // ""' <<<"$input" 2>/dev/null)"
[ -z "$tool" ] && exit 0

# Gate: only act on m365 MCP tools. Match common patterns:
#   mcp_m365-calendar_get_meeting_transcript
#   m365-mail_send_email
#   etc.
case "$tool" in
  *m365*|*M365*|*microsoft365*) ;;
  *) exit 0 ;;
esac

# Pull the response/error text — try every field that might carry it
resp="$("$JQ" -r '
  ( .tool_response // .toolResult // .error // .response // "" )
  | if type == "object" or type == "array" then tostring else . end
' <<<"$input" 2>/dev/null)"

# Detect 403 / Forbidden (case insensitive)
echo "$resp" | grep -qiE '(\b403\b|forbidden|unauthorized)' || exit 0

# ---------------------------------------------------------------------------
# Build the explanation from the shared playbook (transcript-aware). Falls back
# to a short generic note if playbook.sh could not be sourced.
# ---------------------------------------------------------------------------
if command -v m365_403_playbook >/dev/null 2>&1; then
  explain="$(m365_403_playbook "$tool")"
else
  explain="m365 returned 403 on '$tool'. For Graph / m365 tools this is rarely a literal permission denial (not the organizer, transcript not enabled, not a chat member, wrong tenant, Conditional Access). Do NOT retry the same call — ask the user for an alternative source or skip the step."
fi

"$JQ" -n --arg c "$explain" '{
  hookSpecificOutput: {
    hookEventName: "PostToolUse",
    additionalContext: $c
  }
}'

exit 0
