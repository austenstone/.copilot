#!/usr/bin/env bash
# userPromptSubmitted — fires every time the user submits a prompt.
#
# Payload: prompt, sessionId, cwd.
# Like sessionStart, hook_emit_context injects context the model sees for
# this turn. Useful for prompt-triggered protocols or just-in-time reminders.
. "${BASH_SOURCE[0]%/*}/../lib.sh" 2>/dev/null || true

# Example (uncomment to try):
#   case "$(hook_prompt)" in
#     */deploy*) hook_emit_context "Reminder: run the test suite before deploying." "UserPromptSubmitted" ;;
#   esac

exit 0
