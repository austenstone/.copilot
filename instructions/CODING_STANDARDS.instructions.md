---
name: "Coding Standards"
description: "TypeScript and workflow coding standards"
applyTo: "**"
---

# Coding Standards

- Naming: `camelCase` variables/functions, `PascalCase` components/types, `SCREAMING_SNAKE` constants.
- AVOID Comments
- Code should be self-explanatory and readable
- KISS (Keep It Simple, Stupid)
- Comments explain WHY, not WHAT.
- Don't reinvent the wheel. Leverage existing libraries and patterns.
- npm only is favored
- TypeScript strict mode. No `any` unless unavoidable.
- No enums. Use `as const` objects or union types.
- Error handling: try/catch for async, return early on errors, never swallow silently.
- Don't over-abstract. A 50 line function > 5 files of enterprise patterns.
- Avoid long lived secrets when you can
