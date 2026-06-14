---
name: fgpat-deeplink
description: "Build a prefilled link to GitHub's fine-grained PAT creation page so the user lands on the form with name, resource owner, expiration, and permissions pre-selected. Use when asked to 'create a link to make a token/PAT', 'deep link a token', 'prefill token permissions', or when an automation needs a PAT and you want a one-click create link."
---

# Fine-Grained PAT Deep Linking

```
https://github.com/settings/personal-access-tokens/new
  ?name=<≤40>&description=<≤1024>
  &target_name=<user-or-org>          # resource owner; the org for org-owned projects/secrets
  &expires_in=<days|none>
  &<permission>=<read|write|admin>    # one per perm; metadata=read implicit
```

Permission keys: repo perms bare (`contents`), org perms `organization_*` (`organization_projects`), account perms `user_*` (`user_models`). Exact slugs: [docs](https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens).
