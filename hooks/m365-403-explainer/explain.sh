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
# Wired by ~/.github/hooks/m365-403-explainer.json. Safe to run on every
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
# Build the explanation. Transcripts get the detailed playbook (it's the most
# common false-403 with the most ambiguous error). Everything else gets the
# general m365 403 cheat-sheet.
# ---------------------------------------------------------------------------
case "$tool" in
  *transcript*|*Transcript*|*recording*|*Recording*|*recap*|*Recap*)
    explain="m365 returned 403 on '$tool'. For Teams meeting transcripts/recordings, 403 almost never means 'permission denied' in the literal sense. The real cause is one of:

  1. You are NOT the meeting organizer. Only the organizer (and co-organizers / users the organizer explicitly shared the recap with) can retrieve a transcript via Graph. Check the joinUrl's Oid against your own user id.
  2. Transcription was never enabled for that meeting (it has to be turned on during the call, or set as a default by tenant policy).
  3. The meeting was not recorded, so there is no transcript artifact to fetch.
  4. The transcript exists but hasn't finished processing yet (can take minutes to hours after a long meeting).
  5. Tenant policy blocks transcript access via Graph for non-organizers even when the user has the recap in Teams UI.

Do NOT retry the same call — it will keep returning 403. Instead:
  - Tell the user the transcript is not accessible to you via Graph and ask them to paste it (Teams → meeting → Recap → Transcript → ... → Download).
  - Or pivot to a source you can read: chat messages from the meeting, meeting notes, calendar event body, follow-up email.
  - Or skip the transcript step and proceed with whatever context you already have."
    ;;
  *)
    explain="m365 returned 403 on '$tool'. For Microsoft Graph / m365 MCP tools, 403 is rarely a literal permission denial. Common real causes:

  - The resource belongs to another user's mailbox/calendar and you don't have delegate access.
  - You're not (or weren't at the relevant time) a member of the Teams chat/channel/group.
  - The item requires you to be the owner/organizer (meeting transcripts, recordings, shared drive items).
  - Tenant Conditional Access or app permission policy is blocking that specific Graph endpoint.
  - The id you passed is for a resource in a different tenant than the one this MCP server is authenticated against.

Do NOT retry the same call with the same arguments. Either ask the user for an alternative source, switch to a tool that reads a resource you do own (your own mail/calendar/chat), or skip this step and continue with what you have."
    ;;
esac

"$JQ" -n --arg c "$explain" '{
  hookSpecificOutput: {
    hookEventName: "PostToolUse",
    additionalContext: $c
  }
}'

exit 0
