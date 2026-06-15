#!/usr/bin/env bash
# EXAMPLE: sessionStart context injection.
#
# Injects a one-line workspace snapshot (branch, time, uncommitted file count)
# into the model's context at session boot. Whatever you pass to
# hook_emit_context becomes additionalContext the agent sees before its first
# response — a cheap way to make every session start "situationally aware".
#
# INSTALL: copy this repo's lib.sh to .github/hooks/lib.sh, copy this file to
# .github/hooks/events/session-start.sh, and point sessionStart at it in hooks.json.
. "${BASH_SOURCE[0]%/*}/../lib.sh" 2>/dev/null || true

CWD="$(hook_cwd)"; [ -n "$CWD" ] || CWD="$(pwd)"

PARTS=""
add() { [ -z "$PARTS" ] && PARTS="$1" || PARTS="$PARTS | $1"; }

BRANCH="$(git -C "$CWD" rev-parse --abbrev-ref HEAD 2>/dev/null)"
[ -n "$BRANCH" ] && add "Branch: $BRANCH"

add "$(date "+%A, %B %-d, %Y at %-I:%M %p")"

DIRTY="$(git -C "$CWD" status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
[ -n "$DIRTY" ] && [ "$DIRTY" -gt 0 ] && add "Uncommitted changes: $DIRTY files"

# Don't reset a resumed session's context expectations — only enrich fresh boots
# differently if you want. Here we inject for both, which is usually fine.
[ -n "$PARTS" ] && hook_emit_context "$PARTS"

exit 0
