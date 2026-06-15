#!/usr/bin/env bash
# EXAMPLE: preToolUse guardrail that DENIES dangerous shell commands.
#
# Demonstrates the fail-closed pattern done safely: all logic in a guarded
# subroutine, stdout captured, and an unconditional `exit 0` so a bug here can
# never brick the session. Only an explicit hook_deny JSON blocks a tool.
#
# INSTALL: copy this repo's lib.sh to .github/hooks/lib.sh, copy this file to
# .github/hooks/events/pre-tool.sh, and point preToolUse at it in hooks.json.
set +e
trap 'exit 0' EXIT

_main() {
  . "${BASH_SOURCE[0]%/*}/../lib.sh" 2>/dev/null || return 0
  [ "$(hook_tool_name)" = "bash" ] || return 0

  local cmd
  cmd="$(hook_tool_args | "${_HOOK_JQ:-jq}" -r '.command // empty' 2>/dev/null)"
  [ -n "$cmd" ] || return 0

  # Block a few genuinely destructive patterns. Tune to your own risk appetite.
  case "$cmd" in
    *"rm -rf /"*|*"rm -rf /*"*|*":(){ :|:& };:"*)
      hook_deny "Refusing destructive command: $cmd"; return 0 ;;
  esac
  # Block force-push to main/master.
  if printf '%s' "$cmd" | grep -Eq 'git push .*(--force|-f)\b.*\b(main|master)\b'; then
    hook_deny "Refusing force-push to a protected branch."; return 0
  fi

  return 0
}

_OUT="$(_main 2>/dev/null)"
[ -n "$_OUT" ] && printf '%s' "$_OUT"
exit 0
