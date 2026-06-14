#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const { performance } = require('perf_hooks');

const PROFILE = process.env.GOOGLE_SEARCH_PROFILE || path.join(__dirname, 'profile');
const OUTPUT_DIR = process.env.GOOGLE_SEARCH_OUTPUT_DIR || path.join(__dirname, 'outputs');
const MAX_STDOUT_CHARS = Number(process.env.GOOGLE_SEARCH_MAX_STDOUT_CHARS || 12000);
const LOCK_HINT = /lock|singleton|in use|ProcessSingleton/i;

const SERP_SECTIONS = [
  { key: 'ads', title: 'Sponsored results', match: /^Sponsored results$/i, mode: 'cards' },
  { key: 'aiOverview', title: 'AI Overview', match: /^AI Overview$/i, mode: 'ai' },
  { key: 'webResults', title: 'Web results', match: /^Web results$/i, mode: 'cards' },
  { key: 'forums', title: 'Discussions and forums', match: /^Discussions and forums$/i, mode: 'cards' },
  { key: 'videos', title: 'Videos', match: /^Videos$/i, mode: 'cards' },
  { key: 'whatPeopleAreSaying', title: 'What people are saying', match: /^What people are saying$/i, mode: 'cards' },
  { key: 'peopleAlsoAsk', title: 'People also ask', match: /^People also ask$/i, mode: 'chips' },
  { key: 'peopleAlsoSearch', title: 'People also search for', match: /^People also search for$/i, mode: 'chips' },
];

const SEARCH_FLAGS = new Set(['--json', '--raw', '--html', '--dom', '--bench']);

function loadPlaywright() {
  try {
    return require('playwright').chromium;
  } catch {
    try {
      const root = execSync('npm root -g').toString().trim();
      return require(path.join(root, 'playwright')).chromium;
    } catch {
      console.error('Playwright not found. Install it: npm i -g playwright');
      process.exit(1);
    }
  }
}

const chromium = loadPlaywright();

function searchUrl(query) {
  return `https://www.google.com/search?q=${encodeURIComponent(query)}&hl=en&gl=us&num=10`;
}

function captchaCleared(url) {
  return url.startsWith('https://') && !url.includes('/sorry');
}

function normalize(text) {
  return (text || '').replace(/\s+/g, ' ').trim();
}

function cleanTitle(title) {
  return normalize(title)
    .replace(/\s*(YouTube|Reddit|Quora)\s*·.*$/i, '')
    .replace(/\s*(\d+(\.\d+)?K\+? views|\d+ views)\s*·.*$/i, '')
    .trim();
}

function markdownLink(title, url) {
  const safeTitle = cleanTitle(title || url).replace(/\[/g, '\\[').replace(/\]/g, '\\]');
  return `[${safeTitle}](${url})`;
}

function codeLike(text) {
  return /^\(?function\b|^(var|const|let)\s|trustedTypes|createPolicy|google\.kEI|nonce|\.querySelector\?/i.test(normalize(text));
}

function isExternalUrl(url) {
  try {
    const parsed = new URL(url);
    return !/(^|\.)google\.com$/.test(parsed.hostname);
  } catch {
    return false;
  }
}

function slug(query) {
  return query.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 60) || 'query';
}

function launchContext(headless) {
  return chromium.launchPersistentContext(PROFILE, {
    headless,
    viewport: headless ? undefined : null,
    args: ['--no-first-run', '--no-default-browser-check'],
  });
}

async function withContext(headless, fn) {
  let context;
  try {
    context = await launchContext(headless);
  } catch (err) {
    if (LOCK_HINT.test(err.message)) {
      console.error('Profile is locked by another browser. Close the MCP browser or solve window, then retry.');
      process.exit(1);
    }
    throw err;
  }

  try {
    return await fn(context);
  } finally {
    await context.close().catch(() => {});
  }
}

function extractText() {
  return document.body?.innerText || '';
}

function extractHtml() {
  return document.documentElement?.outerHTML || '';
}

