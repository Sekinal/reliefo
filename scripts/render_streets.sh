#!/usr/bin/env bash
# Render the streets variants for every city, reusing the cached LiDAR DEMs.
# Each build emits B (<city>_streets.png) and C (<city>_streets_names.png);
# variant A (clean) already exists as <city>.png.
set -u
cd "$(dirname "$0")/.."

CITIES=(cordoba orizaba coatzacoalcos poza_rica boca_del_rio minatitlan tuxpan \
        san_andres_tuxtla papantla coatepec perote catemaco huatusco zongolica xico)

for slug in "${CITIES[@]}"; do
  [ -f "output/${slug}_streets_names.png" ] && { echo "=== skip $slug (done) ==="; continue; }
  echo "=== $slug  $(date +%H:%M:%S) ==="
  uv run reliefo build "examples/$slug.toml" --skip-dem 2>&1 \
    | grep -E "Overpass returned|rasterised|zone labels|saved .*_streets|✓|Error|RuntimeError|no LiDAR" \
    || echo "  !! $slug FAILED"
done
echo "=== ALL DONE  $(date +%H:%M:%S) ==="
