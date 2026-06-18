---
name: loop-engineering
description: Turn a manual, repeated AI task into an automated loop. Use when the user wants to "set up a loop", "run this every X", "automate this daily", schedule recurring background work, or stop re-prompting the same thing by hand. Maps the request onto a session automation, a scheduled workflow, or a long-running goal.
---

# Loop Engineering

Convert a repeated manual prompt into a reliable, self-checking loop. Don't just schedule it. Engineer the boundaries that make it trustworthy.

## 1. Nail the goal
One sentence on what "done" looks like each run. If it's fuzzy, ask once, then proceed.

## 2. Add a verifiable boundary (this is what makes loops reliable)
Find a check the loop can self-grade against: a test suite, a lint/build, a script exit code, a diff that must stay empty. No boundary means no loop. Define or write one before scheduling.

## 3. Pick the primitive
- **Session automation** (`save_session_automation`): recurring wake-ups in THIS chat for exploratory work, memory/"dream" passes, inbox triage. Cadence: once / minutes / daily / weekly.
- **Workflow** (`save_workflow`): project-scoped scheduled task tied to a repo: security scans, dep bumps, refreshing agent instruction files.
- **One long goal**: a single hard task with tests as the boundary. Let it run, don't schedule.

## 4. Set cadence to the cost of being wrong
Cheap and reversible runs frequent. Expensive or irreversible runs rare, or gets gated.

## 5. Keep a human in the loop
Never auto-send, auto-merge, or auto-delete. The loop drafts and stages; the user keeps final authority. Make the last step "leave it for review" unless told otherwise.

Confirm goal, boundary, primitive, and cadence back to the user, then create it.