function extractDom() {
  const normalize = (text) => (text || '').replace(/\s+/g, ' ').trim();
  const cleanTitle = (title) => normalize(title)
    .replace(/\s*(YouTube|Reddit|Quora)\s*·.*$/i, '')
    .replace(/\s*(\d+(\.\d+)?K\+? views|\d+ views)\s*·.*$/i, '')
    .trim();

  const externalUrl = (href) => {
    try {
      const url = new URL(href, location.href);
      if (/(^|\.)google\.com$/.test(url.hostname) && url.pathname === '/url' && url.searchParams.get('q')) {
        return url.searchParams.get('q');
      }
      if (!url.hostname || /(^|\.)google\.com$/.test(url.hostname)) return '';
      url.hash = '';
      return url.toString();
    } catch {
      return '';
    }
  };

  const titleFor = (el) => {
    const heading = el.querySelector('h3')?.textContent;
    if (heading) return normalize(heading);

    const text = normalize(el.textContent);
    const host = (() => {
      try {
        return new URL(el.href).hostname.replace(/^www\./, '');
      } catch {
        return '';
      }
    })();

    if (host && text.includes(host)) return normalize(text.slice(0, text.indexOf(host)));
    if (text.includes('http')) return normalize(text.slice(0, text.indexOf('http')));
    return cleanTitle(text.slice(0, 160));
  };

  const snippetFor = (el) => {
    const card = el.closest('div[data-hveid]');
    const snippet = card?.querySelector('div[data-sncf], [style*="-webkit-line-clamp"]')?.textContent;
    return normalize(snippet).replace(/Read more$/i, '').trim();
  };

  return [...document.querySelectorAll('div[data-hveid], a[href], div[role="heading"], div[data-sncf]')]
    .slice(0, 500)
    .map((el) => {
      const isLink = el.tagName.toLowerCase() === 'a';
      return {
        tag: el.tagName.toLowerCase(),
        title: isLink ? cleanTitle(titleFor(el)) : '',
        text: normalize(el.textContent).slice(0, 400),
        href: isLink ? externalUrl(el.getAttribute('href') || '') : '',
        snippet: snippetFor(el).slice(0, 400),
        role: el.getAttribute('role') || '',
        hveid: el.getAttribute('data-hveid') || '',
        aria: normalize(el.getAttribute('aria-label') || ''),
        classes: normalize(el.className || ''),
      };
    })
    .filter((node) => node.text || node.href || node.hveid || node.role || node.aria);
}

