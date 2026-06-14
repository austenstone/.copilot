#!/usr/bin/env bash
# Generate a SET of images in ONE conversation so they share style, palette, and
# world. This is Google's recommended way to keep images consistent: keep the
# multi-turn `contents` history and append each generated image back as a `model`
# turn before asking for the next scene.
# Docs: https://ai.google.dev/gemini-api/docs/image-generation (see "multi-turn")
#
# Usage:
#   gen-story.sh -d OUTDIR -s "shared style string" "scene 1 prompt" "scene 2 prompt" ...
#   gen-story.sh -d OUTDIR -s "STYLE" -b hero -i brand.png "scene 1" "scene 2"
#
# Flags:
#   -d DIR     output directory (created if missing). Default: current dir.
#   -s STYLE   shared style string appended to every scene prompt (the glue).
#   -b BASE    output basename. Files are DIR/BASE-01.png, BASE-02.png, ...
#              Default basename: scene.
#   -i REF     reference image seeded into the FIRST turn (repeatable). Use for
#              brand/logo/character lock so the whole set inherits it.
#   -m MODEL   model id. Default gemini-3-pro-image (best consistency).
#
# Each positional arg is one scene -> one output file, generated in order, each
# one seeing all prior prompts AND prior generated images for continuity.
#
# Requires: GEMINI_API_KEY in env. curl, python3 on PATH.
set -euo pipefail

MODEL="${MODEL:-gemini-3-pro-image}"   # Pro = strongest cross-image consistency
OUTDIR="."
STYLE=""
BASE="scene"
REFS=()

while getopts "d:s:b:i:m:" opt; do
  case "$opt" in
    d) OUTDIR="$OPTARG" ;;
    s) STYLE="$OPTARG" ;;
    b) BASE="$OPTARG" ;;
    i) REFS+=("$OPTARG") ;;
    m) MODEL="$OPTARG" ;;
    *) echo "usage: gen-story.sh -d DIR -s STYLE [-b base] [-i ref ...] [-m model] \"scene1\" \"scene2\" ..." >&2; exit 2 ;;
  esac
done
shift $((OPTIND - 1))

[[ $# -eq 0 ]] && { echo "error: no scene prompts given" >&2; exit 2; }
[[ -z "${GEMINI_API_KEY:-}" ]] && { echo "error: GEMINI_API_KEY not set" >&2; exit 2; }

mkdir -p "$OUTDIR"

MODEL="$MODEL" OUTDIR="$OUTDIR" STYLE="$STYLE" BASE="$BASE" \
NREFS="${#REFS[@]}" python3 - "${REFS[@]:-}" -- "$@" <<'PY'
import os, sys, json, base64, mimetypes, subprocess, urllib.request

model  = os.environ["MODEL"]
outdir = os.environ["OUTDIR"]
style  = os.environ["STYLE"].strip()
base   = os.environ["BASE"]
nrefs  = int(os.environ["NREFS"])
key    = os.environ["GEMINI_API_KEY"]

argv   = sys.argv[1:]
sep    = argv.index("--")
refs   = [a for a in argv[:sep] if a]
scenes = argv[sep+1:]

url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

def sniff(raw):
    if raw[:3] == b"\xff\xd8\xff": return "jpeg"
    if raw[:8] == b"\x89PNG\r\n\x1a\n": return "png"
    return None

def save(raw, out):
    ext = os.path.splitext(out)[1].lower().lstrip(".") or "png"
    fmt = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png"}.get(ext, "png")
    actual = sniff(raw)
    if actual == fmt or actual is None:
        open(out, "wb").write(raw); return
    tmp = out + (".jpg" if actual == "jpeg" else ".png")
    open(tmp, "wb").write(raw)
    try:
        subprocess.run(["sips", "-s", "format", fmt, tmp, "--out", out],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.remove(tmp)
    except Exception:
        os.replace(tmp, out)

def post(contents):
    body = json.dumps({"contents": contents,
                       "generationConfig": {"responseModalities": ["IMAGE"]}}).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "x-goog-api-key": key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)

# Seed the conversation. Reference images ride along in the first user turn so the
# entire set inherits them (brand, character, palette lock).
contents = []
first_parts = []
for p in refs:
    mime = mimetypes.guess_type(p)[0] or "image/png"
    with open(p, "rb") as f:
        first_parts.append({"inline_data": {"mime_type": mime,
                            "data": base64.b64encode(f.read()).decode()}})

width = len(str(len(scenes)))
for i, scene in enumerate(scenes, 1):
    prompt = scene if not style else f"{scene} {style}"
    # First scene also reminds the model this is a consistent series.
    if i == 1:
        prompt = ("First image in a consistent series. Establish the visual style. "
                  + prompt)
        user_parts = first_parts + [{"text": prompt}]
    else:
        prompt = ("Next image in the SAME series. Keep the identical art style, "
                  "palette, lighting, and line weight as the previous images. " + prompt)
        user_parts = [{"text": prompt}]
    contents.append({"role": "user", "parts": user_parts})

    resp = post(contents)
    if "error" in resp:
        print("API error:", json.dumps(resp["error"]), file=sys.stderr); sys.exit(1)

    img_part = None
    for cand in resp.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            d = part.get("inlineData") or part.get("inline_data")
            if d and d.get("data"):
                img_part = (part, d["data"]); break
        if img_part: break
    if not img_part:
        print(f"no image for scene {i}:", json.dumps(resp)[:600], file=sys.stderr); sys.exit(1)

    out = os.path.join(outdir, f"{base}-{str(i).zfill(width)}.png")
    save(base64.b64decode(img_part[1]), out)
    print(out)

    # Append the model's image as history so the next scene stays consistent.
    contents.append({"role": "model", "parts": [img_part[0]]})
PY
