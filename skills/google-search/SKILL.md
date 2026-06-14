---
name: google-search
description: "Google web search via the Playwright MCP. Drive a headless browser to google.com, read results from the accessibility snapshot (no scraping, no selectors), and return ranked title/URL/snippet. Use for current facts, docs, releases, versions, news, prices, anything past the knowledge cutoff. Triggers: 'google search', 'web search', 'search the web', 'look it up', 'what's the latest', 'current version of X'."
---

# Google Search (Playwright MCP)

Search Google by driving the Playwright MCP yourself. There is no script and no DOM parsing. You read results straight from the accessibility snapshot, so nothing breaks when Google reshuffles its HTML.

## Steps

1. Navigate to the results page with `browser_navigate`:

   ```
   https://www.google.com/search?q=<URL-encoded query>&hl=en&gl=us&num=10
   ```

2. Capture the page with `browser_snapshot`. The snapshot is the accessibility tree: headings, links, and text. Do not use `browser_evaluate` or any JavaScript.

3. Read the organic results from the snapshot. Each result is a link whose accessible name is the page title, followed by the descriptive text below it. Pull out:
   - **title**: the link text
   - **url**: the link target
   - **snippet**: the description line under the title

4. Skip everything that is not an organic result: ads/sponsored, "People also ask", "People also search for", "Related searches", image and video carousels, and any link to a `google.com` property.

5. Return the top ~10 as a numbered list (title, URL, one-line snippet), or as JSON if the caller asked for structured data.

## Query operators

Google operators work in the `q` param: `site:`, `filetype:`, `intitle:`, `before:`/`after:`, `"exact phrase"`, `-exclude`.

## CAPTCHA / "unusual traffic"

If the page redirects to a `/sorry` interstitial or shows "Our systems have detected unusual traffic", headless got flagged. Either:

- Retry once after a short pause, or
- Switch to the headed `playwright-extension` MCP (it drives the real, logged-in Chrome and rarely gets challenged), solve any prompt, then read the snapshot.

## Why this approach

The accessibility snapshot is semantic. It reports "link: GitHub Newsroom" regardless of what CSS classes Google ships that day. No selectors to maintain, no scraper to rot.
