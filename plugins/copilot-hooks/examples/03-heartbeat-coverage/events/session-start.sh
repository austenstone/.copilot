#!/usr/bin/env bash
# HEARTBEAT EXAMPLE — sessionStart: seed coverage for fresh /heartbeat sessions.
# Backstop for scheduled/non-interactive runs that may not fire
# userPromptSubmitted. Skips resumes so an in-progress run isn't reset.
. "${BASH_SOURCE[0]%/*}/../lib.sh" 2>/dev/null || true
. "${BASH_SOURCE[0]%/*}/../coverage.sh" 2>/dev/null || true

if command -v cov_seed >/dev/null 2>&1 \
   && [ "$(hook_source 2>/dev/null)" != "resume" ] \
   && cov_is_heartbeat_prompt "$(hook_prompt 2>/dev/null)"; then
  cov_seed "$(hook_session_id)" "session-start" 2>/dev/null || true
fi
exit 0
