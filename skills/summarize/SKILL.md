---
name: summarize
description: "Summarize any URL, YouTube video, podcast, PDF, image, audio/video, or local file from the terminal. Use when the user wants the gist of a link, video, podcast episode, paper, or document, or says 'summarize this', 'tldr', 'what's this video about', 'summarize this podcast/PDF'. Backed by the steipete/summarize CLI; defaults to the keyless agy (Antigravity) backend so it's free."
---

# Summarize

One command to get the gist of almost anything: web pages, YouTube, podcasts, RSS, PDFs, images, audio/video, or piped stdin. Extracts content (transcripts, OCR, readability) then summarizes with an LLM.

## Use it

```bash
summarize "https://example.com" --cli agy --plain
```

- `--cli agy` — keyless Antigravity backend (free, Google OAuth). The reliable default here.
- `--plain` — raw Markdown, no ANSI/terminal rendering. Use for automated/captured output.
- `--length short|medium|long|xl|xxl` or a char target (`1500`, `20k`). Default is `long`.
- `--lang <language>` — output language (`auto` matches source).
- Always pass a `--timeout` for automation: `timeout 180 summarize ... --cli agy --plain`.

### Inputs

```bash
summarize "https://youtu.be/dQw4w9WgXcQ" --cli agy --plain     # YouTube (transcript)
summarize "https://feeds.npr.org/500005/podcast.xml" --cli agy  # podcast RSS (latest episode)
summarize "/path/to/paper.pdf" --cli agy --plain                # local PDF
summarize "/path/to/audio.mp3" --cli agy --plain                # transcribe + summarize
pbpaste | summarize - --cli agy --plain                          # clipboard / stdin
```

### Useful flags

- `--extract` — print extracted content (transcript/text) and exit, no summary. URLs only.
- `--slides` — extract slide screenshots from a video (needs `yt-dlp`; native `ffmpeg` faster).
- `--json` — machine-readable output with metrics and diagnostics.
- `--diarize` — speaker-labelled transcript for audio/video (needs `ELEVENLABS_API_KEY` or `OPENAI_API_KEY`).

## Backends

`agy` is the default because it's free and proven on this machine. Others are available:

- `--cli agy` — Antigravity CLI, keyless. **Default.**
- `--cli copilot` / `--cli gemini` — other installed coding CLIs (may hang or return empty; agy is more reliable here).
- `--model google/gemini-3.5-flash` — Gemini API (needs `GEMINI_API_KEY` with billing headroom; the key here has hit its spend cap).

Check what's wired up: `summarize status`.

## Fail fast

Wrap in `timeout` and stop on any error or non-zero exit. "CLI returned empty output" means that backend produced nothing. Switch to `--cli agy` rather than retrying. A `429`/quota error won't clear on retry.

## Setup (only if needed)

- Install: `npm i -g @steipete/summarize` (needs Node 24+).
- `agy` backend: see the `antigravity-cli` skill (`curl -fsSL https://antigravity.google/cli/install.sh | bash`, then sign in).
- Optional media deps: `brew install ffmpeg yt-dlp` (YouTube slides, broader codecs); `brew install tesseract` for `--slides-ocr`.
