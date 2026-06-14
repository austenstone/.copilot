#!/usr/bin/env bash
# Generate video with Google's Veo models via the Gemini predictLongRunning REST API.
# Docs: https://ai.google.dev/gemini-api/docs/video#rest
#
# Usage:
#   gen.sh -o out.mp4 "a prompt"                       # text -> video
#   gen.sh -o out.mp4 -i start.png "prompt"            # image -> video (animate starting frame)
#   gen.sh -o out.mp4 -i first.png -L last.png "..."   # first+last frame interpolation (Veo 3.1)
#   gen.sh -o out.mp4 -a 9:16 -r 1080p -d 8 "prompt"   # portrait, 1080p, 8s
#   MODEL=veo-3.1-fast-generate-preview gen.sh -o out.mp4 "prompt"
#
# Requires: GEMINI_API_KEY in env. curl, jq, python3 on PATH.
set -euo pipefail

MODEL="${MODEL:-veo-3.1-generate-preview}"
BASE_URL="https://generativelanguage.googleapis.com/v1beta"
OUT=""
IMAGE=""
LAST=""
ASPECT=""
RESOLUTION=""
DURATION=""

while getopts "o:i:L:a:r:d:m:" opt; do
  case "$opt" in
    o) OUT="$OPTARG" ;;
    i) IMAGE="$OPTARG" ;;
    L) LAST="$OPTARG" ;;
    a) ASPECT="$OPTARG" ;;
    r) RESOLUTION="$OPTARG" ;;
    d) DURATION="$OPTARG" ;;
    m) MODEL="$OPTARG" ;;
    *) echo "usage: gen.sh -o out.mp4 [-i start.png] [-L last.png] [-a 16:9|9:16] [-r 720p|1080p|4k] [-d 4|6|8] [-m model] \"prompt\"" >&2; exit 2 ;;
  esac
done
shift $((OPTIND - 1))

PROMPT="${*:-}"
[[ -z "$OUT" ]] && { echo "error: -o output path required" >&2; exit 2; }
[[ -z "$PROMPT" ]] && { echo "error: no prompt given" >&2; exit 2; }
[[ -z "${GEMINI_API_KEY:-}" ]] && { echo "error: GEMINI_API_KEY not set" >&2; exit 2; }

REQ_FILE="$(mktemp)"
trap 'rm -f "$REQ_FILE"' EXIT

PROMPT="$PROMPT" IMAGE="$IMAGE" LAST="$LAST" ASPECT="$ASPECT" \
RESOLUTION="$RESOLUTION" DURATION="$DURATION" python3 - > "$REQ_FILE" <<'PY'
import os, json, base64, mimetypes

def img(p):
    mime = mimetypes.guess_type(p)[0] or "image/png"
    with open(p, "rb") as f:
        return {"inlineData": {"mimeType": mime, "data": base64.b64encode(f.read()).decode()}}

instance = {"prompt": os.environ["PROMPT"]}
if os.environ.get("IMAGE"):
    instance["image"] = img(os.environ["IMAGE"])
if os.environ.get("LAST"):
    instance["lastFrame"] = img(os.environ["LAST"])

params = {}
for env, key in (("ASPECT", "aspectRatio"), ("RESOLUTION", "resolution"), ("DURATION", "durationSeconds")):
    v = os.environ.get(env)
    if v:
        params[key] = int(v) if key == "durationSeconds" else v

body = {"instances": [instance]}
if params:
    body["parameters"] = params
print(json.dumps(body))
PY

KICKOFF=$(curl -sS -X POST \
  "${BASE_URL}/models/${MODEL}:predictLongRunning" \
  -H "x-goog-api-key: ${GEMINI_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "@${REQ_FILE}")

KICK_ERR=$(echo "$KICKOFF" | jq -r '.error.message // empty')
[[ -n "$KICK_ERR" ]] && { echo "error: ${KICK_ERR}" >&2; exit 1; }
OP_NAME=$(echo "$KICKOFF" | jq -r '.name // empty')
[[ -z "$OP_NAME" ]] && { echo "error: no operation name returned: $(echo "$KICKOFF" | head -c 800)" >&2; exit 1; }
echo "started: ${OP_NAME}" >&2

while true; do
  STATUS=$(curl -sS -H "x-goog-api-key: ${GEMINI_API_KEY}" "${BASE_URL}/${OP_NAME}")
  ERR=$(echo "$STATUS" | jq -r '.error.message // empty')
  [[ -n "$ERR" ]] && { echo "error: ${ERR}" >&2; exit 1; }
  if [[ "$(echo "$STATUS" | jq -r '.done // false')" == "true" ]]; then
    URI=$(echo "$STATUS" | jq -r '.response.generateVideoResponse.generatedSamples[0].video.uri // .response.generateVideoResponse.generatedVideos[0].video.uri // empty')
    [[ -z "$URI" ]] && { echo "error: done but no video uri: $(echo "$STATUS" | head -c 800)" >&2; exit 1; }
    curl -sS -L -o "$OUT" -H "x-goog-api-key: ${GEMINI_API_KEY}" "$URI"
    echo "$OUT"
    exit 0
  fi
  echo "waiting for video generation..." >&2
  sleep 10
done
