#!/usr/bin/env bash
# Render every Veracruz city poster in importance order (full 4K LiDAR).
# Skips any whose output already exists. Run from the repo root:
#   bash scripts/render_all.sh
set -u
cd "$(dirname "$0")/.."

# importance order (Veracruz handled separately — no clean OSM municipio polygon)
CITIES=(cordoba orizaba coatzacoalcos poza_rica boca_del_rio minatitlan tuxpan \
        san_andres_tuxtla papantla coatepec perote catemaco huatusco zongolica xico)

for slug in "${CITIES[@]}"; do
  if [ -f "output/$slug.png" ]; then
    echo "=== skip $slug (already rendered) ==="
    continue
  fi
  echo "=== $slug  $(date +%H:%M:%S) ==="
  uv run reliefo build "examples/$slug.toml" 2>&1 \
    | grep -E "discovered|px inside|saved /home|done ->|✓|Error|RuntimeError|Traceback" \
    || echo "  !! $slug FAILED"
done
echo "=== ALL DONE  $(date +%H:%M:%S) ==="
