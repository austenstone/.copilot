---
applyTo: "**/*.sh"
---

- Start with `set -euo pipefail`; quote all expansions (`"${var}"`).
- Pass it through `shellcheck` before declaring done.
- Past ~100 lines or when performance matters, use a real language instead.
- Benchmark with [hyperfine](https://github.com/sharkdp/hyperfine).
