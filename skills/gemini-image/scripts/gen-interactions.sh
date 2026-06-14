#!/usr/bin/env bash
# Generate an image with the Gemini Interactions API (newer, stateful, OpenAI-Responses-style).
# Docs: https://ai.google.dev/gemini-api/docs/interactions/image-generation
#
# Usage:
#   gen-interactions.sh -o out.png "a prompt"
#   MODEL=gemini-3-pro-image gen-interactions.sh -o out.png "a prompt"
#
# Requires: GEMINI_API_KEY in env. curl, python3 on PATH.
# Image lives in the model_output step's content[] as { mime_type, data(base64) }.
# For multi-image editing/reference inputs prefer gen.sh (generateContent).
set -euo pipefail

MODEL="${MODEL:-gemini-3.1-flash-image}"   # Nano Banana 2 (newest). Alt: gemini-3-pro-image
OUT="out.png"

while getopts "o:m:" opt; do
  case "$opt" in
    o) OUT="$OPTARG" ;;
    m) MODEL="$OPTARG" ;;
    *) echo "usage: gen-interactions.sh -o out.png [-m model] \"prompt\"" >&2; exit 2 ;;
  esac
done
shift $((OPTIND - 1))

PROMPT="${*:-}"
[[ -z "$PROMPT" ]] && { echo "error: no prompt given" >&2; exit 2; }
[[ -z "${GEMINI_API_KEY:-}" ]] && { echo "error: GEMINI_API_KEY not set" >&2; exit 2; }

REQ_FILE="$(mktemp)"; RESP_FILE="$(mktemp)"
trap 'rm -f "$REQ_FILE" "$RESP_FILE"' EXIT

MODEL="$MODEL" PROMPT="$PROMPT" python3 - > "$REQ_FILE" <<'PY'
import os, sys, json
json.dump({"model": os.environ["MODEL"], "input": os.environ["PROMPT"]}, sys.stdout)
PY

curl -sS -X POST \
  "https://generativelanguage.googleapis.com/v1beta/interactions" \
  -H "x-goog-api-key: ${GEMINI_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "@${REQ_FILE}" -o "$RESP_FILE"

OUT="$OUT" RESP_FILE="$RESP_FILE" python3 - <<'PY'
import os, sys, json, base64, subprocess
resp = json.load(open(os.environ["RESP_FILE"]))
if "error" in resp:
    print("API error:", json.dumps(resp["error"]), file=sys.stderr); sys.exit(1)
out = os.environ["OUT"]

def save(raw, out):
    # Gemini often returns JPEG even when out ends in .png. Make the file's actual
    # format match its extension so downstream readers don't choke on a mime mismatch.
    ext = os.path.splitext(out)[1].lower().lstrip(".") or "png"
    fmt = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png"}.get(ext, "png")
    is_jpeg = raw[:3] == b"\xff\xd8\xff"
    is_png = raw[:8] == b"\x89PNG\r\n\x1a\n"
    actual = "jpeg" if is_jpeg else ("png" if is_png else None)
    if actual == fmt or actual is None:
        open(out, "wb").write(raw)
        return
    tmp = out + (".jpg" if actual == "jpeg" else ".png")
    open(tmp, "wb").write(raw)
    try:
        subprocess.run(["sips", "-s", "format", fmt, tmp, "--out", out],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.remove(tmp)
    except Exception:
        os.replace(tmp, out)  # conversion unavailable; keep real bytes

for step in resp.get("steps", []):
    if step.get("type") != "model_output":
        continue
    for c in step.get("content", []):
        if c.get("data"):
            save(base64.b64decode(c["data"]), out)
            print(out); sys.exit(0)
print("no image in response:", json.dumps(resp)[:800], file=sys.stderr); sys.exit(1)
PY
