---
name: write-an-extension
description: "Build, scaffold, debug, or share Copilot CLI extensions and canvas side panels. Use when creating tools, hooks, canvases, extension.mjs files, joinSession handlers, createCanvas flows, or when debugging extension load failures."
---

# Extension Authoring

Copilot CLI extensions are small ESM packages that add tools, hooks, session handlers, or canvas panels. Do not guess the SDK surface. Use the installed docs, generated types, and working examples.

## The loop

1. **Get the local SDK map.** Run `extensions_manage({ operation: "guide" })` for current doc and type paths.
2. **Scaffold.** Use `extensions_manage({ operation: "scaffold", kind: "canvas" | "basic", name, location })`. Do not hand-write the skeleton.
3. **Read the source of truth.** Start with `docs/extensions.md`, then `docs/agent-author.md`. Check `canvas.d.ts` or `index.d.ts` for exact signatures.
4. **Steal from examples.** Copy the nearest working pattern, then simplify.
5. **Reload and inspect.** After edits, run `extensions_reload`, then `extensions_manage({ operation: "inspect", name })` if anything fails.

## Canonical files

Installed SDK root is usually:

`/Applications/GitHub Copilot.app/Contents/Resources/copilot-sdk/`

Do not hardcode it. `extensions_manage({ operation: "guide" })` wins.

| File | Use it for |
| --- | --- |
| `docs/extensions.md` | Architecture, discovery, lifecycle |
| `docs/agent-author.md` | Author workflow, sessions, tools, hooks, events |
| `docs/examples.md` | Recipes and common patterns |
| `index.d.ts` | Top-level SDK types |
| `canvas.d.ts` | `createCanvas`, actions, canvas contexts, `CanvasError` |

## Known-good examples

Project examples live under `<repo>/.github/extensions/`. User examples live under `~/.copilot/extensions/`.

| Example | Why |
| --- | --- |
| `canvas-counter/` | Minimal canvas starting point |
| `triage-board/` | Full canvas with server, HTML, actions, SSE |
| `canvas-test-bench/` | Broad API surface testbed |
| `highcharts-canvas/` | Durable state model |
| `gemini-search/` | Tools-only extension |

## Tooling

```txt
extensions_manage({ operation: "guide" })
extensions_manage({ operation: "scaffold", kind: "canvas" | "basic", name, location: "project" | "user" })
extensions_manage({ operation: "list" })
extensions_manage({ operation: "inspect", name })
extensions_reload
share_extension / install_extension
```

## Rules that matter

- Entry file is exactly `extension.mjs`. ESM only. No `.ts` entrypoint.
- Put it in an immediate child of `.github/extensions/` or `~/.copilot/extensions/`.
- Never `console.log`. Stdout is JSON-RPC. Use `session.log(msg, { level, ephemeral })`.
- Do not vendor `@github/copilot-sdk`. The CLI resolves it.
- Tool names are global. Duplicate names make later extensions fail to load.
- Project extensions shadow user extensions with the same folder name.
- Canvas servers bind to loopback only, usually `127.0.0.1:0`.
- Never use `systemMessage.mode: "replace"` from an extension.

## Canvas gotchas

- `canvasId` is the canvas type.
- `extensionId` disambiguates duplicate providers.
- `instanceId` is a caller-created panel handle. Never use it for durable state.
- `open()` must be idempotent. Reloads and reconnects call it again.
- Every action needs a `handler`.
- Return raw action values. Throw `new CanvasError("code", "message")` for failures.
- Action names starting with `canvas.` are reserved.
- Action context uses `ctx.canvasId`, not `ctx.id`.

## Debug order

1. `extensions_manage({ operation: "list" })`, check loaded vs failed.
2. `extensions_manage({ operation: "inspect", name })`, read the log tail.
3. `extensions_reload`, then retest.
4. Reopen the canvas with the same `instanceId` to refresh the iframe.
5. If discovery is silent, verify `extension.mjs` location and filename exactly.
