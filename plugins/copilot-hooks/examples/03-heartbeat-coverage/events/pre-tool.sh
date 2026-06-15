#!/usr/bin/env bash
# HEARTBEAT EXAMPLE — preToolUse: seed coverage when the `skill` tool invokes
# heartbeat (covers sessions that start via a skill call, not a /heartbeat prompt).
#
# FAIL-CLOSED EVENT: no `set -e`, trap to force exit 0, all logic in a guarded
# subroutine whose stdout is discarded (empty stdout = default allow).
set +e
trap 'exit 0' EXIT

_pretool_main() {
  . "${BASH_SOURCE[0]%/*}/../lib.sh" 2>/dev/null || return 0
  . "${BASH_SOURCE[0]%/*}/../coverage.sh" 2>/dev/null || return 0
  command -v cov_seed_if_absent >/dev/null 2>&1 || return 0
  [ "$(hook_tool_name 2>/dev/null)" = "skill" ] || return 0
  local skill
  skill="$(hook_tool_args 2>/dev/null | "${_HOOK_JQ:-jq}" -r '.skill // empty' 2>/dev/null)"
  [ "$skill" = "heartbeat" ] && cov_seed_if_absent "$(hook_session_id)" "skill-tool"
  return 0
}

_pretool_main >/dev/null 2>&1 || true
exit 0
