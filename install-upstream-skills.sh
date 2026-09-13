#!/usr/bin/env bash

set -euo pipefail

repository="anthropics/skills"
skills=(
  "skills/docx"
  "skills/pptx"
  "skills/xlsx"
)

if [[ -n "${GH_SKILL_DIR:-}" ]]; then
  target_args=(--dir "${GH_SKILL_DIR}")
else
  target_args=(--agent github-copilot --scope user)
fi

for skill in "${skills[@]}"; do
  install_args=("${repository}" "${skill}")
  if [[ -n "${GH_SKILL_PIN:-}" ]]; then
    install_args+=(--pin "${GH_SKILL_PIN}")
  fi

  gh skill install "${install_args[@]}" \
    "${target_args[@]}" \
    "$@"
done
