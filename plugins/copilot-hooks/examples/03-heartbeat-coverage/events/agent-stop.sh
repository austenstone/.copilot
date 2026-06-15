#!/usr/bin/env bash
# HEARTBEAT EXAMPLE — agentStop: block termination until a /heartbeat run has
# checked every required inbound source. Non-heartbeat sessions (no state file)
# stop normally.
#
# Output contract:
#   {"decision":"block","reason":<str>}   -> forces another turn (reason = prompt)
#   exit 0 / empty / {"decision":"allow"} -> allow stop
. "${BASH_SOURCE[0]%/*}/../lib.sh" 2>/dev/null || true
. "${BASH_SOURCE[0]%/*}/../coverage.sh" 2>/dev/null || true

command -v cov_missing >/dev/null 2>&1 || exit 0
JQ="${_HOOK_JQ:-$(command -v jaq 2>/dev/null || command -v jq 2>/dev/null || true)}"
[ -n "$JQ" ] || exit 0

SID="$(hook_session_id 2>/dev/null)"
[ -n "$SID" ] && [ "$SID" != "unknown" ] || exit 0

# Gate ONLY heartbeat sessions. A heartbeat run is seeded up front; no state
# file => not a heartbeat session => allow stop. We deliberately do NOT sniff
# the transcript to decide this (a session that merely discusses heartbeat
# would false-positive).
SF="$(cov_state_file "$SID")"
[ -f "$SF" ] || exit 0

# Resolve the session transcript for the gh-via-bash backstop only.
TRANSCRIPT="$(printf '%s' "$HOOK_INPUT" | "$JQ" -r '.transcriptPath // .transcript_path // empty' 2>/dev/null)"
if [ -z "$TRANSCRIPT" ] || [ ! -f "$TRANSCRIPT" ]; then
  CAND="$HOME/.copilot/session-state/$SID/events.jsonl"
  [ -f "$CAND" ] && TRANSCRIPT="$CAND"
fi

# Backstop: gh-via-bash read calls don't always fire postToolUse in every host.
# Credit github if the transcript shows a read-only gh inbox check. Safe because
# we already know (state file exists) this is a real heartbeat session.
if [ -n "$TRANSCRIPT" ] && [ -f "$TRANSCRIPT" ]; then
  if grep -Eaq '(^|[^a-zA-Z_])gh (issue (list|view|status)|pr (list|view|status|checks)|search|run (list|view)|notification)' "$TRANSCRIPT" 2>/dev/null; then
    cov_mark "$SID" "github"
  fi
fi

MISSING="$(cov_missing "$SID")"
if [ -z "$MISSING" ]; then
  "$JQ" '.status="complete" | .completed=(now|todate)' "$SF" > "$SF.tmp" 2>/dev/null \
    && mv "$SF.tmp" "$SF" 2>/dev/null || true
  cov_log "allow sid=$SID (all sources covered)"
  exit 0
fi

ITERS="$("$JQ" -r '.block_iterations // 0' "$SF" 2>/dev/null || echo 0)"
MAXB="$("$JQ" -r '.max_block_iterations // 3' "$SF" 2>/dev/null || echo 3)"

# Escape valve: don't loop forever if a source is genuinely unreachable (MCP
# down / auth). Allow stop and log it once. (Wire your own alert here, e.g.
# `gh issue create`, if you want a paper trail.)
if [ "$ITERS" -ge "$MAXB" ]; then
  cov_log "escape sid=$SID missing=[$MISSING] iters=$ITERS"
  exit 0
fi

# Still missing and under the cap -> bump and block.
"$JQ" '.block_iterations=((.block_iterations // 0)+1)' "$SF" > "$SF.tmp" 2>/dev/null \
  && mv "$SF.tmp" "$SF" 2>/dev/null || true

COVERED="$("$JQ" -r '(.covered // []) | join(", ")' "$SF" 2>/dev/null)"
[ -n "$COVERED" ] || COVERED="none"

REASON="HEARTBEAT COVERAGE GATE — not done yet.
Already checked: ${COVERED}. Still UNCHECKED: ${MISSING}.
Before you stop, make a successful READ/SEARCH/LIST call for each unchecked source (sends/writes do NOT count). Then you may stop."

cov_log "block sid=$SID missing=[$MISSING] iter=$((ITERS+1))/$MAXB"
"$JQ" -n --arg r "$REASON" '{decision:"block", reason:$r}'
exit 0
