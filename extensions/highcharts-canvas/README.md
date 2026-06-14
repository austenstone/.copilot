# highcharts-canvas

Render interactive [Highcharts](https://www.highcharts.com/) charts inline in the GitHub Copilot app's side panel.

A canvas extension port of [mcp-highcharts](https://github.com/austenstone/mcp-highcharts). Same idea — agent passes a Highcharts options object, you get a live chart — but rendered as a Copilot canvas instead of via MCP.

## Install

From inside the Copilot app, open the command palette → **"Install extension from Gist/URL…"** and paste this gist URL.

Or install programmatically via the `install_extension` tool.

## Canvas

`id: chart` — Highcharts

## Actions

| Action | What |
| --- | --- |
| `render_chart` | Any standard chart — line, bar, pie, scatter, heatmap, sankey, treemap, wordcloud, etc. |
| `render_stock_chart` | Highcharts Stock — navigator, range selector, 40+ indicators |
| `render_dashboard` | Highcharts Dashboards — multi-component layouts |
| `render_map` | Highcharts Maps — pass `mapData` URL or topojson string |
| `render_gantt` | Project timelines with dependencies + milestones |
| `render_grid` | Standalone DataGrid with sorting + pagination |

All actions take `{ options: <Highcharts options object> }`. `render_map` also accepts `mapData`.

## Notes

- Loads Highcharts modules from `code.highcharts.com` CDN — needs network.
- Each open canvas instance runs its own loopback HTTP server on `127.0.0.1:<random>`.
- State is per-instance and ephemeral (lives in the extension process). Reopening with the same instanceId reuses the server; restarting the extension clears charts.
- Theme-aware: auto-adapts to the app's light/dark mode via CSS variables documented in the canvas theme contract.
- No `package.json` / `node_modules` — `@github/copilot-sdk` is resolved by the CLI.
