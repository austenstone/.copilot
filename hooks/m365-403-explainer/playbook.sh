#!/usr/bin/env bash
# playbook.sh — shared text for the m365-403-explainer.
#
# Single source of truth for the explanation strings, sourced by BOTH:
#   - explain.sh             (VS Code PostToolUse hook → additionalContext)
#   - plugins/.../events/*   (Copilot CLI preToolUse deny + deferred context)
#
# SOURCE this file; it only defines functions. macOS bash 3.2 clean.

# m365_403_is_transcript_tool <toolName> -> exit 0 if the tool is an
# organizer-gated transcript/recording/recap/insight/attendance call.
m365_403_is_transcript_tool() {
  case "$1" in
    *[Tt]ranscript*|*[Rr]ecording*|*[Rr]ecap*|*[Ii]nsight*|*[Aa]ttendance*) return 0 ;;
    *) return 1 ;;
  esac
}

# m365_403_is_m365_tool <toolName> -> exit 0 if this looks like an m365 tool.
m365_403_is_m365_tool() {
  case "$1" in
    *m365*|*M365*|*microsoft365*) return 0 ;;
    *) return 1 ;;
  esac
}

# m365_403_extract_oid <text> -> echoes the organizer GUID from a Teams joinUrl
# (handles both URL-encoded `Oid%22%3a%22<guid>` and decoded `"Oid":"<guid>"`).
m365_403_extract_oid() {
  printf '%s' "$1" \
    | grep -oiE 'Oid(%22%3a%22|"[[:space:]]*:[[:space:]]*")[0-9a-f-]{36}' \
    | grep -oiE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' \
    | head -1
}

# m365_403_playbook <toolName> [organizerOid] -> echoes the explanation text.
m365_403_playbook() {
  _tool="${1:-an m365 tool}"
  _org="${2:-}"
  if m365_403_is_transcript_tool "$_tool"; then
    _who=""
    [ -n "$_org" ] && _who="
  - The meeting's organizer id is ${_org}, which is not you. Either drop the
    transcript step or pass organizerUserId=${_org} (only works if the organizer
    shared the recap with you)."
    cat <<EOF
m365 403 on '${_tool}'. For Teams transcripts/recordings/recaps/insights/attendance,
403 almost never means a literal "permission denied". The real cause is one of:

  1. You are NOT the meeting organizer. Only the organizer (and co-organizers /
     users the organizer shared the recap with) can pull these via Graph.
     Check the joinUrl's Oid against your own user id.
  2. Transcription/recording was never enabled for that meeting.
  3. The meeting was not recorded, so there is no artifact to fetch.
  4. The transcript exists but has not finished processing yet.
  5. Tenant policy blocks Graph access for non-organizers even when the recap
     shows in the Teams UI.${_who}

Do NOT retry the same call — it will keep returning 403. Instead:
  - Tell the user it is not accessible to you via Graph and ask them to paste it
    (Teams → meeting → Recap → Transcript → ... → Download), or
  - Pivot to a source you can read (meeting chat, notes, calendar body, follow-up
    email), or
  - Skip the step and continue with the context you already have.
EOF
  else
    cat <<EOF
m365 403 on '${_tool}'. For Microsoft Graph / m365 tools, 403 is rarely a literal
permission denial. Common real causes:

  - The resource is in another user's mailbox/calendar and you lack delegate access.
  - You are not (or were not at the relevant time) a member of the Teams chat/channel.
  - The item requires you to be the owner/organizer (transcripts, recordings, drive items).
  - Tenant Conditional Access or app-permission policy blocks that Graph endpoint.
  - The id you passed belongs to a different tenant than this server is authed against.

Do NOT retry with the same arguments. Either ask the user for an alternative source,
switch to a tool that reads a resource you DO own (your own mail/calendar/chat), or
skip the step and continue.
EOF
  fi
}