function extractAiOverview() {
  const normalize = (text) => (text || '').replace(/\s+/g, ' ').trim();
  const codeLike = (text) => /^\(?function\b|^(var|const|let)\s|trustedTypes|createPolicy|google\.kEI|nonce|\.querySelector\?/i.test(normalize(text));

  const externalUrl = (href) => {
    try {
      const url = new URL(href, location.href);
      if (/(^|\.)google\.com$/.test(url.hostname) && url.pathname === '/url' && url.searchParams.get('q')) {
        return url.searchParams.get('q');
      }
      if (!url.hostname || /(^|\.)google\.com$/.test(url.hostname)) return '';
      url.hash = '';
      return url.toString();
    } catch {
      return '';
    }
  };

  const visibleText = (root) => {
    const clone = root.cloneNode(true);
    clone.querySelectorAll('script, style, noscript, svg').forEach((el) => el.remove());
    return normalize(clone.innerText || clone.textContent || '');
  };

  const linksFor = (root) => [...root.querySelectorAll('a[href]')]
    .map((link) => ({ title: visibleText(link) || normalize(link.getAttribute('aria-label') || link.title || link.href), url: externalUrl(link.href) }))
    .filter((link) => link.url)
    .filter((link, index, links) => links.findIndex((entry) => entry.url === link.url) === index)
    .slice(0, 20);

  const labels = [...document.querySelectorAll('div, section, h1, h2, h3, span')]
    .filter((el) => /AI Overview|Generative AI is experimental/i.test(el.textContent || ''));

  const candidates = [];
  for (const label of labels) {
    let node = label;
    for (let depth = 0; node && depth < 8; depth += 1, node = node.parentElement) {
      const text = visibleText(node);
      if (!/AI Overview|Generative AI is experimental/i.test(text)) continue;
      if (/An AI Overview is not available|Can't generate an AI overview/i.test(text)) continue;
      if (text.length < 80 || text.length > 12000 || codeLike(text)) continue;
      candidates.push({ text, links: linksFor(node), score: text.length - depth * 100 });
    }
  }

  candidates.sort((a, b) => b.score - a.score);
  const best = candidates[0];
  if (!best) return null;

  return {
    text: best.text
      .replace(/^AI Overview\s*/i, '')
      .replace(/Generative AI is experimental\.?.*?Learn more/i, '')
      .replace(/Show more\s*$/i, '')
      .trim(),
    links: best.links,
  };
}

function sectionFor(node) {
  if (node.role === 'listitem') return null;

  const text = normalize(node.text);
  return SERP_SECTIONS.find((section) => {
    if (section.match.test(text) && node.role === 'heading') return true;
    return text.startsWith(section.title) && text.length > section.title.length + 20;
  }) || null;
}

function sectionHeadings(nodes) {
  return nodes
    .map((node, index) => ({ node, index, section: sectionFor(node) }))
    .filter((entry) => entry.section)
    .filter((entry, index, entries) => {
      const previous = entries[index - 1];
      return !previous || previous.index !== entry.index - 1 || previous.section.key !== entry.section.key;
    });
}

function rejectedTitle(title) {
  if (!title) return true;
  if (/^(cached|similar|more results|translate this page|more|\d+ answers)$/i.test(title)) return true;
  if (/^(From )?\d{2}:\d{2}|^\d+ key moments/i.test(title)) return true;
  return false;
}

function collectCards(nodes, usedUrls) {
  const cards = [];
  const seen = new Set();

  for (let index = 0; index < nodes.length; index += 1) {
    const node = nodes[index];
    if (!isExternalUrl(node.href) || seen.has(node.href)) continue;

    const title = cleanTitle(node.title || node.aria || node.text.split('https://')[0].trim() || node.text);
    if (rejectedTitle(title)) continue;

    const nearbySnippet = nodes.slice(Math.max(0, index - 2), index + 1)
      .map((entry) => entry.text)
      .find((text) => text && !codeLike(text) && text.length > title.length + 20 && !normalize(text).startsWith(title));

    const snippetSource = node.snippet || nearbySnippet || '';
    const snippet = snippetSource && snippetSource !== title ? snippetSource.replace(title, '').trim() : '';

    cards.push({ title, url: node.href, snippet });
    seen.add(node.href);
    usedUrls.add(node.href);
  }

  return cards;
}

function collectChips(nodes) {
  const chips = [];
  const seen = new Set();

  for (const node of nodes) {
    if (/Page Navigation|Footer Links|Results are personalized/i.test(node.text)) break;

    const text = normalize(node.text || node.title || node.aria);
    if (!text || text.length > 120) continue;
    if (/^\d+$|^Next$|^Help$|^Send feedback$|^Privacy$|^Terms$/i.test(text)) continue;
    if (/An error has occurred/i.test(text)) continue;
    if (SERP_SECTIONS.some((section) => section.match.test(text))) continue;
    if (node.href && isExternalUrl(node.href)) continue;
    if (seen.has(text)) continue;

    chips.push(text);
    seen.add(text);
  }

  return chips;
}

function findAiOverview(nodes, ai, usedUrls) {
  if (ai?.text && !codeLike(ai.text)) return ai;

  const headings = sectionHeadings(nodes);
  const headingIndex = headings.findIndex((entry) => entry.section.key === 'aiOverview');
  if (headingIndex === -1) return null;

  const heading = headings[headingIndex];
  const nextIndex = headings[headingIndex + 1]?.index || nodes.length;
  const slice = nodes.slice(heading.index, nextIndex);
  const text = slice
    .map((node) => normalize(node.text))
    .find((entry) => entry.length > 80 && !/^AI Overview$/i.test(entry) && !codeLike(entry));

  if (!text) return null;

  return {
    text: text.replace(/^AI Overview\s*/i, '').trim(),
    links: collectCards(slice, usedUrls).slice(0, 6),
  };
}

function buildSerp(nodes, ai) {
  const headings = sectionHeadings(nodes);
  const sections = [];
  const usedUrls = new Set();
  const aiOverview = findAiOverview(nodes, ai, usedUrls);

  for (let index = 0; index < headings.length; index += 1) {
    const { node, section } = headings[index];
    if (section.key === 'aiOverview') continue;

    const nextIndex = headings[index + 1]?.index || nodes.length;
    const inlineContainer = normalize(node.text).length > section.title.length + 20 ? [node] : [];
    const slice = [...inlineContainer, ...nodes.slice(headings[index].index + 1, nextIndex)];
    const bucket = sections.find((entry) => entry.key === section.key) || { key: section.key, title: section.title, items: [], chips: [] };

    if (!sections.includes(bucket)) sections.push(bucket);

    if (section.mode === 'chips') {
      bucket.chips.push(...collectChips(slice));
    } else {
      bucket.items.push(...collectCards(slice, usedUrls));
    }
  }

  const organic = nodes
    .filter((node) => isExternalUrl(node.href) && !usedUrls.has(node.href) && !rejectedTitle(node.title))
    .map((node) => ({ title: cleanTitle(node.title), url: node.href, snippet: node.snippet || '' }))
    .filter((item, index, items) => items.findIndex((entry) => entry.url === item.url) === index);

  return { ai: aiOverview, sections, organic };
}

function formatCards(cards) {
  return cards
    .map((card) => [
      `- ${markdownLink(card.title, card.url)}`,
      card.snippet ? `  ${card.snippet}` : null,
    ].filter(Boolean).join('\n'))
    .join('\n\n');
}

function formatSerp({ ai, sections, organic }) {
  const parts = [];

  if (ai?.text) {
    parts.push(`# AI Overview\n\n${ai.text}`);
    if (ai.links?.length) parts.push(`## AI links\n\n${formatCards(ai.links)}`);
  }

  for (const section of sections) {
    if (section.items.length) parts.push(`# ${section.title}\n\n${formatCards(section.items)}`);
    if (section.chips.length) parts.push(`# ${section.title}\n\n${section.chips.map((chip) => `- ${chip}`).join('\n')}`);
  }

  if (organic.length) parts.push(`# Other results\n\n${formatCards(organic)}`);

  return parts.join('\n\n');
}

function payloadSummary(payload) {
  return {
    query: payload.query,
    truncated: true,
    file: payload.file,
    ai: payload.ai ? { text: payload.ai.text.slice(0, 1200), links: payload.ai.links || [] } : null,
    sections: payload.sections.map((section) => ({
      key: section.key,
      title: section.title,
      items: section.items.slice(0, 10),
      chips: section.chips.slice(0, 20),
    })),
    organic: payload.organic.slice(0, 10),
  };
}

function spillIfLarge(output, payload, query, json) {
  if (output.length <= MAX_STDOUT_CHARS) return output;

  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const file = path.join(OUTPUT_DIR, `${stamp}-${slug(query)}.${json ? 'json' : 'md'}`);
  fs.writeFileSync(file, output);

  const summary = payloadSummary({ ...payload, file });
  if (json) return JSON.stringify(summary, null, 2);

  return [
    `Full response written to ${file}`,
    '',
    formatSerp(summary),
  ].join('\n').trim();
}

async function navigate(page, query) {
  const started = performance.now();
  await page.goto(searchUrl(query), { waitUntil: 'domcontentloaded' });
  return performance.now() - started;
}

async function search(query, options) {
  const started = performance.now();

  for (let attempt = 0; attempt <= 1; attempt++) {
    let captchaUrl = null;

    await withContext(true, async (context) => {
      const page = context.pages()[0] || await context.newPage();
      const gotoMs = await navigate(page, query);

      if (page.url().includes('/sorry')) {
        captchaUrl = page.url();
        return;
      }

      if (options.raw) return console.log(await page.evaluate(extractText));
      if (options.html) return console.log(await page.evaluate(extractHtml));
      if (options.dom) return console.log(JSON.stringify(await page.evaluate(extractDom), null, 2));

      const extractStarted = performance.now();
      const [ai, nodes] = await Promise.all([
        page.evaluate(extractAiOverview).catch(() => null),
        page.evaluate(extractDom),
      ]);
      const parsed = buildSerp(nodes, ai);
      const extractMs = performance.now() - extractStarted;

      if (!parsed.ai && !parsed.sections.length && !parsed.organic.length) {
        console.error('No results parsed. Google may have changed shape or served a CAPTCHA.');
        process.exitCode = 3;
        return;
      }

      const payload = { query, ...parsed };
      const output = options.json ? JSON.stringify(payload, null, 2) : formatSerp(parsed);

      if (options.bench) {
        console.error(JSON.stringify({
          query,
          gotoMs: Math.round(gotoMs),
          extractMs: Math.round(extractMs),
          totalMs: Math.round(performance.now() - started),
          sections: parsed.sections.length,
          organic: parsed.organic.length,
        }, null, 2));
      }

      console.log(spillIfLarge(output, payload, query, options.json));
    });

    if (!captchaUrl) break;

    if (attempt === 0) {
      console.error('CAPTCHA detected. Opening a browser — solve it and the search will retry automatically.');
      await solve(captchaUrl);
    } else {
      console.error('CAPTCHA still showing after solve. Run with --solve to try again manually.');
      process.exitCode = 2;
    }
  }
}

async function solve(url) {
  for (const channel of ['chrome', 'msedge', 'chromium', undefined]) {
    try {
      const context = await chromium.launchPersistentContext(PROFILE, {
        headless: false,
        viewport: null,
        channel,
        args: ['--no-first-run', '--no-default-browser-check'],
      });

      const page = context.pages()[0] || await context.newPage();
      let closing = false;
      let solved = false;

      await new Promise((resolve) => {
        const finish = async (msg) => {
          if (closing) return;
          closing = true;
          clearInterval(timer);
          if (msg) console.error(msg);
          await context.close().catch(() => {});
          resolve();
        };

        const timer = setInterval(() => {
          for (const tab of context.pages()) {
            try {
              if (captchaCleared(tab.url())) {
                solved = true;
                finish('Closed. Cookie saved.');
                return;
              }
            } catch {}
          }
        }, 1000);

        context.on('close', () => finish(solved ? '' : 'Window closed without solving.'));
        console.error('Opening a browser. Solve the CAPTCHA and it will close automatically.');
        page.goto(url, { waitUntil: 'domcontentloaded' }).then(() => {
          if (captchaCleared(page.url())) finish('Closed. Cookie saved.');
        }).catch(() => {});
      });

      return;
    } catch (err) {
      if (LOCK_HINT.test(err.message)) {
        console.error('Profile is locked by another browser. Close the MCP browser or solve window, then retry.');
        process.exit(1);
      }
      if (channel === undefined) throw err;
    }
  }
}

function parseArgs(args) {
  if (args[0] === '--solve') return { solve: true, url: args[1] || searchUrl('are you human') };

  const options = {
    json: args.includes('--json'),
    raw: args.includes('--raw'),
    html: args.includes('--html'),
    dom: args.includes('--dom'),
    bench: args.includes('--bench'),
  };

  return {
    ...options,
    help: args.includes('--help') || args.includes('-h'),
    query: args.filter((arg) => !SEARCH_FLAGS.has(arg) && arg !== '--help' && arg !== '-h').join(' ').trim(),
  };
}

const usage = `google-search.js: Google search on a shared Chromium profile.

  node google-search.js "<query>"          Structured SERP breakdown
  node google-search.js "<query>" --json   Structured JSON
  node google-search.js "<query>" --raw    Rendered page text
  node google-search.js "<query>" --dom    Compact DOM outline
  node google-search.js "<query>" --html   Full HTML
  node google-search.js "<query>" --bench  Timing data on stderr
  node google-search.js --solve [<url>]    Open a browser to clear CAPTCHA

Default output groups what Google exposes: AI Overview, sponsored results, web results, forums, videos, people also ask, related searches, and other links.

Environment:
  GOOGLE_SEARCH_PROFILE        Chromium profile directory
  GOOGLE_SEARCH_OUTPUT_DIR     Spill directory for large output
  GOOGLE_SEARCH_MAX_STDOUT_CHARS  Max stdout before spill, default 12000

Exit codes: 0 ok, 1 error or profile lock, 2 CAPTCHA, 3 no parsed results.`;

(async () => {
  const parsed = parseArgs(process.argv.slice(2));

  if (parsed.solve) {
    await solve(parsed.url);
    return;
  }

  if (parsed.help || !parsed.query) {
    console.error(usage);
    process.exit(parsed.query ? 0 : 1);
  }

  await search(parsed.query, parsed);
})().catch((err) => {
  console.error(err.message);
  process.exit(1);
});
