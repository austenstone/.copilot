#!/usr/bin/env bash
# preToolUse — pre-empt doomed organizer-gated m365 transcript/recording calls.
#
# *** FAIL-CLOSED EVENT *** a nonzero exit / crash / timeout here DENIES the tool.
# So: never `set -e`, always reach `exit 0`, and only an explicit top-level
# {"permissionDecision":"deny",...} on stdout blocks. Empty stdout = allow.
#
# CLI contract (verified against the installed @github/copilot bundle):
#   stdin  : {sessionId,timestamp,cwd,toolName,toolArgs}
#   stdout : top-level {permissionDecision,permissionDecisionReason,modifiedArgs}
#            (NOT wrapped in hookSpecificOutput — that's the VS Code schema)
set +e
trap 'exit 0' EXIT

DIR="$HOME/.copilot/hooks/m365-403-explainer"

emit() {
  # emit "<deny reason>" -> top-level deny JSON the CLI understands
  "$JQ" -n --arg r "$1" \
    '{permissionDecision:"deny",permissionDecisionReason:$r}'
}

main() {
  . "$DIR/playbook.sh" 2>/dev/null || return 0

  JQ="${HOOK_JQ:-$(command -v jaq 2>/dev/null || command -v jq 2>/dev/null)}"
  [ -n "$JQ" ] || return 0   # no JSON engine -> fail open

  payload="$(cat)"
  [ -n "$payload" ] || return 0

  tool="$("$JQ" -r '.toolName // ""' <<<"$payload" 2>/dev/null)"
  m365_403_is_m365_tool "$tool" || return 0
  m365_403_is_transcript_tool "$tool" || return 0

  # Normalize toolArgs (object, or a JSON string) into one object.
  norm='(.toolArgs // {}) | (if type=="string" then (try fromjson catch {}) else . end)'
  org_param="$("$JQ" -r "$norm | (.organizerUserId // \"\") | tostring" <<<"$payload" 2>/dev/null)"
  case "$org_param" in ""|null) ;; *) return 0 ;; esac   # explicit intent -> allow

  join="$("$JQ" -r "$norm | (.joinWebUrl // .joinUrl // \"\")" <<<"$payload" 2>/dev/null)"
  [ -n "$join" ] || return 0

  org_oid="$(m365_403_extract_oid "$join")"
  [ -n "$org_oid" ] || return 0

  self="${M365_SELF_OID:-$(cat "$DIR/self-oid" 2>/dev/null)}"
  [ -n "$self" ] || return 0

  lc() { printf '%s' "$1" | tr 'A-Z' 'a-z'; }
  [ "$(lc "$org_oid")" = "$(lc "$self")" ] && return 0   # you organize it -> allow

  emit "$(m365_403_playbook "$tool" "$org_oid")"
  return 0
}

OUT="$(main 2>/dev/null)"
[ -n "$OUT" ] && printf '%s' "$OUT"
exit 0
