# Actions Agent Plugin

Five GitHub Actions skills for runtime diagnosis, security, performance, and
estate design. They teach agents how to use `gh`, `actionlint`, and `zizmor`
directly, with focused procedures for the mistakes those tools do not prevent.

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

Every callable skill loads the toolkit, so copy `actions-workflow-toolkit`
alongside `actions-debug`, `actions-security-review`, `actions-optimization`,
or `actions-architecture-review`. The toolkit contains shared references,
so this copy path does not depend on files at the plugin root.

## Skills

```text
actions-workflow-toolkit          native-tool procedures and shared references
├── actions-debug                 absent, waiting, queued, skipped, and failed runs
├── actions-security-review       injection, triggers, pinning, permissions
├── actions-optimization          queue, execution, reruns, minutes, and cost
└── actions-architecture-review   bounded estate inventory and CI design
```

| Skill | Use when |
| --- | --- |
| [`actions-workflow-toolkit`](skills/actions-workflow-toolkit/SKILL.md) | Using native tools, interpreting run-attempt evidence, tracing reusable contracts, or checking Actions documentation. |
| [`actions-debug`](skills/actions-debug/SKILL.md) | Diagnosing why a workflow or job is absent, waiting, queued, skipped, failed, cancelled, or timed out. |
| [`actions-security-review`](skills/actions-security-review/SKILL.md) | Auditing workflow security, privileged triggers, token permissions, action pinning, secrets, or OIDC boundaries. |
| [`actions-optimization`](skills/actions-optimization/SKILL.md) | Reducing CI latency or cost, diagnosing queue time and reruns, or tuning runners, caches, matrices, and triggers. |
| [`actions-architecture-review`](skills/actions-architecture-review/SKILL.md) | Reviewing reusable workflow boundaries, duplicated CI, monorepo design, migrations, or governance. |

## Tools

The skills never install tools or dependencies.

| Capability | Required |
| --- | --- |
| Local correctness scanning | [`actionlint`](https://github.com/rhysd/actionlint) |
| Security scanning | [`zizmor`](https://docs.zizmor.sh/) |
| Shell analysis inside `run:` blocks | [`shellcheck`](https://www.shellcheck.net/) (optional but reported when unavailable) |
| Remote repository, run-attempt, and estate reads | Authenticated [`gh`](https://cli.github.com/) access to GitHub.com |

Use only the tools needed for the request. Local validation does not require
`gh` authentication. Authenticated zizmor network audits use an existing
`GH_TOKEN` or `GITHUB_TOKEN`; report missing access or skipped audits.

There are no bundled runtime wrappers, Python runtime dependency, or custom
tool-output schema. The [tooling procedures](skills/actions-workflow-toolkit/references/tools.md)
explain native exit codes, pagination, exact attempts/refs, and evidence gaps.
Retrieved workflow code is never executed during review.

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

Install only the tools needed for your task. The skills do not run setup
commands automatically.

## Development

Development validators use Python 3 and PyYAML for frontmatter checks.
Run these commands from this directory:

```bash
python3 scripts/check-plugin.py
python3 scripts/check-frontmatter.py
python3 scripts/check-links.py
python3 scripts/check-portable-layout.py
python3 scripts/check-recipes.py
./scripts/check-urls.sh
./scripts/check-audit-idents.sh
./scripts/check-action-refs.sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m unittest discover -s evals/tests -p 'test_*.py'
./test-corpus/verify.sh
```

CI also runs actionlint, zizmor, and ShellCheck against the repository's own workflow and every bundled shell script.

The synthetic behavioral corpus and exact-model paired harness live in
[`evals/`](evals/). Deterministic harness tests run in CI; live model
comparisons require existing ephemeral authentication and write raw transcripts
only to an external session-artifact directory.

## Safety

The skills are read-only by default. They do not edit workflows, commit, push, or open a pull request unless the current request explicitly authorizes it. Security scanner output is ranked by exploitability and business consequence, not dumped as undifferentiated rule noise.

## License

MIT. See [`LICENSE`](LICENSE).
