---
name: summarize
description: "Summarize any URL, YouTube video, podcast, PDF, image, audio/video, or local file from the terminal. Use when the user wants the gist of a link, video, podcast episode, paper, or document, or says 'summarize this', 'tldr', 'what's this video about', 'summarize this podcast/PDF'. Backed by the steipete/summarize CLI; defaults to the keyless agy (Antigravity) backend so it's free."
---

# Summarize

- Gist of a URL, YouTube, podcast, PDF, image, audio/video, or stdin.
- Run: `timeout 180 npx -y @steipete/summarize "<input>" --cli agy --plain` (or `summarize` if installed; Node 24+).
- `--cli agy`: free, reliable default (copilot returns empty, gemini key is capped).
- `--length short|medium|long|xl|xxl` or char count · `--lang <lang>`.
- `--extract` text only · `--slides` video screenshots · `--json` machine output.
- stdin: `pbpaste | npx -y @steipete/summarize - --cli agy --plain`
- Fail fast on error/empty, don't retry.
