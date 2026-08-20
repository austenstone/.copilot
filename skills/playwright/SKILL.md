---
name: playwright
description: "Picking and driving a browser: which of the four browser MCPs to use, reading pages with evaluate instead of snapshot, the extension token bypass, strict-mode selectors, the .playwright-mcp artifact leak, and the headless shared-profile CAPTCHA trick. Use when: browse a site, scrape a page, log into a site and..., check a dashboard in the browser, CAPTCHA, 'unusual traffic', bot-walled, headless browser, browser keeps asking for a token."
---

# Browser access

## Pick the tool first

| Server | Use it for |
|---|---|
| **`playwright-extension`** | **Default.** Drives real Chrome via extension, inherits live cookies. Anything behind SSO: Power BI, Salesforce, C360, stafftools, personal accounts. |
| `playwright-headless` | Public web, bulk scraping, no window stealing focus. Shared warm profile. |
| `playwright-headed` | Only to solve a CAPTCHA or log in once, then swap back to headless. |
| `chrome-devtools` | Perf traces, network waterfalls, console debugging. Not general navigation. |
| `chrome-bridge` | Redundant with extension. Skip. |

Verified: `playwright-extension` walked straight into an authenticated financial app (Monarch) with zero setup, no login, no token prompt. Nothing else in the lineup does that.

Extension mode drives the user's **real browser**. Navigating retargets their active tab, and `browser_close` kills a tab they may want. Leave the tab open when you're done and say so.

## Read with `evaluate`, not `snapshot`

On any React / styled-components / CSS-in-JS app, `browser_snapshot` returns tens of KB of unlabeled `generic [ref=...]` div soup that answers nothing and burns context. Monarch's dashboard: 24KB of mush.

Go straight to text:

```js
() => {
  const lines = document.body.innerText.split('\n').map(s => s.trim()).filter(Boolean);
  return { url: location.pathname, count: lines.length, slice: lines.slice(0, 80) };
}
```

219 clean lines, every figure present. Slice the output — don't return the whole page and blow the tool-result limit. `browser_find` is the cheap middle ground when you only need one element's ref.

Snapshot is still right for simple/semantic pages and for getting refs to click.

## Uploading files (extension mode can't)

`browser_file_upload` fails in extension mode — `DOM.setFileInputFiles` returns `Not allowed`. Build the `File` in the page instead:

```js
() => {
  const bytes = Uint8Array.from(atob(BASE64), c => c.charCodeAt(0));
  const dt = new DataTransfer();
  dt.items.add(new File([bytes], 'x.jpg', { type: 'image/jpeg' }));
  const input = document.querySelector('input[type=file]');
  input.files = dt.files;
  input.dispatchEvent(new Event('change', { bubbles: true }));
}
```

Getting the bytes in is the hard part. Same-origin `fetch()` works only if you're testing a local dev server. For **any** origin, inline the base64 into a script file and run it with `browser_run_code_unsafe({ filename })` — the server reads that file off disk, so a 500 KB script costs nothing in context. Generate it with node rather than writing it by hand.

Three things that will bite you with `browser_run_code_unsafe`:

- **Allowed roots.** Files outside the session dir are refused. Write the script into the session root, not `/tmp`.
- **Not a module, not CommonJS.** The file must be a bare `async (page) => {...}` expression. Top-level `import`/`export` throws `Cannot use import statement outside a module`, and dynamic `import()` throws `ERR_VM_DYNAMIC_IMPORT_CALLBACK_MISSING`. **You cannot read the filesystem from inside it** — that's why the data has to be inlined.
- **Template-literal escapes.** Generating the script with a JS template literal silently eats regex escapes: `/\s*\n+/` becomes `/s*<newline>+/` and fails with `Invalid regular expression: missing /`. Use `split('\n')` instead of a regex, or double every backslash.

Return a compact string. The result is echoed with the source, so a big inlined script means a big tool result — grep the saved output file rather than reading it.

## Selectors: strict mode is a feature

Playwright refuses ambiguous locators rather than guessing:

```
strict mode violation: locator('a[href="/accounts"]') resolved to 2 elements
```

Don't reach for `.first()`. Add a distinguishing attribute — the error prints both candidates, so the fix is usually visible in it:

```js
a[data-external-id="nav-bar-link"][href="/accounts"]
```

## The extension token: literal, never a prompt

If the browser keeps demanding a fresh token, the config is using a VS Code `promptString` input. VS Code flushes those on every window reload and MCP restart, so it re-asks forever.

```jsonc
// WRONG — re-prompts on every reload
"env": { "PLAYWRIGHT_MCP_EXTENSION_TOKEN": "${input:playwright-key}" }

// RIGHT
"env": { "PLAYWRIGHT_MCP_EXTENSION_TOKEN": "<token from the extension connect page>" }
```

The token is stable per extension install (it's a pairing secret for a `127.0.0.1` websocket relay, not a credential). Set it in **every** client config — `~/.copilot/mcp-config.json` *and* `~/Library/Application Support/Code/User/mcp.json`. Fixing one leaves the other prompting. Check the target file isn't in a git repo before hardcoding.

## Artifacts leak to disk — check before browsing authed sites

Every call silently writes page snapshots and console logs to `.playwright-mcp/` **in the current working directory**. Browse an authenticated site and the page contents land in plaintext `.yml` on disk.

Before driving a browser through anything private:

```bash
git check-ignore -v .playwright-mcp/ || echo "NOT IGNORED — fix before browsing"
```

`austenstone-notes` ignores it (`.gitignore:12`). Other repos may not. Best fix is a global ignore so it can't bite anywhere:

```bash
git config --global core.excludesfile ~/.gitignore_global
echo '.playwright-mcp/' >> ~/.gitignore_global
```

Clean up sensitive artifacts when you're done, and the dir accumulates forever otherwise:

```bash
rm -f .playwright-mcp/*$(date +%Y-%m-%d)*   # today's only
```

## The two-browser trick (headless profile)

For the headless path only. Headless gets bot-walled (CAPTCHA, "unusual traffic", login walls). Two MCP servers share one persistent `--user-data-dir`: solve the challenge once in a headed window, the cookie lands in the shared profile, headless runs clean for days.

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

**Assume it's warm.** Default to headless and just run: navigate, evaluate, act, close. Don't preflight a tool check or open the headed browser "to be safe." The swap is a fallback for an actual block, not a routine step.

**The swap** — only when headless actually hits a wall. Chrome locks a profile dir to one process, so `browser_close` first or you get `Browser is already in use for <dir>`:

1. `browser_close` on headless (releases the lock).
2. `browser_navigate` headed to the same URL.
3. Solve the CAPTCHA / log in. Ask the user if needed.
4. `browser_close` headed.
5. Re-navigate headless. The cookie is now in the shared profile.

Cookies age out every few days; repeat once when challenges return. Never `--isolated`, it discards the profile every run.

**Stuck lock.** If a browser crashed or an agent bailed without `browser_close`, the orphan holds the profile:

```bash
pkill -f "user-data-dir=/path/to/profile"
```

**Cleaner alternative.** The always-on headed server is a second process that keeps colliding on the lock. Better: run only headless, and launch a one-off visible Chrome on the same profile when challenged (`open -na "Google Chrome" --args --user-data-dir=<profile> <url>`), solve, quit. See `skills/google-search/captcha.sh`.

## Related

- `~/source/austenstone-notes/docs/CHROME_DEVTOOLS_MCP.md` — `--autoConnect` setup for the DevTools server
- `skills/google-search/` — the warmed profile these servers share
