#!/usr/bin/env bash
# HEARTBEAT EXAMPLE — userPromptSubmitted: seed coverage when prompt is /heartbeat.
. "${BASH_SOURCE[0]%/*}/../lib.sh" 2>/dev/null || true
. "${BASH_SOURCE[0]%/*}/../coverage.sh" 2>/dev/null || true

if command -v cov_seed >/dev/null 2>&1 && cov_is_heartbeat_prompt "$(hook_prompt 2>/dev/null)"; then
  cov_seed "$(hook_session_id)" "user-prompt" 2>/dev/null || true
fi
exit 0
