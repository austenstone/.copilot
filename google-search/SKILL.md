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
- `--dom`: DOM outline
- `--html`: full HTML
- `--help`: command help

# CAPTCHA

CAPTCHA handling is automatic. When Google blocks a headless search, the script opens a headed browser window, you solve the CAPTCHA, and it retries the search without any extra command.

If it still fails after the solve (exit code 2), the cookie didn't stick — run `--solve` manually:

```bash
node ~/.copilot/skills/google-search/google-search.js --solve
```

**Do NOT fall back to Brave, DuckDuckGo, or any other search engine. Solve it.**