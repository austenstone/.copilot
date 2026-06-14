---
name: playwright
description: "The two-browser shared-profile trick for the Playwright MCP: run headless by default, swap to a headed window to clear a CAPTCHA or log in once, then reuse that cookie headlessly for days. Use when a headless browser gets bot-walled, blocked by a CAPTCHA, or needs a logged-in session. Triggers: 'headless browser', 'log into a site and...', 'scrape a page', 'CAPTCHA', 'unusual traffic'."
---

# The two-browser trick

Headless browsers get bot-walled (CAPTCHA, "unusual traffic", login walls). Fix: two MCP servers sharing one persistent `--user-data-dir`. Solve the challenge once in a headed window, the cookie lands in the shared profile, headless runs clean for days.

```jsonc
"playwright-headless": {
  "command": "npx",
  "args": ["-y", "@playwright/mcp@latest", "--headless", "--user-data-dir", "/path/to/profile"]
},
"playwright-headed": {
  "command": "npx",
  "args": ["-y", "@playwright/mcp@latest", "--user-data-dir", "/path/to/profile"]
}
```

- `playwright-headless` (tools `mcp_playwright3_*`): default. Run everything here.
- `playwright-headed` (tools `mcp_playwright_*`): same profile, visible window. Only for solving a challenge or logging in.

## Assume it's warm

The profile is already warmed. Default to headless and just run: navigate, snapshot, act, close. Don't preflight a tool check or open the headed browser "to be safe." The swap below is a fallback for when a run actually gets blocked, not a step you do every time.

## The fallback swap: one browser per profile

Only when headless actually hits a wall (CAPTCHA, `/sorry`, a login gate in the snapshot). Chrome locks a profile dir to a single process, so `browser_close` before swapping servers or you get `Browser is already in use for <dir>`:

1. `browser_close` on headless (releases the lock).
2. `browser_navigate` headed to the same URL.
3. Solve the CAPTCHA / log in. Ask the user if needed.
4. `browser_close` headed.
5. Re-navigate headless. The cookie is now in the shared profile.

Cookies age out every few days; repeat the swap once when challenges return. Don't use `--isolated`, it throws away the profile every run.

## When the lock is stuck

If a browser crashes or an agent bails without `browser_close`, the orphan keeps holding the profile and every launch errors with `Browser is already in use`. Kill it and retry:

```bash
pkill -f "user-data-dir=/path/to/profile"
```

## Cleaner: one headless MCP + an on-demand headed script

The two-MCP swap works but the always-on headed server is a second process that keeps colliding on the lock. Better: run **only** the headless MCP, and when you hit a challenge, launch a one-off visible Chrome with a tiny script on the same profile (kill stale chrome → `open -na "Google Chrome" --args --user-data-dir=<profile> <url>`), solve it, quit the window. The cookie persists, the headless MCP reuses it, and there's no second server to contend with. See `skills/google-search/captcha.sh` for a working example.
