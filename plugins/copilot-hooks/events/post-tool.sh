#!/usr/bin/env bash
# postToolUse — fires AFTER a tool call SUCCEEDS.
#
# Payload: toolName, toolArgs, toolResult, resultType, sessionId, cwd.
# Copilot ignores this hook's stdout — use it for observation/side effects
# (logging, metrics, marking state). See examples/03-heartbeat-coverage.
. "${BASH_SOURCE[0]%/*}/../lib.sh" 2>/dev/null || true

# Example (uncomment to try): log every successful tool to a file.
#   printf '%s\t%s\n' "$(date -u +%FT%TZ)" "$(hook_tool_name)" >> "$HOME/.copilot/tool.log"

exit 0
