---
name: antigravity-cli
description: "Use when you need a second model from the terminal — current facts, web research, docs lookup, summarization, code review, or a second opinion. Triggers: 'ask gemini', 'use gemini', 'gemini search', 'use agy', 'antigravity cli', 'second opinion', 'parallel research'. Backed by Antigravity CLI (`agy`); keyless Google OAuth, no API key."
---

# Antigravity CLI (`agy`)

A second model in your terminal. Great for **web-grounded research** — `agy` is well connected to the web, so it can pull current facts, prices, releases, and docs and cite sources.

## Use it

```bash
export PATH="$HOME/.local/bin:$PATH"
agy -p "Use web search. Current GitHub Actions larger-runner pricing, cite source URLs." --dangerously-skip-permissions
```

- `-p` — one-shot, prints the answer and exits (~5-60s).
- `--dangerously-skip-permissions` — required for automated calls or `agy` hangs on a prompt.
- `--model "<name>"` — optional; list available models with `agy models`.
- Run from a neutral cwd (e.g. `/tmp`) unless file context matters.
- Be explicit about web search: say "use web search" for current facts, "do not use web search" for pure reasoning.

Independent work? Run it in parallel (subagent or background shell), and fan out multiple `agy -p` calls instead of serializing.

## Fail fast

`timeout 90 agy -p "..." --dangerously-skip-permissions`. On any error or non-zero exit, **report it and stop** — no retry loops. A `429`/quota error means the daily limit is spent and won't clear on retry.

## Setup (only if needed)

- Install: `curl -fsSL https://antigravity.google/cli/install.sh | bash`
- Sign in: run `agy` (Google OAuth, no key). If `agy models` lists models, you're already in.
