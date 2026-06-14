---
name: gemini-video
description: "Generate video with Google's Veo models (Gemini API) via REST. Use when the user wants to create a video clip from a text prompt, animate an image into a video, or make a short cinematic/animation clip with audio. Triggers: 'generate a video', 'make a video', 'veo', 'text to video', 'animate this image', 'image to video', 'create a clip'. Produces a real .mp4 file on disk. Requires GEMINI_API_KEY in env."
---

# Gemini Video Generation (Veo)

Generate video with Google's Veo models over the Gemini REST API. One bundled script. Output is a real `.mp4` written to the path you pass with `-o`.

This is a long-running job: the script kicks off generation, polls until done (usually 30s-3min, up to 6min at peak), then downloads the result. It blocks until the file is on disk.

## Prereqs

- `GEMINI_API_KEY` must be set in the environment. Check with `[ -n "$GEMINI_API_KEY" ] && echo set`.
- `curl`, `jq`, and `python3` on PATH (python3 only for JSON assembly + base64, no pip installs).
- zsh gotcha: never name a shell variable `path` in a loop. It is tied to `$PATH` and will wipe it. Use `p` or `url`.

## Model

Default is `veo-3.1-generate-preview` (Veo 3.1, the best as of June 2026: 720p/1080p/4k, native audio, portrait, image-to-video, reference images, extension). Override with `-m <model>` or `MODEL=<model>`.

| Model | Use |
|---|---|
| `veo-3.1-generate-preview` | best quality, all features (default) |
| `veo-3.1-fast-generate-preview` | faster, cheaper, still has audio + extension |
| `veo-3.1-lite-generate-preview` | cheapest; no reference images, no extension |
| `veo-3.0-generate-001` | stable Veo 3 |
| `veo-2.0-generate-001` | stable Veo 2, silent (no audio) |

Don't go re-checking the API for newer models on every run; use the default unless the user asks otherwise.

## Usage

Text to video:
```bash
scripts/gen.sh -o clip.mp4 "Drone shot following a red convertible along a coastal road at sunset, waves crashing, engine roaring loudly"
```

Portrait + 1080p:
```bash
scripts/gen.sh -o clip.mp4 -a 9:16 -r 1080p "A chef tossing pizza dough, upbeat music, high energy"
```

Image to video (animate a starting frame):
```bash
scripts/gen.sh -o clip.mp4 -i start.png "Panning wide shot of a calico kitten sleeping in the sunshine"
```

First + last frame interpolation (Veo 3.1 only):
```bash
scripts/gen.sh -o clip.mp4 -i first.png -L last.png "the swing slowly empties as she fades into the fog"
```

Faster/cheaper model:
```bash
scripts/gen.sh -m veo-3.1-fast-generate-preview -o clip.mp4 "..."
```

Flags: `-o` output (required), `-i` starting image, `-L` last frame, `-a` aspect (`16:9` default, `9:16`), `-r` resolution (`720p` default, `1080p`, `4k`), `-d` duration seconds (`4`,`6`,`8`), `-m` model.

After generating, the script prints the path. The chat can't preview video inline, so tell the user where it saved.

## Prompt tips

Veo prompts reward cinematic detail. Cover these elements:
- **Subject + action**: who/what and what they're doing.
- **Style**: "film noir", "3D cartoon render", "cinematic", "stop-motion".
- **Camera**: "drone shot", "dolly in", "eye-level close-up", "tracking shot".
- **Composition + lens**: "wide shot", "shallow focus", "macro lens".
- **Ambiance**: "warm tones", "cool blue", "golden hour".
- **Audio** (Veo 3.x generates sound): put dialogue in quotes (`A man murmurs, "this must be it."`), describe SFX ("tires screeching, engine roaring") and ambience ("a faint eerie hum").

## Constraints worth knowing

- Output is 8 seconds at 24fps (4s/6s also valid; must be 8s for 1080p/4k or reference images).
- `1080p` and `4k` only support 8s duration; 4k is pricier and not on Lite.
- Veo 3.x always generates audio; Veo 2 is silent.
- Generated videos are stored server-side for **2 days** only. The script downloads immediately so this rarely matters.
- 1 video per request (Veo 2 can do 2). Region limits apply to person generation in EU/UK/CH/MENA.

## Response shape (for debugging)

- Kickoff: `POST .../models/{model}:predictLongRunning` returns `{ "name": "operations/..." }`.
- Poll: `GET .../{operation_name}` until `.done == true`.
- Download URI lives at `.response.generateVideoResponse.generatedSamples[0].video.uri` (the script also falls back to `.response.generateVideoResponse.generatedVideos[0].video.uri`). Fetch it with the API key header and follow redirects (`curl -L`).

## Failure modes

- `404 ... not found for API version v1beta`: wrong/dead model name. Use one from the table.
- `GEMINI_API_KEY not set`: export the key first.
- Video blocked by safety/audio filter: Veo sometimes refuses (you're not charged). Rework the prompt.
- Polls forever: check the kickoff response for an `error` field; a bad param (e.g. `4k` with non-8s duration) fails the operation.
