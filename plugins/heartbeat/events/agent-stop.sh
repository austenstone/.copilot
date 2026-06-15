#!/usr/bin/env bash
# HEARTBEAT — agentStop: the ENTIRE gate, in one hook, with no state file.
#
# At stop time it reads the session transcript and derives everything:
#   - is this a /heartbeat run?          cov_is_heartbeat
#   - which required sources were read?  cov_covered  (-> cov_missing)
#   - how many times have we blocked?    cov_block_count (escape valve)
# Non-heartbeat sessions have no heartbeat marker in their transcript, so they
# fall straight through and stop normally.
#
# Output contract:
#   {"decision":"block","reason":<str>}  -> forces another turn (reason = prompt)
#   exit 0 / empty stdout                -> allow stop
. "${BASH_SOURCE[0]%/*}/../lib.sh" 2>/dev/null || true
. "${BASH_SOURCE[0]%/*}/../coverage.sh" 2>/dev/null || true

command -v cov_missing >/dev/null 2>&1 || exit 0
JQ="${_HOOK_JQ:-$(command -v jaq 2>/dev/null || command -v jq 2>/dev/null || true)}"
[ -n "$JQ" ] || exit 0

SID="$(hook_session_id 2>/dev/null)"
[ -n "$SID" ] && [ "$SID" != "unknown" ] || exit 0

TRANSCRIPT="$(cov_transcript "$SID")"
[ -f "$TRANSCRIPT" ] || exit 0

# Only gate real heartbeat runs. Everything else stops normally.
cov_is_heartbeat "$TRANSCRIPT" || exit 0

MISSING="$(cov_missing "$TRANSCRIPT")"
if [ -z "$MISSING" ]; then
  cov_log "allow sid=$SID (all sources covered)"
  exit 0
fi

ITERS="$(cov_block_count "$TRANSCRIPT")"
case "$ITERS" in ''|*[!0-9]*) ITERS=0 ;; esac

# Escape valve: don't loop forever if a source is genuinely unreachable (MCP
# down / auth). Allow stop and log it once. (Wire your own alert here, e.g.
# `gh issue create`, if you want a paper trail.)
if [ "$ITERS" -ge "$COV_MAX_BLOCKS" ]; then
  cov_log "escape sid=$SID missing=[$MISSING] iters=$ITERS"
  exit 0
fi

COVERED="$(cov_covered_csv "$TRANSCRIPT")"

REASON="HEARTBEAT COVERAGE GATE — not done yet.
Already checked: ${COVERED}. Still UNCHECKED: ${MISSING}.
Before you stop, make a successful READ/SEARCH/LIST call for each unchecked source (sends/writes do NOT count). Then you may stop.
[gate:${COV_SENTINEL}]"

cov_log "block sid=$SID missing=[$MISSING] iter=$((ITERS+1))/$COV_MAX_BLOCKS"
"$JQ" -n --arg r "$REASON" '{decision:"block", reason:$r}'
exit 0
