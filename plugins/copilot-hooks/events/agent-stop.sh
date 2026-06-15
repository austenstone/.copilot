#!/usr/bin/env bash
# agentStop — fires when the agent is about to stop its turn.
#
# Payload: stopReason, sessionId, cwd, transcriptPath (when available).
# Output contract:
#   exit 0 / empty / {"decision":"allow"}     -> allow the agent to stop
#   {"decision":"block","reason":"<text>"}    -> force another turn; <text> is
#                                                fed back to the agent as a prompt
#
# This is how you build "not done yet" gates. See examples/03-heartbeat-coverage
# for a complete one that blocks until required work is verified.
. "${BASH_SOURCE[0]%/*}/../lib.sh" 2>/dev/null || true

# Example (uncomment to try): never block, just observe.
#   printf '%s\tstop=%s\n' "$(date -u +%FT%TZ)" "$(hook_stop_reason)" >> "$HOME/.copilot/stops.log"

exit 0
