#!/usr/bin/env node

// Google search on a shared Chromium profile, headless by default.
//
//   node google-search.js "<query>" [--json]        headless search -> top ~10 results
//   node google-search.js "<query>" --ai [--json]   include AI Overview text + links when present
//   node google-search.js --solve [<url>]            headed window to clear a CAPTCHA
//
// The profile (./profile) is the same user-data-dir the Playwright MCP uses, so
// a CAPTCHA cleared once via --solve keeps headless runs clean for days. Results
// come from a structural selector (a:has(h3) + data-hveid), independent of
// Google's rotating CSS classes.

const path = require('path');
const fs = require('fs');
const { execSync } = require('child_process');

let chromium;
try {
  ({ chromium } = require('playwright'));
} catch {
  try {
    const root = execSync('npm root -g').toString().trim();
    ({ chromium } = require(path.join(root, 'playwright')));
  } catch {
    console.error('Playwright not found. Install it: npm i -g playwright');
    process.exit(1);
  }
}

const profile = process.env.GOOGLE_SEARCH_PROFILE || path.join(__dirname, 'profile');
const outputDir = process.env.GOOGLE_SEARCH_OUTPUT_DIR || path.join(__dirname, 'outputs');
const aiWaitMs = Number(process.env.GOOGLE_SEARCH_AI_WAIT_MS || 30000);
const maxStdoutChars = Number(process.env.GOOGLE_SEARCH_MAX_STDOUT_CHARS || 12000);
const lockHint = /lock|singleton|in use|ProcessSingleton/i;
const cleared = (u) => u.startsWith('https://') && !u.includes('/sorry');
const resultsUrl = (q) => `https://www.google.com/search?q=${encodeURIComponent(q)}&udm=14&hl=en&gl=us&num=10`;
const aiUrl = (q) => `https://www.google.com/search?q=${encodeURIComponent(q)}&hl=en&gl=us&num=10`;

const extract = () => {
  const externalUrl = (href) => {
    try {
      const u = new URL(href, location.href);
      if (/(^|\.)google\.com$/.test(u.hostname) && u.pathname === '/url' && u.searchParams.get('q')) {
        return u.searchParams.get('q');
      }
      if (!u.hostname || /(^|\.)google\.com$/.test(u.hostname)) return '';
      u.hash = '';
      return u.toString();
    } catch {
      return '';
    }
  };

  return [...document.querySelectorAll('a:has(h3)')]
  .map((a) => ({ a, url: externalUrl(a.href) }))
  .filter(({ url }) => url)
  .map((a) => {
    const c = a.a.closest('div[data-hveid]') || a.a.parentElement;
    const snip = c?.querySelector('div[data-sncf], [style*="-webkit-line-clamp"]');
    return {
      title: a.a.querySelector('h3')?.textContent.trim(),
      url: a.url,
      snippet: (snip ? snip.textContent.trim() : '').replace(/Read more$/, '').trim(),
    };
  })
  .filter((r, i, arr) => arr.findIndex((x) => x.url === r.url) === i)
  .slice(0, 10);
};

