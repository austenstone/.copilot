# .copilot

My personal GitHub Copilot customizations, synced from `~/.copilot`. Drop these into your home Copilot config directory (or a repo's `.github/`) to share the same instructions, skills, hooks, and MCP setup.

## What's here

| Path | What it is |
| --- | --- |
| `copilot-instructions.md` | Top-level pointer to the instruction set |
| `instructions/` | Always-on instructions (identity, personality, coding standards, web use) |
| `skills/` | Austen-authored agent skills and local-only upstream installs |
| `agents/` | Custom agents |
| `hooks/` | Lifecycle hooks + `setup-hooks` installer |
| `plugins/` | Self-contained marketplace plugins |
| `.github/plugin/marketplace.json` | `austenstone` plugin marketplace catalog |
| `.mcp.json` | Distributable MCP servers (public packages only) |
| `mcp-config.example.json` | Full personal MCP config. Secrets are `${ENV_VAR}` placeholders |

## Usage

### Plugin install

```bash
copilot plugin marketplace add austenstone/.copilot
copilot plugin install copilot@austenstone
```

GitHub Actions workflow review, security, optimization, and architecture skills:

```bash
copilot plugin marketplace add austenstone/.copilot
copilot plugin install actions@austenstone
```

The Actions package is an [Agent Plugins 1.0](https://agent-plugins.org/) plugin. Its canonical, self-contained source and direct skill-copy instructions are in [`plugins/actions/`](plugins/actions/).

### Manual install

Personal (applies everywhere):

```bash
cp -R instructions skills hooks agents ~/.copilot/
cp copilot-instructions.md .mcp.json ~/.copilot/
./install-upstream-skills.sh
```

Per-repo:

```bash
mkdir -p .github
cp -R instructions .github/instructions
cp -R skills .github/skills
./hooks/setup-hooks .   # installs .github/hooks/hooks.json
```

### Upstream skills

[`docx`](https://github.com/anthropics/skills/tree/main/skills/docx), [`pptx`](https://github.com/anthropics/skills/tree/main/skills/pptx), and [`xlsx`](https://github.com/anthropics/skills/tree/main/skills/xlsx) are owned by Anthropic. The migration source was verified against [`fa0fa64`](https://github.com/anthropics/skills/commit/fa0fa64bdc967915dc8399e803be67759e1e62b8), the upstream revision that updated all three skills. They are installed directly from their canonical exact paths with `gh skill` instead of being copied into this repository or republished through a plugin:

```bash
./install-upstream-skills.sh
gh skill list --scope user
```

The normal install follows the upstream default branch and preserves the CLI-injected `metadata.github-ref` and `metadata.github-tree-sha` used by `gh skill update`. Existing directories are not overwritten unless you explicitly pass `--force`:

```bash
./install-upstream-skills.sh --force
```

Review or back up local changes before forcing an install. To test the bootstrap without touching your user skills, set a temporary target:

```bash
GH_SKILL_DIR="$(mktemp -d)" ./install-upstream-skills.sh
```

Review upstream drift before applying it:

```bash
gh skill update --dry-run
gh skill update --all
```

For a reproducible snapshot, set an explicit commit or tag:

```bash
GH_SKILL_PIN="<commit-or-tag>" ./install-upstream-skills.sh
```

Pinned installs include `metadata.github-pinned` and are intentionally skipped by `gh skill update`. Use this mode only when reproducibility is more important than automatic drift detection.

## Skill ownership

- **Austen-authored:** Commit, dogfood, evaluate, and publish from this repository or one of its plugins.
- **Upstream-owned:** Install directly from the canonical repository with `gh skill`; retain its injected source metadata and keep the installed directory ignored here.
- **Patched fork:** Use a distinct skill name under `skills/forks/`, record the upstream repository and revision plus the patch rationale, and verify the upstream license permits redistribution. Never silently replace an upstream skill under its original name.
- **Private/internal:** Keep in its private source or installed plugin. Never copy it into this public repository.

General-purpose Austen-owned skills should be periodically evaluated for contribution or listing in [`github/awesome-copilot`](https://github.com/github/awesome-copilot). Upstream-owned skills stay upstream even when they are heavily dogfooded here.

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

- Austen-owned skills live directly in this repository as committed files.
- `skills/docx/`, `skills/pptx/`, and `skills/xlsx/` are ignored local installs, not publication sources.
- The real `mcp-config.json` is gitignored. Only the sanitized example is tracked.
- `skills/google-search/profile/` (browser session data) is excluded.
