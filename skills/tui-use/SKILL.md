---
name: tui-use
description: Drive interactive terminal programs that expect a human at the keyboard — REPLs (python, node), debuggers (pdb, gdb), and full-screen TUI apps (vim, lazygit, htop, fzf). Use when a program waits for keystrokes, a debugger hits a breakpoint, or a full-screen TUI renders a menu and raw terminal output is unreadable. Triggers: REPL, debugger, pdb, gdb, breakpoint, vim, lazygit, htop, fzf, interactive prompt, TUI.
---

# tui-use

Like BrowserUse, but for the terminal. Spawns a program in a PTY, renders its screen to clean plain text through a headless xterm emulator, and lets you send keystrokes. The killer feature is `wait`: it blocks until the screen stabilizes (or a pattern appears), so no `sleep` guessing.

## Native vs tui-use — decide first

- **Native `run_in_terminal` (async) + `send_to_terminal`** is fine for line-oriented REPLs and simple prompts. Reach for it first; it needs no install.
- **tui-use** wins when: it's a **full-screen TUI** (vim/lazygit/htop/fzf) where raw ANSI output is garbage, you need a **clean rendered snapshot**, you need to know **which item is selected** (`highlights`), or you need a reliable **`wait --text` semantic signal** instead of polling. Debuggers and long-lived REPL sessions across many calls also benefit from its persistent daemon.

## Setup

```sh
command -v tui-use || npm install -g tui-use   # verified working on this machine
```

## Core workflow

```
start → wait → type/press → wait → ... → kill
```

`start` makes the new session current automatically. Only call `use <id>` when switching between multiple existing sessions.

## Commands

```sh
tui-use start <cmd>                 # start a program (becomes current session)
tui-use start --cwd <dir> "<cmd> -flags"   # start in dir; quote full cmd to pass flags
tui-use start --label <name> <cmd>  # labeled session
tui-use type <text>                 # type printable chars / strings / vim cmds (i, :wq)
tui-use press <key>                 # named key: enter, escape, tab, ctrl+r, arrow_up, f1…
tui-use paste "<a>\n<b>\n"          # multi-line paste (each line + Enter)
tui-use wait --text <pattern>       # PREFERRED: block until screen contains pattern
tui-use wait [<ms>] [--debounce <ms>]  # block until screen idle (default 3000ms / 100ms)
tui-use snapshot [--format json]    # current screen as clean text (or JSON w/ highlights)
tui-use find <pattern>              # regex search the screen
tui-use scrollup <n> / scrolldown <n>  # scroll history
tui-use list / info / rename <label>   # session management
tui-use use <id>                    # switch sessions
tui-use kill                        # kill current session
tui-use keys                        # list all valid key names
tui-use daemon status|stop|restart  # manage the background daemon
```

## type vs press

- `type` — printable characters: letters, numbers, symbols, vim commands (`i`, `u`, `:wq`).
- `press` — a named control key: `enter`, `escape`, `tab`, `backspace`, `arrow_up`, `ctrl+r`, `ctrl+c`, `f1`–`f10`.

## Rules

1. **wait before type/press** — confirm the program is ready.
2. **prefer `wait --text <pattern>`** — a semantic signal beats silence detection (`">>>"` for python, `"(Pdb)"` for pdb, `"\\$"` for a shell prompt).
3. **`use` only when switching** — `start` already sets the current session.
4. **check status** — if `snapshot --format json` shows `"exited"`, stop sending input.
5. **kill when done** — clean up sessions.

## Examples

Python REPL:
```sh
tui-use start python3
tui-use wait --text ">>>"
tui-use type "print(21*2)"; tui-use press enter
tui-use wait --text ">>>"
tui-use snapshot
tui-use type "exit()"; tui-use press enter
tui-use kill
```

Debugger / TUI — same loop. Start, `wait --text` for the prompt or a known label (`"(Pdb)"`, `"PID"`), `type`/`press`, `snapshot` to read state, `kill` to clean up. For full-screen apps use `snapshot --format json` to read the `highlights` field (the inverse-video span = the currently selected item).
