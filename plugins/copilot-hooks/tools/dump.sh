#!/usr/bin/env bash
# dump.sh — universal hook input dumper. The single most useful debugging tool
# when building hooks: wire it to every event and watch exactly what Copilot
# sends you.
#
# Wire it via tools/dump.json (or add it alongside your real hooks). For every
# firing it appends a full record of everything the hook receives:
#   - the raw JSON on stdin (the real payload)
#   - any CLI args
#   - the full environment
#
# Output:
#   ~/.copilot/hook-dumps/dump.log      (human-readable, all events)
#   ~/.copilot/hook-dumps/dump.jsonl    (one JSON object per firing, replayable)
#   ~/.copilot/hook-dumps/<event>.json  (latest payload per event, for quick peeking)
#
# Writes NOTHING to stdout so it never influences a preToolUse decision.

DUMP_DIR="${HOME}/.copilot/hook-dumps"
mkdir -p "$DUMP_DIR"

# Slurp stdin (the payload). Skip if nothing is piped.
STDIN_DATA=""
if [ ! -t 0 ]; then
  STDIN_DATA="$(cat)"
fi

# GNU date supports %3N (millis); BSD/macOS date does not, so fall back cleanly.
TS="$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ 2>/dev/null)"
case "$TS" in
  *3NZ|"") TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)" ;;
esac

# Infer the event from which keys are present (Copilot sends no event-name field).
EVENT="unknown"
if command -v jq >/dev/null 2>&1 && [ -n "$STDIN_DATA" ]; then
  EVENT="$(printf '%s' "$STDIN_DATA" | jq -r '
    if   has("initialPrompt") then "sessionStart"
    elif has("stopReason")    then "agentStop"
    elif (has("toolName") and has("error"))      then "postToolUseFailure"
    elif (has("toolName") and has("toolResult")) then "postToolUse"
    elif has("toolName")      then "preToolUse"
    elif has("prompt")        then "userPromptSubmitted"
    else "unknown" end' 2>/dev/null || echo unknown)"
fi

# --- Human-readable log -------------------------------------------------------
{
  echo "================================================================"
  echo "[$TS] event=$EVENT pid=$$ argc=$#"
  echo "---- args ----"
  i=0; for a in "$@"; do echo "  argv[$i]=$a"; i=$((i+1)); done
  echo "---- stdin (raw payload) ----"
  if [ -n "$STDIN_DATA" ]; then
    if command -v jq >/dev/null 2>&1; then
      printf '%s' "$STDIN_DATA" | jq . 2>/dev/null || printf '%s\n' "$STDIN_DATA"
    else
      printf '%s\n' "$STDIN_DATA"
    fi
  else
    echo "  (empty)"
  fi
  echo "---- environment ----"
  env | sort | sed 's/^/  /'
  echo ""
} >> "$DUMP_DIR/dump.log"

# --- Machine-readable JSONL (stdin payload + meta) ----------------------------
if command -v jq >/dev/null 2>&1; then
  jq -n \
    --arg ts "$TS" \
    --arg event "$EVENT" \
    --arg stdin "$STDIN_DATA" \
    --argjson argv "$(printf '%s\n' "$@" | jq -R . | jq -s .)" \
    --argjson env "$(env | jq -R 'split("=") | {(.[0]): (.[1:] | join("="))}' | jq -s 'add // {}')" \
    '{ts: $ts, event: $event, argv: $argv, env: $env,
      stdin_raw: $stdin,
      stdin_parsed: ($stdin | try fromjson catch null)}' \
    >> "$DUMP_DIR/dump.jsonl" 2>/dev/null

  # Latest payload per event, for quick inspection.
  [ -n "$STDIN_DATA" ] && printf '%s' "$STDIN_DATA" | jq . > "$DUMP_DIR/${EVENT}.json" 2>/dev/null
fi

exit 0
