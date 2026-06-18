---
name: GitHub Actions Workflow Standards
description: GitHub Actions workflow standards and best practices
applyTo: ".github/workflows/**/*.{yml,yaml}"
---

# GitHub Actions Standards

Maintain efficient, secure, and well-structured workflows.

## Standards

- Permissions: Define explicit top-level `permissions` to restrict token access (e.g., `contents: read` by default). Do not grant broad write access unless necessary.
- Use `ubuntu-slim` for small jobs that don't need more than 1 CPU.
- Lint workflows for security with `zizmor .github/workflows/`.
- [Use an intermediate environment variable](https://docs.github.com/en/actions/reference/security/secure-use#use-an-intermediate-environment-variable) for untrusted input in inline scripts: bind `${{ }}` to an `env` var and reference it as `"$VAR"`, never interpolate directly into `run`.
- No token > GITHUB_TOKEN > OIDC > GitHub App token > FGPATs > PATs
- uses: actions/create-github-app-token for creating GitHub App tokens
- Vet third-party actions before `uses:`. Check the OpenSSF Scorecard: `https://scorecard.dev/viewer/?uri=github.com/<owner>/<repo>`.

## Reference

The [GitHub Actions reference](https://docs.github.com/en/actions/reference) is the authoritative source for GitHub Actions best practices, workflow syntax, contexts, and runner details. Treat it as the bible: when reviewing or writing a workflow, defer to it over assumptions.
