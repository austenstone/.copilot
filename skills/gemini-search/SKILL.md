---
name: gemini-search
description: "Web research grounded in live Google Search via Google's Gemini CLI. This is 'Google Search +': real-time Google results synthesized by Gemini, returned with source URLs. Use when the user wants current/real-time info: news in the last N hours, weather right now, latest software/library versions, recent releases, prices, scores, or anything past the model's knowledge cutoff. Triggers: 'gemini search', 'google search', 'search the web with gemini', 'what's the weather', 'latest news', 'current version of X', 'what happened today'. Requires the gemini CLI on PATH and GEMINI_API_KEY in env."
---

# Gemini CLI Search (Google Search +)

Grounded web research via the Gemini CLI's `google_web_search` tool. `gemini -p` runs a real Google Search, then Gemini synthesizes a cited answer. Google Search with an LLM summarizer on top.

## Prereqs

- `gemini` on PATH: `command -v gemini && gemini --version`. Install: `npm install -g @google/gemini-cli`.
- `GEMINI_API_KEY` in env: `[ -n "$GEMINI_API_KEY" ] && echo set`.

## How to call it

Preferred: the `gemini_search` Copilot tool (extension at `~/.copilot/extensions/gemini-search/extension.mjs`). Call with `query` (and optional `model`); no shell needed. If missing, run `extensions_reload` then `extensions_manage inspect gemini-search`.

Fallback (CLI / scripting):
```bash
gemini --skip-trust -m gemini-flash-latest -p "Use web search: <question>. Cite sources as URLs."
```
- `--skip-trust` required from any non-trusted dir (temp dir, CI), else "not running in a trusted directory". Or set `GEMINI_CLI_TRUST_WORKSPACE=true`.
- `-p` is one-shot mode. Calls take 10-60s; budget a 90-120s timeout.
- Filter the harmless stderr warning: `... 2>&1 | grep -v "True color"`.

## Models

Default `gemini-flash-latest` (newest Flash). Override with `-m` or the `model` param.

| Model | Use for |
|-------|---------|
| `gemini-flash-latest` | Default. Fast, cheap, grounds well. |
| `gemini-pro-latest` | Harder reasoning / many-source synthesis. |
| `gemini-2.5-flash` / `gemini-2.5-pro` | Pinned GA fallbacks. |

List what the key can call:
```bash
curl -s "https://generativelanguage.googleapis.com/v1beta/models?key=$GEMINI_API_KEY" \
  | node -e 'let d="";process.stdin.on("data",c=>d+=c).on("end",()=>JSON.parse(d).models.filter(m=>(m.supportedGenerationMethods||[]).includes("generateContent")).forEach(m=>console.log(m.name.replace("models/",""))))'
```
Off-limits: anything absent from that list, and specialized non-text models (image, TTS, robotics, computer-use).

## Diagnose a failing key

Cause is almost always tier/quota, not the CLI. No API reports tier or remaining quota; the only signal is the error from a real `generateContent` call (ListModels returns 200 regardless).
```bash
curl -s -w "\nHTTP %{http_code}\n" -X POST \
  "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key=$GEMINI_API_KEY" \
  -H 'Content-Type: application/json' -d '{"contents":[{"parts":[{"text":"ok"}]}]}'
```
200 = good. On 429, read the message:
- "exceeded its monthly spending cap" → paid key, AI Studio spend cap maxed. Raise at <https://ai.studio/spend>.
- "quota" / `RESOURCE_EXHAUSTED` without spending cap → free-tier daily limit (Flash-only). Wait for reset or enable billing.
- Pro fails but Flash works → unpaid key (free tier is Flash-only).

## Quotas & pricing

Auth is via `GEMINI_API_KEY`, so only the Gemini API key limits apply (not Code Assist / Workspace / Vertex tiers). Numbers change; never quote from memory, fetch live:
- Rate limits: <https://ai.google.dev/gemini-api/docs/rate-limits>
- Pricing: <https://ai.google.dev/gemini-api/docs/pricing>
- CLI plans: <https://geminicli.com/plans/>

Stable facts: free keys are rate-limited and Flash-only; paid keys bill per token with higher limits, so many small calls cost more than one good query. Check live session usage with `/stats model` in the interactive CLI.

## Gotchas

- Grounding URLs come back as `vertexaisearch.cloud.google.com/grounding-api-redirect/...`. Resolve the real URL: `curl -sIL -o /dev/null -w '%{url_effective}\n' "<redirect-url>"`.
- For "last N hours" / "right now", put the explicit date and time window in the query.
- When scripting, run from a neutral cwd so Gemini doesn't scan a repo or load `GEMINI.md`. The extension already does this.

## vs other search

- `gemini_search`: you want Google grounding + Gemini synthesis, or other tools fell short.
- Built-in `web_search`: fine general default, already in every session.
- Brave MCP: raw result lists, images, news, local/places.

Cross-check across them when a fact really matters.
