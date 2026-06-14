---
name: extension-authoring
description: "Reference map for building Copilot CLI extensions and canvases. Use when an agent needs to create, scaffold, debug, or share an extension (tools, hooks, or a canvas side-panel) — points to the canonical SDK docs/types, working example extensions, the right tooling, and the hard rules that trip people up. Triggers: 'create an extension', 'build a canvas', 'scaffold an extension', 'extension.mjs', 'joinSession', 'createCanvas', 'how do extensions work'."
---

# Copilot CLI Extension Authoring — Reference Map

Use this when building, scaffolding, debugging, or sharing a Copilot CLI extension — whether it contributes tools/hooks or a canvas side-panel. This skill is a pointer map: it tells you *where the real docs, types, and working examples live* so you don't reinvent boilerplate or guess at the API.

## Read order

1. **Tooling first.** Call `extensions_manage({ operation: "guide" })` — it prints absolute paths to the SDK docs that ship with the installed app. Then scaffold with `extensions_manage({ operation: "scaffold", kind: "canvas" | "basic", name, location })`. Don't hand-write the skeleton.
2. **Docs.** Read `extensions.md` first (architecture/lifecycle), then `agent-author.md` (signatures/workflow). Hit `examples.md` when stuck.
3. **Types.** `canvas.d.ts` / `index.d.ts` are the source of truth for exact field names and signatures — view them directly.
4. **Steal from a working example** (see table below) instead of writing from scratch.
5. **`extensions_reload`** after every edit, then `extensions_manage({ operation: "inspect", name })` to read the log tail if anything fails.

## SDK docs & types (canonical source of truth)

Installed app path: `/Applications/GitHub Copilot.app/Contents/Resources/copilot-sdk/`

| File | Covers |
|------|--------|
| `docs/extensions.md` | Architecture, discovery rules, lifecycle — **read first** |
| `docs/agent-author.md` | Step-by-step workflow, full tool/hook/session/event signatures, gotchas |
| `docs/examples.md` | Recipes: tools, hooks, events, lifecycle, file watching, `session.send` |
| `index.d.ts` | Top-level type entry point |
| `canvas.d.ts` | Canvas types (`createCanvas`, `CanvasError`, contexts) — must-read for canvas work |
| `extension.d.ts`, `session.d.ts`, `types.d.ts`, `generated/` | Tool/hook/session/event types, system-message config |

The exact path can shift with app version — always run `extensions_manage({ operation: "guide" })` to get current absolute paths rather than hardcoding them.

## Working examples (best "show me one that works" references)

Project scope (`<repo>/.github/extensions/`), e.g. in `~/source/github-app`:

| Example | Why look at it |
|---------|----------------|
| `triage-board/` | Full-featured GitHub App canvas: loopback HTTP server + `index.html` + actions + SSE. Gold standard for a non-trivial canvas. |
| `canvas-counter/` | Minimal canvas + `README.md`. Best starting skeleton. |
| `canvas-test-bench/` | Exercises the *entire* surface: open input, actions, errors, artifacts, tools, commands, hooks, `send`/`getEvents`, UI elicitation. Best "what's possible" reference. |

User scope (`~/.copilot/extensions/`):

| Example | Why look at it |
|---------|----------------|
| `highcharts-canvas/` | Canvas with a durable `state/` dir — state-model example. |
| `gemini-search/` | Tools-only extension (no canvas), single `extension.mjs`. |

## Tooling (use it; don't hand-roll)

- `extensions_manage({ operation: "guide" })` — current SDK doc paths
- `extensions_manage({ operation: "scaffold", kind: "canvas" | "basic", name, location: "project" | "user" })` — correct boilerplate
- `extensions_manage({ operation: "list" })` — loaded? marked `failed`?
- `extensions_manage({ operation: "inspect", name })` — log file path + **tail** (primary debug surface)
- `extensions_reload` — restart providers after edits
- `share_extension` / `install_extension` — gist round-trip

## Hard rules (the stuff that trips people up)

- Entry file **must** be `extension.mjs` — ESM only, no `.ts`. Lives in an immediate subdir of `.github/extensions/` (project) or `~/.copilot/extensions/` (user).
- **Never `console.log`** — `stdout` is reserved for JSON-RPC and a stray log corrupts the protocol. Use `session.log(msg, { level, ephemeral })`.
- Don't add a `package.json`/`node_modules` for `@github/copilot-sdk` — it's auto-resolved by the CLI.
- Canvas embedded servers bind to **loopback only** (`127.0.0.1:0`); the host only embeds loopback URLs.
- Tool names must be **globally unique** across all loaded extensions, or the second one fails to load.
- A project `.github/extensions/<name>/` **shadows** a user `~/.copilot/extensions/<name>/` of the same name at discovery.

## Canvas ID model (three distinct IDs)

- `canvasId` — the canvas *type*, declared by the extension. Used by `list_canvas_capabilities` and `open_canvas`.
- `extensionId` — auto-derived `${source}:${name}` (e.g. `project:triage-board`). Only needed to disambiguate when two providers declare the same `canvasId`.
- `instanceId` — caller-invented handle for one panel (`^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`). `invoke_canvas_action` / `close` take only this.

**Never key durable state by `instanceId`** — it's a transient panel handle. Store state under the real owning scope (session workspace, `~/.copilot/extensions/<name>/artifacts/`, a repo path, or a domain `documentId`) and resolve it from `open()` input. Re-opening the same `instanceId` (or a provider reconnect / `extensions_reload`) re-invokes `open()` — treat it as idempotent and rehydrate from durable storage.

## Action handler contract

- Every `actions[]` entry needs a `handler`.
- Return the **raw** value; throw `CanvasError("code", "message")` for errors. Don't wrap in `{ ok, result, error }`.
- Action names starting with `canvas.` are reserved and rejected at declaration time.
- The context field is `ctx.canvasId`, not `ctx.id`.

## Injecting instructions

- Everyday path: return `{ additionalContext: "..." }` from `onSessionStart` (once/session) or `onUserPromptSubmitted` (per turn). Appended as a `developer`-role message.
- Section-level control: `systemMessage: { mode: "append", content }` or `{ mode: "customize", sections: {...} }` on `joinSession`. **Never use `mode: "replace"` from an extension** — it strips the SDK's safety guardrails.

## Debugging order

1. `extensions_manage({ operation: "list" })` — loaded / failed?
2. `extensions_manage({ operation: "inspect", name })` — read the log tail (uncaught throws, stray `console.log`, missing deps show here).
3. `extensions_reload` before re-testing — stale provider code is the #1 "nothing changed" cause.
4. Force an iframe reload: `open_canvas` again with the same `instanceId`.
5. Discovery silent? Confirm the file is exactly `extension.mjs` in an immediate subdir of an extensions root.
