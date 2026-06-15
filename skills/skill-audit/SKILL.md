---
name: skill-audit
description: Audit the local skill inventory for prompt-budget bloat, duplicate names, near-identical descriptions, and invalid frontmatter. Use when skills feel bloated, descriptions seem redundant, after adding several skills, when context budget is tight, or to validate SKILL.md frontmatter before committing.
---

# Skill Audit

Every skill's `description` is loaded into context on every turn. A big inventory quietly eats prompt budget and routes worse when descriptions overlap. This audits the canonical skill sources (`~/.copilot/skills`, `~/.agents/skills`); add `--plugins` to also scan installed-plugin copies.

## Audit the inventory

```bash
node ~/.copilot/skills/skill-audit/scripts/skill-audit.mjs            # source skills
node ~/.copilot/skills/skill-audit/scripts/skill-audit.mjs --plugins  # include installed plugins
```

Reports:
- **Total description token budget** always loaded into context.
- **Invalid frontmatter** — missing YAML, `name`, or `description`.
- **Duplicate names** — same skill name in multiple roots.
- **Near-identical descriptions** — ≥60% word overlap, likely routing collisions.
- **Bloated descriptions** — over 600 chars, candidates for trimming.

## Validate frontmatter

```bash
node ~/.copilot/skills/skill-audit/scripts/validate-skills.mjs                # all skills
node ~/.copilot/skills/skill-audit/scripts/validate-skills.mjs path/to/SKILL.md   # specific files
```

Exits non-zero on any problem, so it works as a pre-commit gate. Checks frontmatter exists, has `name` + `description`, description is long enough to route, and `name` matches the folder.

## Acting on results

- **Suggest first, edit only when asked.** Don't delete skills unprompted.
- Prefer trimming over deleting: tighten a bloated description before removing the skill.
- For near-duplicates, decide which one owns the trigger and narrow the other's description, or merge them.
- For duplicate names across roots, keep the canonical one and remove the stray copy.
- Preserve trigger nouns in descriptions: the product, tool, action, and object that should fire the skill.
