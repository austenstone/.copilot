# .copilot

My personal GitHub Copilot customizations, synced from `~/.copilot`. Drop these into your home Copilot config directory (or a repo's `.github/`) to share the same instructions, skills, hooks, and MCP setup.

## What's here

| Path | What it is |
| --- | --- |
| `copilot-instructions.md` | Top-level pointer to the instruction set |
| `instructions/` | Always-on instructions (identity, personality, coding standards, web use) |
| `skills/` | Agent skills, tracked at [austenstone/skills](https://github.com/austenstone/skills) |
| `agents/` | Custom agents |
| `hooks/` | Lifecycle hooks + `setup-hooks` installer |
| `plugin.json` | Copilot CLI plugin manifest |
| `.mcp.json` | Distributable MCP servers (public packages only) |
| `mcp-config.example.json` | Full personal MCP config. Secrets are `${ENV_VAR}` placeholders |

## Usage

### Plugin install

```bash
copilot plugin marketplace add austenstone/.copilot
copilot plugin install copilot@austenstone
```

### Manual install

Personal (applies everywhere):

```bash
cp -R instructions skills hooks agents ~/.copilot/
cp copilot-instructions.md plugin.json .mcp.json ~/.copilot/
```

Per-repo:

```bash
mkdir -p .github
cp -R instructions .github/instructions
cp -R skills .github/skills
./hooks/setup-hooks .   # installs .github/hooks/hooks.json
```

## MCP config

The plugin ships `.mcp.json` with public, no-auth-needed servers. One env var is needed if you want Brave Search:

- `BRAVE_API_KEY`

For the full personal config (all servers including GitHub-internal and OAuth): copy the example and fill in secrets:

```bash
cp mcp-config.example.json ~/.copilot/mcp-config.json
```

Additional env vars for the full config:

- `PLAYWRIGHT_MCP_EXTENSION_TOKEN`
- `TFE_TOKEN`

## Notes

- `skills/` is a git submodule ([austenstone/skills](https://github.com/austenstone/skills)). Use `--recurse-submodules` when cloning or the plugin install won't bundle them.
- The real `mcp-config.json` is gitignored. Only the sanitized example is tracked.
- `skills/google-search/profile/` (browser session data) is excluded.
