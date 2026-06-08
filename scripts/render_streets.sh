#!/usr/bin/env bash
# Add the streets + zone-name (leader-line) treatment to every city poster,
# reusing the cached LiDAR DEMs (--skip-dem). The existing clean poster is
# preserved as <city>_clean.png. (Xalapa is handled by examples/xalapa.toml;
# the whole-state Veracruz map is intentionally excluded.)
set -u
cd "$(dirname "$0")/.."

CITIES=(cordoba orizaba coatzacoalcos poza_rica boca_del_rio minatitlan tuxpan \
        san_andres_tuxtla papantla coatepec perote catemaco huatusco zongolica xico)

for slug in "${CITIES[@]}"; do
  [ -f "output/$slug.png" ] && cp -n "output/$slug.png" "output/${slug}_clean.png"
  echo "=== $slug  $(date +%H:%M:%S) ==="
  uv run reliefo build "examples/$slug.toml" --skip-dem 2>&1 \
    | grep -E "rasterised|zone labels|leader|saved /home|✓|Error|RuntimeError" \
    || echo "  !! $slug FAILED"
done
echo "=== ALL DONE  $(date +%H:%M:%S) ==="
