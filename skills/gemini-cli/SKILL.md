---
name: gemini-cli
description: "Use when: running Google's Gemini CLI, asking Gemini for a second opinion, using Gemini for parallel research, web-grounded current facts, docs lookup, summarization, code review, long-context synthesis, or general-purpose reasoning. Triggers: 'gemini cli', 'ask gemini', 'use gemini', 'run gemini', 'gemini search', 'google search with gemini', 'second opinion', 'parallel research'. Prefer running it in parallel or in a subagent when the work is independent. Requires the gemini CLI on PATH and GEMINI_API_KEY in env."
---

# Gemini CLI

General-purpose Gemini CLI access from Copilot. Use it for web-grounded research, second-opinion reasoning, docs lookup, summarization, code review, and synthesis that can run independently from the main task.

## Default pattern

Prefer the `gemini_cli` Copilot tool if available. It shells out to `gemini -p` from a neutral directory and returns Gemini's answer.

Use it like this:

- `prompt`: the full task for Gemini
- `model`: optional, defaults to `gemini-flash-latest`
- `cwd`: optional, only when Gemini should see files from a specific directory
- `timeoutSeconds`: optional, defaults to 120

When the work is independent, run Gemini in parallel with your local work:

- Launch a subagent whose only job is to ask Gemini CLI and summarize the result back.
- For shell fallback, run the command in the background with `run_in_terminal` async mode if you can keep working while it runs.
- For multiple independent questions, start multiple Gemini CLI calls in parallel rather than serializing them.

## Good prompts

Be explicit about whether Gemini should use web search.

```text
Use web search. Find the current GitHub Actions larger runner pricing and cite source URLs. Return only the key numbers and links.
```

```text
Review this API design for edge cases. Do not use web search. Focus on failure modes and simpler alternatives.
```

```text
Use web search if helpful. Compare the latest stable versions of Vite, Vitest, and Playwright. Include source URLs.
```

## Shell fallback

```bash
gemini --skip-trust -m gemini-flash-latest -p "<task>"
```

- `--skip-trust` is required from non-trusted dirs, temp dirs, and CI. Or set `GEMINI_CLI_TRUST_WORKSPACE=true`.
- `-p` is one-shot mode. Calls usually take 10-60s. Use a 90-180s timeout.
- Filter the harmless stderr warning: `... 2>&1 | grep -v "True color"`.
- Run from a neutral cwd unless file context matters, so Gemini does not scan a repo or load `GEMINI.md` unintentionally.

## Models

Default: `gemini-flash-latest`.

| Model | Use for |
|-------|---------|
| `gemini-flash-latest` | Default. Fast, cheap, good for search, summaries, and second opinions. |
| `gemini-pro-latest` | Harder reasoning and larger synthesis jobs. |
| `gemini-2.5-flash` / `gemini-2.5-pro` | Pinned GA fallbacks. |

List what the key can call:

```bash
curl -s "https://generativelanguage.googleapis.com/v1beta/models?key=$GEMINI_API_KEY" \
  | node -e 'let d="";process.stdin.on("data",c=>d+=c).on("end",()=>JSON.parse(d).models.filter(m=>(m.supportedGenerationMethods||[]).includes("generateContent")).forEach(m=>console.log(m.name.replace("models/",""))))'
```

Specialized non-text models, image generation, TTS, robotics, and computer-use are outside this skill. Use the dedicated Gemini image/video skills for those.

## Diagnose a failing key

Cause is usually tier or quota, not the CLI. No API reports tier or remaining quota. The only useful signal is the error from a real `generateContent` call.

```bash
curl -s -w "\nHTTP %{http_code}\n" -X POST \
  "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key=$GEMINI_API_KEY" \
  -H 'Content-Type: application/json' -d '{"contents":[{"parts":[{"text":"ok"}]}]}'
```

200 = good. On 429, read the message:

- "exceeded its monthly spending cap" means a paid key hit the AI Studio spend cap. Raise it at <https://ai.studio/spend>.
- "quota" or `RESOURCE_EXHAUSTED` without spending-cap language usually means free-tier daily limit. Wait for reset or enable billing.
- Pro fails but Flash works usually means the key is unpaid, since free tier is Flash-only.

## Quotas and pricing

Auth is via `GEMINI_API_KEY`, so Gemini API limits apply, not Code Assist, Workspace, or Vertex tiers. Numbers change, so fetch live:

- Rate limits: <https://ai.google.dev/gemini-api/docs/rate-limits>
- Pricing: <https://ai.google.dev/gemini-api/docs/pricing>
- CLI plans: <https://geminicli.com/plans/>

Stable facts: free keys are rate-limited and Flash-only. Paid keys bill per token with higher limits. Many small calls cost more than one well-scoped prompt. Check live session usage with `/stats model` in the interactive CLI.

## Gotchas

- For current facts, tell Gemini to use web search and include the date or time window.
- Grounding URLs may come back as `vertexaisearch.cloud.google.com/grounding-api-redirect/...`. Resolve the real URL with `curl -sIL -o /dev/null -w '%{url_effective}\n' "<redirect-url>"`.
- If the answer matters, cross-check with another search tool or source.
- Keep prompts bounded. One good, specific prompt beats five vague ones.

## vs other tools

- `gemini_cli`: Gemini as a general-purpose peer agent, especially useful for parallel research, second opinions, current facts, and long synthesis.
- Built-in `web_search`: fastest default for simple current facts.
- Google Search skill: raw Google SERP links and snippets when you need source discovery, not synthesis.
- Brave MCP: raw result lists, images, news, local, and places.