const extractAi = () => {
  const normalize = (text) => text.replace(/\s+/g, ' ').trim();
  const visibleText = (root) => {
    const clone = root.cloneNode(true);
    clone.querySelectorAll('script, style, noscript, svg').forEach((el) => el.remove());
    return normalize(clone.innerText || clone.textContent || '');
  };
  const unavailable = (text) => /An AI Overview is not available|Can't generate an AI overview/i.test(text);
  const externalUrl = (href) => {
    try {
      const u = new URL(href, location.href);
      if (/(^|\.)google\.com$/.test(u.hostname) && u.pathname === '/url' && u.searchParams.get('q')) {
        return u.searchParams.get('q');
      }
      if (!u.hostname || /(^|\.)google\.com$/.test(u.hostname)) return '';
      u.hash = '';
      return u.toString();
    } catch {
      return '';
    }
  };

  const linksFor = (root) => [...root.querySelectorAll('a[href]')]
    .map((a) => ({
      title: visibleText(a) || normalize(a.getAttribute('aria-label') || a.title || a.href),
      url: externalUrl(a.href),
    }))
    .filter((link) => link.url)
    .filter((link, i, arr) => arr.findIndex((x) => x.url === link.url) === i)
    .slice(0, 30);

  const labels = [...document.querySelectorAll('div, section, h1, h2, h3, span')]
    .filter((el) => /AI Overview|Generative AI is experimental/i.test(el.textContent || ''));

  const candidates = [];
  for (const label of labels) {
    let node = label;
    for (let depth = 0; node && depth < 10; depth += 1, node = node.parentElement) {
      const text = visibleText(node);
      if (!/AI Overview|Generative AI is experimental/i.test(text) || text.length < 80) continue;
      if (unavailable(text)) continue;
      if (text.length > 60000) continue;
      const links = linksFor(node);
      const score = (links.length * 1000) + Math.min(text.length, 8000) - (depth * 50);
      candidates.push({ node, text, links, score });
    }
  }

  candidates.sort((a, b) => b.score - a.score);
  const best = candidates[0];
  if (!best) return null;

  const text = best.text
    .replace(/^AI Overview\s*/i, '')
    .replace(/Generative AI is experimental\.?.*?Learn more/i, '')
    .replace(/Show more\s*$/i, '')
    .trim();

  return { text, links: best.links };
};

const crumb = (u) => {
  try {
    const { hostname, pathname } = new URL(u);
    return [hostname, ...pathname.split('/').filter(Boolean)].join(' › ');
  } catch { return u; }
};

const format = (results) => results
  .map((r) => `**[${r.title}](${r.url})**\n\`${crumb(r.url)}\`${r.snippet ? `\n${r.snippet}` : ''}`)
  .join('\n\n');

const formatAi = ({ ai, results }) => {
  const parts = [];
  if (ai?.text) {
    parts.push(`# AI response\n\n${ai.text}`);
    if (ai.links.length) {
      parts.push(`## AI links\n\n${ai.links.map((link) => `- [${link.title || crumb(link.url)}](${link.url})`).join('\n')}`);
    }
  } else {
    parts.push('No AI Overview parsed. Google may not have shown one for this query.');
  }
  if (results.length) parts.push(`## Search results\n\n${format(results)}`);
  return parts.join('\n\n');
};

const slug = (query) => query.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 60) || 'query';

const spillIfLarge = (output, payload, query, json) => {
  if (output.length <= maxStdoutChars) return output;

  fs.mkdirSync(outputDir, { recursive: true });
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const file = path.join(outputDir, `${stamp}-${slug(query)}.${json ? 'json' : 'md'}`);
  fs.writeFileSync(file, output);

  if (json) {
    return JSON.stringify({
      query,
      truncated: true,
      file,
      ai: payload.ai ? {
        text: `${payload.ai.text.slice(0, 1200)}${payload.ai.text.length > 1200 ? '...' : ''}`,
        links: payload.ai.links,
      } : null,
      results: payload.results,
    }, null, 2);
  }

  const lines = [
    `Full response written to ${file}`,
    '',
  ];
  if (payload.ai?.text) lines.push(payload.ai.text.slice(0, 1800), '');
  if (payload.ai?.links.length) lines.push('AI links:', ...payload.ai.links.map((link) => `- ${link.title || crumb(link.url)}: ${link.url}`), '');
  if (payload.results.length) lines.push('Search result links:', ...payload.results.map((r) => `- ${r.title}: ${r.url}`));
  return lines.join('\n').trim();
};

async function search(query, options) {
  const { json, ai: includeAi } = options;
  let context;
  try {
    context = await chromium.launchPersistentContext(profile, {
      headless: true,
      args: ['--no-first-run', '--no-default-browser-check'],
    });
  } catch (err) {
    if (lockHint.test(err.message)) {
      console.error('Profile is locked by another browser. Close the MCP browser or the --solve window, then retry.');
      process.exit(1);
    }
    throw err;
  }

  try {
    const page = context.pages()[0] || await context.newPage();
    await page.goto(includeAi ? aiUrl(query) : resultsUrl(query), { waitUntil: 'domcontentloaded' });

    if (page.url().includes('/sorry')) {
      console.error(`CAPTCHA wall. Clear it once: node "${__filename}" --solve`);
      process.exitCode = 2;
      return;
    }

    let ai = null;
    if (includeAi) {
      await page.waitForFunction(extractAi, null, { timeout: aiWaitMs }).catch(() => {});
      ai = await page.evaluate(extractAi);
    }

    const results = await page.evaluate(extract);
    if (!results.length && !ai) {
      console.error('No results parsed. Google may have changed shape or served a CAPTCHA.');
      process.exitCode = 3;
      return;
    }

    const payload = includeAi ? { query, ai, results } : results;
    const output = json ? JSON.stringify(payload, null, 2) : includeAi ? formatAi(payload) : format(results);
    console.log(includeAi ? spillIfLarge(output, payload, query, json) : output);
  } finally {
    await context.close().catch(() => {});
  }
}

