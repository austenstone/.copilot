---
name: google-search
description: "Google web search from the command line. Run google-search.js to get ranked title/URL/snippet results, headless, on a shared browser profile. Use for current facts, docs, releases, versions, news, prices, anything past the knowledge cutoff. Triggers: 'google search', 'web search', 'search the web', 'look it up', 'what's the latest', 'current version of X'."
---

# Google Search

```bash
node ~/.copilot/skills/google-search/google-search.js "<query>"
```

- Add `--ai` to include Google AI Overview text and citation links when Google shows one.
- Add `--json` for raw results, `--help` for the full rundown.
- `--ai` waits for late-rendered AI content. Oversized AI output is written to `skills/google-search/outputs/`, and stdout keeps the file path plus links so agents can navigate.
- If it exits with a CAPTCHA wall (code 2), close any open MCP browser, then run `--solve` once to clear it in a headed window. The cookie persists and headless runs clean for days.

Read what the script tells you on stderr and follow it.