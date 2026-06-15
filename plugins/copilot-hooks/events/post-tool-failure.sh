#!/usr/bin/env bash
# postToolUseFailure — fires AFTER a tool call ERRORS.
#
# Payload: toolName, toolArgs, error, sessionId, cwd.
# Copilot ignores this hook's stdout — use it for observation (logging failures,
# alerting on repeated errors, capturing context for debugging).
. "${BASH_SOURCE[0]%/*}/../lib.sh" 2>/dev/null || true

# Example (uncomment to try): record tool failures for later inspection.
#   printf '%s\t%s\t%s\n' "$(date -u +%FT%TZ)" "$(hook_tool_name)" "$(hook_error)" \
#     >> "$HOME/.copilot/tool-failures.log"

exit 0
