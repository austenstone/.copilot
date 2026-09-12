# Actions Agent Plugin

Five GitHub Actions skills for runtime diagnosis, security, performance, and
estate design, backed by deterministic tooling instead of vibes.

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
or `actions-architecture-review`. The toolkit contains its runtime helpers and
contract, so this copy path does not depend on files at the plugin root.

## Skills

```text
actions-workflow-toolkit          shared procedures and portable helpers
├── actions-debug                 absent, waiting, queued, skipped, and failed runs
├── actions-security-review       injection, triggers, pinning, permissions
├── actions-optimization          queue, execution, reruns, minutes, and cost
└── actions-architecture-review   bounded estate inventory and CI design
```

| Skill | Use when |
| --- | --- |
| [`actions-workflow-toolkit`](skills/actions-workflow-toolkit/SKILL.md) | Collecting bounded workflow, run-attempt, or estate evidence with the shared helper contract. |
| [`actions-debug`](skills/actions-debug/SKILL.md) | Diagnosing why a workflow or job is absent, waiting, queued, skipped, failed, cancelled, or timed out. |
| [`actions-security-review`](skills/actions-security-review/SKILL.md) | Auditing workflow security, privileged triggers, token permissions, action pinning, secrets, or OIDC boundaries. |
| [`actions-optimization`](skills/actions-optimization/SKILL.md) | Reducing CI latency or cost, diagnosing queue time and reruns, or tuning runners, caches, matrices, and triggers. |
| [`actions-architecture-review`](skills/actions-architecture-review/SKILL.md) | Reviewing reusable workflow boundaries, duplicated CI, monorepo design, migrations, or governance. |

## Runtime dependencies

The skills never install tools or dependencies.

| Capability | Required |
| --- | --- |
| All helpers | Python 3 |
| Local correctness scanning | [`actionlint`](https://github.com/rhysd/actionlint) |
| Security scanning | [`zizmor`](https://docs.zizmor.sh/) |
| Shell analysis inside `run:` blocks | [`shellcheck`](https://www.shellcheck.net/) (optional but reported when unavailable) |
| Run-attempt and estate collection | Authenticated [`gh`](https://cli.github.com/) access to GitHub.com |
| Estate YAML parsing | [`PyYAML`](https://pyyaml.org/) |

Remote scanner network audits require an existing `GH_TOKEN` or
`GITHUB_TOKEN`. Missing tools, authentication, inaccessible inputs, timeouts,
and degraded scans are explicit results, never silently installed or reported
as clean.

The helpers live under
[`skills/actions-workflow-toolkit/scripts/`](skills/actions-workflow-toolkit/scripts/)
and emit the versioned
[`actions-helper/v1` envelope](skills/actions-workflow-toolkit/references/helper-contract.md)
to stdout by default. They never execute retrieved workflow files.

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
python3 -m pip install PyYAML
```

Install dependencies before using the corresponding helper. The helpers
themselves do not run these commands.

## Development

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
./scripts/check-helpers.sh
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
