#!/usr/bin/env bash
# ============================================================================
#  coverage.sh - STATELESS heartbeat inbound-coverage derivation. SOURCE after lib.sh.
# ============================================================================
#
#  THE PROBLEM IT SOLVES
#    A scheduled `/heartbeat` session is supposed to CHECK a set of inbound
#    sources (here: Slack, Teams, Email, GitHub) before it stops. Agents, being
#    eager, sometimes declare victory early. The agentStop gate makes that
#    impossible: it refuses to let the session stop until every required source
#    has a successful READ/SEARCH/LIST call on record.
#
#  HOW THIS VERSION WORKS (no state file, one hook)
#    Everything is DERIVED at stop time from the session transcript
#    (~/.copilot/session-state/<sid>/events.jsonl). There is no seeding, no
#    per-tool marking, and nothing written to disk to coordinate events:
#      cov_is_heartbeat   <transcript>  -> is this a /heartbeat run at all?
#      cov_covered        <transcript>  -> which required sources were read?
#      cov_missing        <transcript>  -> required minus covered
#      cov_block_count    <transcript>  -> how many times we've already blocked
#    agent-stop.sh calls these. That's the entire system.
#
#  PORTABILITY NOTE
#    This trades portability for simplicity: it depends on Copilot's transcript
#    schema (event types tool.execution_start / tool.execution_complete /
#    skill.invoked / user.message and their .data shapes). If that schema
#    changes, update the jq here. The previous state-file design was schema-
#    independent but needed five hooks; this needs one.
#
#  WHY "READ" ONLY
#    A Slack *send* or a `gh issue create` is not "checking notifications". Only
#    read/search/list calls count, so the gate measures intent (did the agent
#    look?) not side effects.
#
#  CUSTOMIZE  change COV_REQUIRED and the patterns in cov_classify_read to your
#    own sources/tools. That function is the whole domain-specific surface.
# ============================================================================

COV_REQUIRED="teams slack mail github"
COV_MAX_BLOCKS=3
# Distinctive marker embedded in each block reason so we can count prior blocks
# straight from the transcript (no counter file needed).
COV_SENTINEL="HB-GATE-7f3"

# Optional append-only diagnostics (NOT coordination state; safe to delete).
COV_LOG="${COPILOT_STATE_DIR:-$HOME/.copilot}/heartbeat-state/coverage.log"

# Share lib.sh's engine; fall back to a local probe if sourced standalone.
_COV_JQ="${_HOOK_JQ:-$(command -v jaq 2>/dev/null || command -v jq 2>/dev/null || true)}"

cov_log() {
  mkdir -p "${COV_LOG%/*}" 2>/dev/null || return 0
  printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" "$*" >> "$COV_LOG" 2>/dev/null || true
}

# Resolve the session transcript: prefer the path Copilot hands us on stdin,
# else the conventional location. Echoes a path (may not exist).
cov_transcript() {
  local sid="$1" tp=""
  if [ -n "$_COV_JQ" ] && [ -n "${HOOK_INPUT:-}" ]; then
    tp="$(printf '%s' "$HOOK_INPUT" | "$_COV_JQ" -r '.transcriptPath // .transcript_path // empty' 2>/dev/null)"
  fi
  if [ -z "$tp" ] || [ ! -f "$tp" ]; then
    tp="${COPILOT_STATE_DIR:-$HOME/.copilot}/session-state/$sid/events.jsonl"
  fi
  printf '%s' "$tp"
}

