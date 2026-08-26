#!/usr/bin/env bash
# Download Highcharts assets into vendor/ so index.html can serve them locally.
#
# vendor/ is gitignored on purpose: Highcharts is commercially licensed
# ((c) Highsoft AS, see https://www.highcharts.com/license) and must not be
# redistributed from this public repo. Run this once after cloning.
#
# Sourced from jsDelivr rather than code.highcharts.com, which returns 403
# from some corporate networks.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
mkdir -p vendor

HC="https://cdn.jsdelivr.net/npm/highcharts@13.0.0"
DB="https://cdn.jsdelivr.net/npm/@highcharts/dashboards"
GL="https://cdn.jsdelivr.net/npm/@highcharts/grid-lite@3.0.0"

ASSETS=(
  "highcharts__highcharts.js|$HC/highcharts.js"
  "highcharts__highcharts-more.js|$HC/highcharts-more.js"
  "highcharts__highcharts-3d.js|$HC/highcharts-3d.js"
  "highcharts__modules__stock.js|$HC/modules/stock.js"
  "highcharts__modules__map.js|$HC/modules/map.js"
  "highcharts__modules__gantt.js|$HC/modules/gantt.js"
  "highcharts__modules__exporting.js|$HC/modules/exporting.js"
  "highcharts__modules__accessibility.js|$HC/modules/accessibility.js"
  "highcharts__modules__heatmap.js|$HC/modules/heatmap.js"
  "highcharts__modules__sankey.js|$HC/modules/sankey.js"
  "highcharts__modules__treemap.js|$HC/modules/treemap.js"
  "highcharts__modules__wordcloud.js|$HC/modules/wordcloud.js"
  "highcharts__modules__funnel.js|$HC/modules/funnel.js"
  "highcharts__modules__networkgraph.js|$HC/modules/networkgraph.js"
  "highcharts__modules__solid-gauge.js|$HC/modules/solid-gauge.js"
  "highcharts__modules__annotations.js|$HC/modules/annotations.js"
  "highcharts__modules__drag-panes.js|$HC/modules/drag-panes.js"
  "highcharts__indicators__indicators-all.js|$HC/indicators/indicators-all.js"
  "highcharts__themes__adaptive.js|$HC/themes/adaptive.js"
  "highcharts__dashboards__dashboards.js|$DB/dashboards.js"
  "highcharts__dashboards__modules__layout.js|$DB/modules/layout.js"
  "highcharts__dashboards__css__dashboards.css|$DB/css/dashboards.css"
  "highcharts__grid-lite__grid-lite.js|$GL/grid-lite.js"
  "highcharts__grid-lite__css__grid-lite.css|$GL/css/grid-lite.css"
)

for entry in "${ASSETS[@]}"; do
  name="${entry%%|*}"
  url="${entry#*|}"
  printf '%-48s' "$name"
  if curl -fsSL "$url" -o "vendor/$name"; then
    echo "ok"
  else
    echo "FAILED ($url)"
    exit 1
  fi
done

echo "Done. $(find vendor -type f | wc -l | tr -d ' ') assets in vendor/"
