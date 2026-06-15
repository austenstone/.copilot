---
name: mac-maintenance
description: Mac upkeep routine: brew update/upgrade, pull clean git repos under ~/source, empty Trash. Use when Austen asks for "mac maintenance", "cleanup", "update my mac", "refresh repos", "brew update", or any periodic housekeeping on the machine.
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

3. Empty Trash:

```bash
osascript -e 'tell application "Finder" to empty trash'
```

## Report

Terse counts only:

- brew: upgraded / already current
- repos: pulled / skipped (dirty) / failed
- trash: emptied / failed
