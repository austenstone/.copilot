---
name: google-search
description: "Use when: google search, web search, search the web, look it up, latest news, current version, current facts, prices, docs, releases, or anything past the model cutoff. Run google-search.js for a structured Google SERP breakdown: AI Overview, sponsored results, web results, forums, videos, people also ask, and related searches."
---

# Google Search

# Use

```bash
node ~/.copilot/skills/google-search/google-search.js "<query>"
```

# Output

Default output is grouped by Google section with inline markdown links:

- AI Overview
- Sponsored results
- Web results
- Discussions and forums
- Videos
- People also ask
- People also search for
- Other results

# Flags

- `--json`: structured JSON
- `--raw`: rendered page text
- `--dom`: compact DOM outline
- `--html`: full HTML
- `--bench`: timing data on stderr
- `--help`: command help

# CAPTCHA

If exit code is 2, close any open MCP browser and run:

```bash
node ~/.copilot/skills/google-search/google-search.js --solve
```

The cookie persists in the shared profile.

Read what the script tells you on stderr and follow it.