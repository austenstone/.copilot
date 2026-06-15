# m365-403-explainer

A `PostToolUse` hook that translates the useless "403 Forbidden" returned by m365
MCP tools (especially Teams meeting transcript / recording calls) into actionable
context for the agent.

## Why

m365 / Microsoft Graph throws a bare `403 Forbidden` for a long list of things
that are not actually permission failures from the caller's perspective:

- The Teams meeting transcript caller isn't the organizer.
- Transcription was never enabled for the meeting.
- The meeting wasn't recorded.
- The resource lives in another mailbox the caller doesn't have delegate access to.
- The caller isn't (or wasn't) a member of the Teams chat/channel.

Without context, the agent reads `403 Forbidden` and tends to retry, escalate, or
tell the user "you don't have access" — none of which is useful. This hook
intercepts the failure and injects the real likely-causes playbook so the agent
either asks the user for an alternative source or skips the step.

## Wiring

The script lives in this repo (versioned dotfile). It's wired to VS Code via
`~/.github/hooks/m365-403-explainer.json`, which is the location listed in your
`chat.hookFilesLocations`. The JSON references this script by absolute path.

## What it does

1. Fires on every `PostToolUse`.
2. Exits silently for anything that isn't an m365 tool. Cheap.
3. For m365 tools, scans the response for `403` / `Forbidden` / `Unauthorized`.
4. On match, emits `hookSpecificOutput.additionalContext` with:
   - A transcript/recording-specific playbook when the tool name mentions
     transcript/recording/recap.
   - A general m365 403 playbook for everything else.

## Testing

Replay a sample payload:

```bash
echo '{
  "tool_name": "mcp_m365-calendar_get_meeting_transcript",
  "tool_response": "Failed to get meeting transcript (Forbidden): Request failed with status 403: Forbidden"
}' | ./explain.sh
```

You should see a JSON `hookSpecificOutput` with the transcript playbook in
`additionalContext`. For non-m365 tools or non-403 responses the script exits 0
with no output.
