---
name: mac-maintenance
description: Mac upkeep routine: brew update/upgrade, pull clean git repos under ~/source, check global npm packages with npm-check-updates, empty Trash. Use when Austen asks for "mac maintenance", "cleanup", "update my mac", "refresh repos", "brew update", "ncu", "outdated npm packages", or any periodic housekeeping on the machine.
---

# Mac Maintenance

Run the steps in order. Report a terse summary at the end.

## Run

1. Homebrew:

```bash
brew update && brew upgrade
```

2. Repos under `~/source` (fast-forward only, skip dirty):

```bash
for repo in ~/source/*/.git(N); do
  dir=${repo:h}
  if [[ -n "$(git -C "$dir" status --porcelain)" ]]; then
    echo "skip (dirty): $dir"
    continue
  fi
  git -C "$dir" pull --ff-only
done
```

Skip dirty repos unless Austen explicitly asked to handle them. Report skipped paths.

3. Global npm packages (report only, don't auto-upgrade):

```bash
npx -y npm-check-updates -g
```

Surface the suggested `npm -g install ...` commands. Don't run them automatically — global package upgrades can break tooling. Ask before applying.

4. Empty Trash:

```bash
osascript -e 'tell application "Finder" to empty trash'
```

## Report

Terse counts only:

- brew: upgraded / already current
- repos: pulled / skipped (dirty) / failed
- npm globals: outdated count (list packages behind, ask before upgrading)
- trash: emptied / failed