# True (0) iff the transcript shows this is a real /heartbeat run: the heartbeat
# skill was invoked, OR a `skill` tool call selected heartbeat, OR a user prompt
# is the literal /heartbeat slash command. Deliberately strict so a session that
# merely *discusses* heartbeat is not gated.
cov_is_heartbeat() {
  local tr="$1"
  [ -f "$tr" ] && [ -n "$_COV_JQ" ] || return 1
  "$_COV_JQ" -s -e '
    any(.[];
      (.type=="skill.invoked" and (.data.name=="heartbeat"))
      or (.type=="tool.execution_start" and .data.toolName=="skill"
          and ((.data.arguments.skill // "")=="heartbeat"))
      or (.type=="user.message"
          and (((.data.content // .data.transformedContent // "")|tostring)
               | test("^[[:space:]]*/heartbeat")))
    )' "$tr" >/dev/null 2>&1
}

# Echo the space-separated set of required sources that have a SUCCESSFUL read on
# record. Joins tool.execution_start (name+args) to tool.execution_complete
# (success) by toolCallId, then runs each through cov_classify_read. Args are
# base64'd through the pipe so embedded tabs/newlines can't corrupt the stream.
cov_covered() {
  local tr="$1" tname targs64 targs src out=""
  [ -f "$tr" ] && [ -n "$_COV_JQ" ] || { printf ''; return 0; }
  while IFS="$(printf '\t')" read -r tname targs64; do
    [ -n "$tname" ] || continue
    targs="$(printf '%s' "$targs64" | base64 -d 2>/dev/null || true)"
    src="$(cov_classify_read "$tname" "$targs" 2>/dev/null)"
    [ -n "$src" ] || continue
    case " $out " in *" $src "*) : ;; *) out="$out $src" ;; esac
  done <<EOF
$("$_COV_JQ" -s -rc '
  ([ .[] | select(.type=="tool.execution_complete" and (.data.success==true))
         | .data.toolCallId ] | map({(.):true}) | add // {}) as $ok
  | .[]
  | select(.type=="tool.execution_start" and ($ok[(.data.toolCallId // "")] == true))
  | [(.data.toolName // ""), ((.data.arguments // {}) | tojson | @base64)] | @tsv
' "$tr" 2>/dev/null)
EOF
  printf '%s' "${out# }"
}

# Print the comma-joined set of still-missing required sources (empty if all in).
cov_missing() {
  local tr="$1" covered src out=""
  covered=" $(cov_covered "$tr") "
  for src in $COV_REQUIRED; do
    case "$covered" in *" $src "*) : ;; *) out="$out, $src" ;; esac
  done
  printf '%s' "${out#, }"
}

# Comma-joined covered set, for human-readable messages ("none" if empty).
cov_covered_csv() {
  local c; c="$(cov_covered "$1")"
  if [ -n "$c" ]; then printf '%s' "$(printf '%s' "$c" | sed 's/  */, /g')"; else printf 'none'; fi
}

# How many times we've already injected the gate this run = count of the
# sentinel in NON-assistant transcript events (so the agent echoing the text
# back doesn't inflate the count). Replaces the old block_iterations counter.
cov_block_count() {
  local tr="$1"
  [ -f "$tr" ] && [ -n "$_COV_JQ" ] || { printf '0'; return 0; }
  "$_COV_JQ" -s --arg s "$COV_SENTINEL" \
    '[ .[] | select(.type!="assistant.message") | select((tostring)|contains($s)) ] | length' \
    "$tr" 2>/dev/null || printf '0'
}

# ----------------------------------------------------------------------------
#  cov_classify_read - THE function you customize for your own tools/sources.
#  Map a successful tool call to a required source IFF it is a READ/SEARCH/LIST
#  call. Writes (send/create/update/merge) deliberately return nothing.
#  Args: <tool_name> <tool_args_json>. Echoes teams|slack|mail|github|"".
# ----------------------------------------------------------------------------
cov_classify_read() {
  local name="$1" args="$2" cmd
  case "$name" in
    *m365-teams-List*|*m365-teams-Search*|*m365-teams-Get*|*m365-teams-Read*) printf 'teams'; return ;;
    *m365-teams-Send*) return ;;
    *slack-slack_search*|*slack-slack_read*) printf 'slack'; return ;;
    *m365-mail-Search*|*m365-mail-Get*|*m365-mail-Download*|*m365-mail-List*) printf 'mail'; return ;;
    *github-mcp-server-search_*|*github-mcp-server-list_*|*github-mcp-server-get_*) printf 'github'; return ;;
    bash)
      [ -n "$_COV_JQ" ] || return 0
      cmd="$(printf '%s' "$args" | "$_COV_JQ" -r '.command // empty' 2>/dev/null)"
      cov_gh_read_line "$cmd" && printf 'github'
      return ;;
  esac
}

# True (0) if a shell command line is a READ-ONLY gh/github inbox check.
# Rejects writes (issue/pr create|comment|edit|close|merge ...) and any
# `gh api` carrying a mutating method.
cov_gh_read_line() {
  local cmd="$1"
  printf '%s' "$cmd" | grep -Eq '(-X|--method)[[:space:]]+(POST|PATCH|PUT|DELETE)' && return 1
  printf '%s' "$cmd" | grep -Eq '(^|[^a-zA-Z_])gh (issue (create|comment|edit|close|reopen|delete|lock)|pr (create|comment|review|edit|merge|close|ready|lock))' && return 1
  printf '%s' "$cmd" | grep -Eq '(^|[^a-zA-Z_])gh (issue (list|view|status)|pr (list|view|status|checks|diff)|search|run (list|view)|workflow (list|view)|release (list|view)|repo (list|view)|api|browse|notification)' && return 0
  return 1
}
