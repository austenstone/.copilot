---
name: gemini-image
description: "Generate or edit images with Google's Gemini API (Nano Banana / Imagen) via REST. Use when the user wants to create an image, illustration, hero graphic, icon, photo, or visual asset from a text prompt, or edit/compose/restyle existing image(s) with a prompt. Triggers: 'generate an image', 'make a picture', 'create a hero image', 'nano banana', 'gemini image', 'edit this image', 'add X to this photo', 'image for my blog'. Produces real PNG/JPEG files on disk. Requires GEMINI_API_KEY in env."
---

# Gemini Image Generation

Generate and edit images with the Gemini REST API. Two bundled scripts, both tested working. Output is a real image file written to the path you pass with `-o`.

## Prereqs

- `GEMINI_API_KEY` must be set in the environment (the scripts read it). Check with `[ -n "$GEMINI_API_KEY" ] && echo set`.
- `curl` and `python3` on PATH (python3 only used for JSON assembly + base64 decode, no pip installs).
- zsh gotcha: never name a shell variable `path` in a loop. It is tied to `$PATH` and will wipe your PATH. Use `p` or `url`.

## Models

Override the model on any script with `-m <model>` or `MODEL=<model>`.

(as of June 2026)
> **Best model for Gemini image gen today: `gemini-3-pro-image` (Nano Banana Pro).** This is the highest-quality option as of this skill's writing (June 2026). Don't go re-checking the API for newer models on every run; just use this unless the user asks otherwise.

## Which script

- **`scripts/gen.sh`** — `generateContent` API. Use for text-to-image AND for editing/composing with reference images (`-i ref.png`, repeatable). This is the simplest path and the one to default to for a single image.
- **`scripts/gen-story.sh`** — generates a SET of images in ONE conversation so they share style, palette, character, and world. Use whenever you need 2+ images that belong together (a blog's hero + section art, a step-by-step series, a recurring mascot). This is Google's officially recommended way to get consistency: it keeps the multi-turn `contents` history and appends each generated image back as a `model` turn before asking for the next scene. Defaults to `gemini-3-pro-image` for the tightest consistency.
- **`scripts/gen-interactions.sh`** — newer Interactions API (`v1beta/interactions`, stateful, OpenAI-Responses-style). Use when the user specifically wants the Interactions API or multi-turn/stateful behavior. Text prompt only in this wrapper.

### Consistency: always prefer one conversation for a set

When the user wants multiple images that tell one story or share a look, do NOT fire independent one-shot `gen.sh` calls (each call starts cold and drifts). Use `gen-story.sh` with a single shared `-s STYLE` string and one scene prompt per image. Gemini's docs are explicit: "Chat or multi-turn conversation is the recommended way to iterate on images," and the model maintains style/character/context across turns. For brand or character lock, seed a reference image into the first turn with `-i`.

## Usage

Text to image:
```bash
scripts/gen.sh -o hero.png "editorial tech illustration, dark slate background, teal and amber accents, no text, 16:9"
```

Edit / compose with one or more reference images:
```bash
scripts/gen.sh -o out.png -i logo.png -i bg.png "place the logo centered on the background, soft drop shadow"
```

Higher quality model:
```bash
scripts/gen.sh -m gemini-3-pro-image -o hero.png "..."
```

Interactions API:
```bash
scripts/gen-interactions.sh -o out.png "a glossy red apple on a white studio background"
```

Consistent series (one conversation, shared style) — use this for blog hero + section art:
```bash
STYLE="editorial flat-vector tech illustration, dark slate background, teal and amber accents, no text, 16:9"
scripts/gen-story.sh -d ./out -s "$STYLE" -b oidc \
  "a silver bullet shattering against a glass shield" \
  "two sealed chambers, a chaotic dirty build room and a clean secure deploy vault, an artifact passing between them" \
  "a kernel firewall on a runner blocking a rogue outbound packet while allowed packets pass"
# writes ./out/oidc-1.png, oidc-2.png, oidc-3.png, all matching
```
Seed a brand/character into the whole set by adding `-i logo.png` (rides in the first turn).

After generating, view the result with the `view_image` tool to confirm it matches intent before wiring it into anything. To iterate, feed the output back in as `-i` with a new prompt.

## Prompt tips

- Be specific about subject, style, lighting, palette, and aspect/orientation. Say "no text" if you don't want garbled words.
- For blog/hero art: name a style ("flat vector", "editorial illustration", "photorealistic"), a background, and an accent palette. Keep it clean and on-brand.
- Editing: describe the change AND what to preserve ("keep everything else identical").

## Output format note

Gemini commonly returns JPEG even when you name the file `.png`. Both scripts now auto-correct this: they sniff the real bytes and `sips`-convert so the file's actual format matches its extension. This matters because tools that read the image back (image viewers, the chat `view_image` tool, LLM APIs) trust the extension for the media type. A `.png` that's secretly JPEG gets rejected with errors like `image/png media type, but the image appears to be a image/jpeg image`. If `sips` is unavailable, the script keeps the real bytes and the extension may not match, so prefer naming outputs `.png` on macOS where conversion just works.

## Response shapes (for debugging)

- `generateContent`: image at `candidates[].content.parts[].inlineData.data` (base64).
- Interactions: image at `steps[type=model_output].content[].data` (base64); there is also a `thought` step.

## Failure modes

- `404 ... is not found for API version v1beta`: dead/wrong model name. Use a current ID from the table above (the old `gemini-2.5-flash-image-preview` is retired).
- `GEMINI_API_KEY not set`: export the key first.
- `no image in response`: the model returned text only. Make the prompt clearly an image request, or set `responseModalities: ["IMAGE"]` (gen.sh already does).
