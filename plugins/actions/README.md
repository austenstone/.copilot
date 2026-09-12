# Actions Agent Plugin

Four GitHub Actions skills that make workflows **safer, faster, and better-shaped** with deterministic tooling instead of vibes.

This directory is the canonical source. It is a self-contained [Agent Plugins 1.0](https://agent-plugins.org/) package with real files under the required `skills/` location. The specification rejects package paths that resolve outside the plugin root, so the package does not use symlinks to the repository's top-level skills.

## Install with Copilot CLI

```bash
copilot plugin marketplace add austenstone/.copilot
copilot plugin install actions@austenstone
```

Verify the plugin and its skills:

```bash
copilot plugin list
copilot skill list
```

Only the Copilot CLI marketplace, install, and load flow is validated by this repository. Other Agent Plugins 1.0 clients can consume [`plugins/actions`](.) through their own documented local or Git installation mechanism.

## Use individual skills directly

Clients that read portable `SKILL.md` directories can use one or more skills without installing the whole plugin. Clone the repository, then copy the selected directory and its bundled references:

```bash
git clone https://github.com/austenstone/.copilot
cp -R .copilot/plugins/actions/skills/actions-optimization ~/.copilot/skills/
cp -R .copilot/plugins/actions/skills/actions-workflow-toolkit ~/.copilot/skills/
```

The review skills load the toolkit, so copy `actions-workflow-toolkit` alongside `actions-security-review`, `actions-optimization`, or `actions-architecture-review`.

## Skills

```text
actions-workflow-toolkit          shared substrate for the other three
├── actions-security-review       injection, triggers, pinning, permissions
├── actions-optimization          queue vs run vs rerun, then the highest-ROI lever
└── actions-architecture-review   cross-file and cross-repository CI design
```

| Skill | Use when |
| --- | --- |
| [`actions-workflow-toolkit`](skills/actions-workflow-toolkit/SKILL.md) | Running actionlint and zizmor correctly, retrieving performance data, or routing a question to live GitHub Actions documentation. |
| [`actions-security-review`](skills/actions-security-review/SKILL.md) | Auditing workflow security, privileged triggers, token permissions, action pinning, secrets, or OIDC boundaries. |
| [`actions-optimization`](skills/actions-optimization/SKILL.md) | Reducing CI latency or cost, diagnosing queue time and reruns, or tuning runners, caches, matrices, and triggers. |
| [`actions-architecture-review`](skills/actions-architecture-review/SKILL.md) | Reviewing reusable workflow boundaries, duplicated CI, monorepo design, migrations, or governance. |

## Why both actionlint and zizmor

| Fixture | actionlint | zizmor |
| --- | --- | --- |
| `broken.yml` | **7 correctness findings** | 0 relevant |
| `insecure.yml` | 3 | **14 findings across 8 security rules** |
| `clean.yml` | **0** | **0** |

Neither tool subsumes the other. [`test-corpus/`](test-corpus/) keeps the documented behavior and false-positive control honest.

Install the tools through their documented package:

```bash
brew install actionlint shellcheck
brew install zizmor
```

`zizmor` needs `GH_TOKEN` for network audits such as known-vulnerability and remote-reference checks. The toolkit documents explicit degraded modes rather than treating a failed scan as clean.

## Development

Run these commands from this directory:

```bash
python3 scripts/check-plugin.py
python3 scripts/check-frontmatter.py
python3 scripts/check-links.py
python3 scripts/check-recipes.py
./scripts/check-urls.sh
./scripts/check-audit-idents.sh
./scripts/check-action-refs.sh
./scripts/check-wrapper-runs.sh
./test-corpus/verify.sh
```

CI also runs actionlint, zizmor, and ShellCheck against the repository's own workflow and every bundled shell script.

## Safety

The skills are read-only by default. They do not edit workflows, commit, push, or open a pull request unless the current request explicitly authorizes it. Security scanner output is ranked by exploitability and business consequence, not dumped as undifferentiated rule noise.

## License

MIT. See [`LICENSE`](LICENSE).
