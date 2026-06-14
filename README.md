# .copilot

My personal GitHub Copilot customizations, synced from `~/.copilot`. Drop these into your home Copilot config directory (or a repo's `.github/`) to share the same instructions, skills, hooks, and MCP setup.

## What's here

| Path | What it is |
| --- | --- |
| `copilot-instructions.md` | Top-level pointer to the instruction set |
| `instructions/` | Always-on custom instructions (identity, personality, coding standards, web/shell use) |
| `skills/` | Portable agent skills, tracked separately at [`austenstone/skills`](https://github.com/austenstone/skills), that Copilot loads on demand |
| `hooks/` | Lifecycle hooks + `setup-hooks` installer |
| `mcp-config.example.json` | Sanitized MCP server config. Secrets are `${ENV_VAR}` placeholders |

## Usage

Personal (applies everywhere):

```bash
cp -R instructions skills hooks ~/.copilot/
cp copilot-instructions.md ~/.copilot/
```

Per-repo:

```bash
mkdir -p .github
cp -R instructions .github/instructions
cp -R skills .github/skills
./hooks/setup-hooks .   # installs .github/hooks/hooks.json
```

## MCP config

`mcp-config.example.json` is sanitized. Copy it to your live config and fill in the secrets:

```bash
cp mcp-config.example.json ~/.copilot/mcp-config.json
```

Set these in your environment (the live config is gitignored):

- `BRAVE_API_KEY`
- `PLAYWRIGHT_MCP_EXTENSION_TOKEN`
- `TFE_TOKEN`

## Notes

- The real `mcp-config.json` is gitignored. Only the sanitized example is tracked.
- `skills/google-search/profile/` (browser session data) is excluded.
