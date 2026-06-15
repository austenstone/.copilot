#!/usr/bin/env bash
# preToolUse — fires BEFORE every tool call. The agent is asking permission.
#
# *** FAIL-CLOSED EVENT — READ THIS ***
# A nonzero exit, an error, or a timeout here DENIES the tool. Get it wrong and
# EVERY tool call is blocked until you fix this file and restart Copilot. So:
#   - never `set -e`
#   - trap to force exit 0
#   - put all logic in a guarded subroutine whose stdout is discarded
#     (empty stdout = the default "allow")
#
# Payload: toolName, toolArgs, sessionId, cwd.
# Output:  empty (allow) | hook_deny "reason" (block) | hook_allow "reason".
# See examples/02-guardrail-deny for a real guardrail.
set +e
trap 'exit 0' EXIT

_pretool_main() {
  . "${BASH_SOURCE[0]%/*}/../lib.sh" 2>/dev/null || return 0

  # Example (uncomment to try): block `rm -rf /` style commands.
  #   if [ "$(hook_tool_name)" = "bash" ]; then
  #     cmd="$(hook_tool_args | "${_HOOK_JQ:-jq}" -r '.command // empty' 2>/dev/null)"
  #     case "$cmd" in *"rm -rf /"*) hook_deny "refusing to run 'rm -rf /'"; return 0 ;; esac
  #   fi

  return 0
}

# Capture stdout so only an explicit hook_deny/hook_allow JSON reaches Copilot.
_OUT="$(_pretool_main 2>/dev/null)"
[ -n "$_OUT" ] && printf '%s' "$_OUT"
exit 0
