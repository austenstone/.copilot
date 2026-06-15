#!/usr/bin/env bash
# sessionStart — fires ONCE when a session boots (new or resume).
#
# Payload: initialPrompt, source ("new"|"resume"), sessionId, cwd.
# To inject context the model will see, print via hook_emit_context.
# See examples/01-context-injection for a real implementation.
. "${BASH_SOURCE[0]%/*}/../lib.sh" 2>/dev/null || true

# Example (uncomment to try):
#   hook_emit_context "Booted on branch $(git rev-parse --abbrev-ref HEAD 2>/dev/null)"

exit 0