async function solve(url) {
  let context;
  // Prefer a real installed browser (human fingerprint); fall back to bundled.
  for (const channel of ['chrome', 'msedge', 'chromium', undefined]) {
    try {
      context = await chromium.launchPersistentContext(profile, {
        headless: false,
        viewport: null,
        channel,
        args: ['--no-first-run', '--no-default-browser-check'],
      });
      break;
    } catch (err) {
      if (lockHint.test(err.message)) {
        console.error('Profile is locked by another browser. Close the headless search or the MCP browser first, then retry.');
        process.exit(1);
      }
      if (channel === undefined) throw err;
    }
  }

  const page = context.pages()[0] || await context.newPage();

  let closing = false;
  let solved = false;
  const savedMsg = 'Closed. Cookie saved — retry your headless search.';
  const finish = async (msg) => {
    if (closing) return;
    closing = true;
    clearInterval(timer);
    console.log(msg);
    await context.close().catch(() => {});
    process.exitCode = 0;
  };

  // Poll every tab once a second: the authoritative, event-miss-proof signal.
  const timer = setInterval(() => {
    for (const p of context.pages()) {
      let u = '';
      try { u = p.url(); } catch { continue; }
      if (cleared(u)) { solved = true; return finish(savedMsg); }
    }
  }, 1000);

  context.on('close', () => finish(solved ? savedMsg : 'Window closed. Retry your headless search.'));

  console.log('Opening a browser — solve the CAPTCHA and it closes automatically.');
  await page.goto(url, { waitUntil: 'domcontentloaded' }).catch(() => {});
  if (cleared(page.url())) finish(savedMsg);
}

const usage = `google-search.js — Google search on a shared Chromium profile (headless by default).

  node google-search.js "<query>"          Search, print top ~10 as markdown (title, breadcrumb, snippet)
  node google-search.js "<query>" --json   Same, raw JSON
  node google-search.js "<query>" --ai     Include Google AI Overview text and its citation links when shown
  node google-search.js --solve [<url>]    Open a headed window to clear a CAPTCHA, then auto-close

AI mode waits up to GOOGLE_SEARCH_AI_WAIT_MS, default 30000, because AI Overviews often render late.
If the AI payload would exceed GOOGLE_SEARCH_MAX_STDOUT_CHARS, default 12000, the full response is
written to GOOGLE_SEARCH_OUTPUT_DIR or ./outputs and stdout keeps the file path plus navigable links.

How it works: results come from a structural selector (a:has(h3) + data-hveid) that
survives Google's CSS churn. The ./profile dir is the same user-data-dir the Playwright
MCP uses, so a CAPTCHA cleared once with --solve keeps headless runs clean for days.
Only one browser can hold the profile at a time — close the MCP browser before --solve.

Exit codes: 0 ok · 2 CAPTCHA wall (run --solve) · 3 no results parsed · 1 error/lock.`;

(async () => {
  const args = process.argv.slice(2);
  if (args[0] === '--solve') {
    const url = args[1] || resultsUrl('are you human');
    await solve(url);
    return;
  }

  const json = args.includes('--json');
  const ai = args.includes('--ai');
  const query = args.filter((a) => a !== '--json' && a !== '--ai').join(' ').trim();
  if (!query || args.includes('--help') || args.includes('-h')) {
    console.error(usage);
    process.exit(query ? 0 : 1);
  }
  await search(query, { json, ai });
})().catch((err) => {
  console.error(err.message);
  process.exit(1);
});
