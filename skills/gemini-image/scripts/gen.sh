#!/usr/bin/env bash
# Generate or edit images with the Gemini generateContent REST API (Nano Banana family).
# Docs: https://ai.google.dev/gemini-api/docs/image-generation\#rest
#
# Usage:
#   gen.sh -o out.png "a prompt"                          # text -> image
#   gen.sh -o out.png -i ref1.png -i ref2.png "prompt"    # image(s) + text -> image (edit/compose)
#   MODEL=gemini-3-pro-image gen.sh -o out.png "prompt"   # override model
#
# Requires: GEMINI_API_KEY in env. curl, python3 on PATH.
set -euo pipefail

MODEL="${MODEL:-gemini-3.1-flash-image}"   # Nano Banana 2 (newest). Alt: gemini-3-pro-image, gemini-2.5-flash-image
OUT="out.png"
INPUTS=()

while getopts "o:i:m:" opt; do
  case "$opt" in
    o) OUT="$OPTARG" ;;
    i) INPUTS+=("$OPTARG") ;;
    m) MODEL="$OPTARG" ;;
    *) echo "usage: gen.sh -o out.png [-i ref.png ...] [-m model] \"prompt\"" >&2; exit 2 ;;
  esac
done
shift $((OPTIND - 1))

PROMPT="${*:-}"
[[ -z "$PROMPT" ]] && { echo "error: no prompt given" >&2; exit 2; }
[[ -z "${GEMINI_API_KEY:-}" ]] && { echo "error: GEMINI_API_KEY not set" >&2; exit 2; }

REQ_FILE="$(mktemp)"; RESP_FILE="$(mktemp)"
trap 'rm -f "$REQ_FILE" "$RESP_FILE"' EXIT

PROMPT="$PROMPT" python3 - "${INPUTS[@]:-}" > "$REQ_FILE" <<'PY'
import os, sys, json, base64, mimetypes
parts = []
for p in sys.argv[1:]:
    if not p:
        continue
    mime = mimetypes.guess_type(p)[0] or "image/png"
    with open(p, "rb") as f:
        parts.append({"inline_data": {"mime_type": mime, "data": base64.b64encode(f.read()).decode()}})
parts.append({"text": os.environ["PROMPT"]})
json.dump({"contents": [{"role": "user", "parts": parts}],
           "generationConfig": {"responseModalities": ["IMAGE"]}}, sys.stdout)
PY

curl -sS -X POST \
  "https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent" \
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

for cand in resp.get("candidates", []):
    for part in cand.get("content", {}).get("parts", []):
        d = part.get("inlineData") or part.get("inline_data")
        if d and d.get("data"):
            save(base64.b64decode(d["data"]), out)
            print(out); sys.exit(0)
print("no image in response:", json.dumps(resp)[:800], file=sys.stderr); sys.exit(1)
PY
