---
name: mac-maintenance
description: Mac upkeep routine: brew update/upgrade, pull clean git repos under ~/source, check global npm packages with npm-check-updates, empty Trash. Use when Austen asks for "mac maintenance", "cleanup", "update my mac", "refresh repos", "brew update", "ncu", "outdated npm packages", or any periodic housekeeping on the machine.
---

# Mac Maintenance

Run the steps in order. Report a terse summary at the end.

## Golden rule: be patient, never interrupt an update

Update tools are slow and run non-interactively here (no TTY), so their output is
**buffered** and they often sit at **0% CPU** while waiting on network or
downloads. **None of that means hung.** Do not kill an update because it looks
idle. The one time it actually stalls is when a tool blocks on a hidden
**interactive prompt** -- so the real fix is to remove prompts entirely (below),
not to babysit and kill processes.

Rules:

- **Run everything non-interactively.** Pre-answer every prompt so nothing can
  block. Use the env vars and `yes |` shown below.
- **Use generous `initial_wait`** (300s) and keep waiting with `read_bash`. A
  full brew upgrade of large formulae (openjdk, go, node) can take 20-40+ min.
- **Don't equate quiet with dead.** Buffered output + 0% CPU is normal during
  downloads. Only suspect a real stall after a long quiet period AND evidence of
  no progress (see "Is it actually stuck?").
- **Never `kill` an update** unless you've confirmed a real interactive prompt is
  blocking it. If you must, kill and re-run with prompts pre-answered -- don't
  just retry the same blocking command.

## Run

1. Homebrew. Run non-interactively so the upgrade confirmation and tap-trust
   prompts can't block:

```bash
export HOMEBREW_NO_AUTO_UPDATE=0 \
       HOMEBREW_NO_ENV_HINTS=1 \
       HOMEBREW_NO_REQUIRE_TAP_TRUST=1
brew update
yes | brew upgrade
```

- `yes |` auto-confirms the `Do you want to proceed with the upgrade? [y/n]`
  prompt that otherwise silently blocks forever in a non-TTY. This was the exact
  thing that broke a past run.
- `HOMEBREW_NO_REQUIRE_TAP_TRUST=1` skips the untrusted-tap prompt.
- `HOMEBREW_NO_ENV_HINTS=1` cuts noise.
- Use `initial_wait: 300`, `mode: sync`, then `read_bash` patiently until it
  exits. Piping through `| tail -40` is fine but hides progress -- if you do,
  verify progress out-of-band instead of assuming it's stuck.
- After it exits, confirm with `brew outdated` (should be empty).

2. Repos under `~/source` (fast-forward only, skip dirty). Plain bash version
   (the `.git(N)` zsh glob does not work in bash):

```bash
for dir in ~/source/*/; do
  [ -d "$dir/.git" ] || continue
  if [ -n "$(git -C "$dir" status --porcelain)" ]; then
    echo "skip (dirty): $dir"; continue
  fi
  out=$(git -C "$dir" pull --ff-only 2>&1)
  if [ $? -eq 0 ]; then
    echo "$out" | grep -q "Already up to date" && echo "current: $dir" || echo "pulled: $dir"
  else
    echo "failed: $dir -> $(echo "$out" | tail -1)"
  fi
done
```

Skip dirty repos unless Austen explicitly asked to handle them. Report skipped
and failed paths. Common failures (diverged / no upstream) are expected -- list
them, don't try to force them.

3. Global npm packages (report only, don't auto-upgrade):

```bash
npx -y npm-check-updates -g
```

Surface the suggested `npm -g install ...` command. Don't run it automatically --
global package upgrades can break tooling. Ask before applying.

4. Empty Trash:

```bash
osascript -e 'tell application "Finder" to empty trash'
```

## Is it actually stuck? (only after a long quiet stretch)

Before ever considering a kill, prove there's no progress from a **separate**
shell -- don't touch the running one:

```bash
# Is a real upgrade prompt waiting? (the usual culprit)
ps aux | grep -iE "[b]rew.rb (upgrade|install)"
# Are new bottles still landing? (timestamps should advance)
ls -lt ~/Library/Caches/Homebrew/downloads/ | head
ls -lt /opt/homebrew/Cellar/ | head
```

If Cellar/download timestamps are advancing, it's working -- keep waiting. If it's
truly parked on a `[y/n]`, the right fix is to re-run with `yes |` and the env
vars above, not to kill-and-pray.

## Report

Terse counts only:

- brew: upgraded count / already current / any deprecated or untrusted-tap notes
- repos: pulled / skipped (dirty) / failed (list failed paths)
- npm globals: outdated count (list packages behind, ask before upgrading)
- trash: emptied / failed
