---
name: write-a-skill
description: Create a new agent skill to make a repeatable capability reusable. Use when a capability is missing or keeps getting rebuilt, when the user says "make a skill", "write a skill", "turn this into a skill", or after solving something worth keeping.
---

# Write a Skill

Skills are modular, on-demand capabilities. When you find yourself solving the same kind of problem twice, or a capability is missing, capture it as a skill so it is reusable next time.

## The loop

1. **Spot the gap.** A capability is missing, or you just did something worth repeating. That is the trigger.
2. **Check local.** List `~/.copilot/skills/`. If a close skill exists, improve it instead of cloning.
3. **Search the registries.** Before writing from scratch, look for one that already exists (see below). Adapt a good one rather than reinventing it.
4. **Draft.** Create `~/.copilot/skills/<name>/SKILL.md`. Keep the body under ~100 lines. Bundle scripts or reference files only if needed.
5. **Tell Austen.** Say what you added or changed so he can use it too.

## Find existing skills

`npx skills` (from [vercel-labs/skills](https://github.com/vercel-labs/skills)) is the CLI for skill registries like [skills.sh](https://skills.sh).

```sh
npx skills find <query>          # search the registry by keyword
npx skills add <owner/repo> -l   # list skills in a repo without installing
npx skills use <owner/repo>@<skill>  # print a skill's prompt without installing (preview it)
npx skills add <owner/repo>@<skill> -g   # install globally; --copy to copy instead of symlink
npx skills list                  # what's already installed
```

Skills install into agent dirs in the portable `SKILL.md` format. To land one in Austen's setup, install with `--copy` or just drop the folder into `~/.copilot/skills/<name>/`. Prefer official namespaces (e.g. `github/awesome-copilot`, `microsoft/`, `vercel-labs/`) and skills that pass the registry security audits. Preview with `use` before trusting anything community-published.

## SKILL.md template

```md
---
name: skill-name
description: What it does in one sentence. Use when [specific triggers, keywords, file types].
---

# Skill Name

## Quick start
[Minimal working example]

## Workflow
[Step-by-step, checklists for anything complex]

## Advanced
[Link to REFERENCE.md or scripts/ only if the body would exceed ~100 lines]
```

## The description is everything

It is the only thing seen when deciding whether to load the skill. Make it earn its trigger.

- Max ~1024 chars, third person.
- First sentence: what it does. Second: "Use when [concrete triggers]".
- Name the keywords, contexts, and file types that should fire it.
- Good: "Extract text and tables from PDFs, fill forms, merge documents. Use when working with PDF files or when the user mentions PDFs, forms, or extraction."
- Bad: "Helps with documents." No way to distinguish it from anything else.

## Add scripts when

The operation is deterministic (validation, formatting), the same code would be regenerated repeatedly, or errors need explicit handling. Scripts save tokens and beat regenerated code on reliability. Prefer a small composable CLI in `~/.local/bin` for anything you also want to run by hand.

## Split files when

SKILL.md would exceed ~100 lines, content spans distinct domains, or advanced material is rarely needed. Keep references one level deep.

## Before finishing

- [ ] Description includes "Use when..." triggers
- [ ] Body under ~100 lines
- [ ] No time-sensitive info
- [ ] Consistent terminology
- [ ] Concrete examples
- [ ] Told Austen what changed
