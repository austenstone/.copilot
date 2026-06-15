#!/usr/bin/env bash
# HEARTBEAT EXAMPLE — postToolUse: credit a required source when a
# READ/SEARCH/LIST tool succeeds.
. "${BASH_SOURCE[0]%/*}/../lib.sh" 2>/dev/null || true
. "${BASH_SOURCE[0]%/*}/../coverage.sh" 2>/dev/null || true

if command -v cov_mark >/dev/null 2>&1; then
  _sid="$(hook_session_id 2>/dev/null)"
  if [ -n "$_sid" ] && [ -f "$(cov_state_file "$_sid")" ]; then
    _src="$(cov_classify_read "$(hook_tool_name 2>/dev/null)" "$(hook_tool_args 2>/dev/null)" 2>/dev/null)"
    [ -n "$_src" ] && cov_mark "$_sid" "$_src" 2>/dev/null || true
  fi
fi
exit 0
