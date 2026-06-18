---
name: "Coding Standards"
description: "TypeScript standards"
applyTo: "**/*.{ts,tsx,mts,cts,js,jsx,mjs,cjs}"
---

# Project & Type System
- Default to TS over JS. Enable TypeScript strict mode. Avoid `any`.
- Use `satisfies` over `as` (The Death of Type Assertions).
- Naming: `camelCase` variables/functions, `PascalCase` components/types, `SCREAMING_SNAKE` constants.

# Syntax & Variables
- Always prefer arrow functions `() => {}` over the `function` keyword. Use implicit returns.
- Use `const` and `let` over `var`.
- Use template literals over string concatenation.
- Use ES Modules `import`/`export` over CommonJS `require`.

# Data & Control Flow
- Use object and array destructuring over dot-notation.
- Use spread `...` syntax over `Object.assign()` and `Array.concat()`.
- Use optional chaining `?.` and nullish coalescing `??`.
- Use declarative array methods over `for` loops.
- Use strict equality `===`.

# React & Logic
- Use Functional Components & Hooks over Class Components.
- Use ternary operators and logical AND `&&` for conditionals.
- Error handling: `try/catch` for async, return early on errors, never swallow silently.
- Use `async`/`await` over Promise chains `.then()`.

# Tooling
- Prefer `npm` and `vitest`.
- Compilers: `vite` > `turbopack` > `rspack`.
- Linting/Formatting: `biome`.
- `tsc` is not a compiler.