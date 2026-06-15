#!/usr/bin/env bash
# ============================================================================
#  coverage.sh - heartbeat inbound-coverage gate. SOURCE it after lib.sh.
# ============================================================================
#
#  THE PROBLEM IT SOLVES
#    A scheduled "heartbeat" session is supposed to CHECK a set of inbound
#    sources (here: Slack, Teams, Email, GitHub) before it stops. Agents,
#    being eager, sometimes declare victory early. This gate makes that
#    impossible: agentStop BLOCKS termination — re-prompting the agent — until
#    every required source has a successful READ/SEARCH/LIST tool call on record.
#
#  HOW IT FITS THE EVENT HOOKS (this is the pattern worth copying)
#    seed     user-prompt.sh / session-start.sh (heartbeat prompt) -> cov_seed
#             pre-tool.sh   (skill==heartbeat)                      -> cov_seed_if_absent
#    mark     post-tool.sh: cov_classify_read <tool> <args> -> cov_mark
#    enforce  agent-stop.sh: cov_missing -> block while non-empty (capped)
#
#  WHY "READ" ONLY
#    A Slack *send* or a `gh issue create` is not "checking notifications". Only
#    read/search/list calls count, so the gate measures intent (did the agent
#    look?) not side effects.
#
#  STATE  ~/.copilot/heartbeat-state/coverage-<sid>.json
#    { required:[teams,slack,mail,github], covered:[], block_iterations:0,
#      max_block_iterations:3, status:"open", started:"<iso>" }
#
#  SAFETY  every function is best-effort. A missing jq engine or a write race
#    degrades to "did not mark", which can only cause one extra (harmless)
#    block, never a brick. Never `set -e` in a sourcing hook; never `exit` here.
#
#  CUSTOMIZE  change COV_REQUIRED and the patterns in cov_classify_read to your
#    own sources/tools. That function is the whole domain-specific surface.
# ============================================================================

COV_DIR="${COPILOT_STATE_DIR:-$HOME/.copilot}/heartbeat-state"
COV_LOG="$COV_DIR/coverage.log"
COV_REQUIRED="teams slack mail github"
COV_MAX_BLOCKS=3

# Share lib.sh's engine; fall back to a local probe if sourced standalone.
_COV_JQ="${_HOOK_JQ:-$(command -v jaq 2>/dev/null || command -v jq 2>/dev/null || true)}"

cov_state_file() { printf '%s/coverage-%s.json' "$COV_DIR" "${1:-unknown}"; }

cov_log() {
  mkdir -p "$COV_DIR" 2>/dev/null || return 0
  printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" "$*" >> "$COV_LOG" 2>/dev/null || true
}

# True (0) only when a prompt is the actual `/heartbeat` slash command (with
# optional trailing args), NOT merely a prompt that mentions "heartbeat". This
# is deliberately strict: a dev session *discussing* heartbeat must not seed,
# else it gets gated on its own inbound sources.
cov_is_heartbeat_prompt() {
  local p
  p="$(printf '%s' "${1:-}" | sed 's/^[[:space:]]*//' 2>/dev/null)"
  case "$p" in
    /heartbeat|/heartbeat[[:space:]]*) return 0 ;;
    *) return 1 ;;
  esac
}

# Write a fresh state file (resets covered + block_iterations). Called at the
# START of a heartbeat run so a reused session id can't carry stale coverage.
cov_seed() {
  local sid="$1" why="${2:-}" sf
  [ -n "$sid" ] || return 0
  [ -n "$_COV_JQ" ] || return 0
  mkdir -p "$COV_DIR" 2>/dev/null || return 0
  sf="$(cov_state_file "$sid")"
  "$_COV_JQ" -n --arg started "$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" \
    --argjson maxb "$COV_MAX_BLOCKS" \
    --argjson req "$(printf '%s\n' $COV_REQUIRED | "$_COV_JQ" -R . | "$_COV_JQ" -s .)" \
    '{required:$req, covered:[],
      block_iterations:0, max_block_iterations:$maxb, status:"open", started:$started}' \
    > "$sf" 2>/dev/null && cov_log "seed sid=$sid ($why)"
  return 0
}

cov_seed_if_absent() { # only seed when no state exists (avoids mid-run reset)
  local sid="$1"
  [ -n "$sid" ] || return 0
  [ -f "$(cov_state_file "$sid")" ] && return 0
  cov_seed "$sid" "${2:-if-absent}"
}

# Add a source to covered[] under a portable mkdir lock. Source must be in the
# required set. Safe to call repeatedly.
cov_mark() {
  local sid="$1" src="$2" sf lock tmp tries=0
  [ -n "$sid" ] && [ -n "$src" ] || return 0
  [ -n "$_COV_JQ" ] || return 0
  case " $COV_REQUIRED " in *" $src "*) : ;; *) return 0 ;; esac
  sf="$(cov_state_file "$sid")"
  [ -f "$sf" ] || return 0
  lock="$sf.lock"
  while ! mkdir "$lock" 2>/dev/null; do
    tries=$((tries + 1))
    [ "$tries" -ge 20 ] && break          # ~1s ceiling; proceed unlocked rather than hang
    sleep 0.05 2>/dev/null || sleep 1
  done
  tmp="$(mktemp 2>/dev/null)" || { rmdir "$lock" 2>/dev/null || true; return 0; }
  if "$_COV_JQ" --arg b "$src" \
      'if (.covered // []) | index($b) then . else .covered = ((.covered // []) + [$b]) end' \
      "$sf" > "$tmp" 2>/dev/null && [ -s "$tmp" ]; then
    mv "$tmp" "$sf" 2>/dev/null && cov_log "mark sid=$sid covered=$src"
  else
    rm -f "$tmp" 2>/dev/null || true
  fi
  rmdir "$lock" 2>/dev/null || true
  return 0
}

# Print the comma-joined set of still-missing required sources (empty if all in).
cov_missing() {
  local sid="$1" sf
  sf="$(cov_state_file "${sid}")"
  [ -f "$sf" ] && [ -n "$_COV_JQ" ] || { printf ''; return 0; }
  "$_COV_JQ" -r '((.required // []) - (.covered // [])) | join(", ")' "$sf" 2>/dev/null || printf ''
}

# Map a successful tool call to a required source IFF it is a READ/SEARCH/LIST
# call. Writes (send/create/update/merge) deliberately return nothing.
# Args: <tool_name> <tool_args_json>. Echoes teams|slack|mail|github|"".
#
# *** THIS is the function you customize for your own tools/sources. ***
cov_classify_read() {
  local name="$1" args="$2" cmd
  case "$name" in
    # Teams reads (List/Search/Get/Read). Excludes Send.
    *m365-teams-List*|*m365-teams-Search*|*m365-teams-Get*|*m365-teams-Read*) printf 'teams'; return ;;
    *m365-teams-Send*) return ;;
    # Slack reads (search_*/read_*). Excludes send/post/update.
    *slack-slack_search*|*slack-slack_read*) printf 'slack'; return ;;
    # Email reads (Search/Get/Download/List). Excludes Send/Reply/Forward/Draft/Update.
    *m365-mail-Search*|*m365-mail-Get*|*m365-mail-Download*|*m365-mail-List*) printf 'mail'; return ;;
    # GitHub MCP reads (search_/list_/get_). Excludes create_/update_/add_/merge_.
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
