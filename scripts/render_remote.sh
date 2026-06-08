#!/usr/bin/env bash
# Render every variant at L40S quality (8K, high samples, full-native LiDAR mesh).
# Run ON the remote:  bash scripts/render_remote.sh
set -u
cd "$(dirname "$0")/.."
UV=~/.local/bin/uv
RES=${RES:-8000}; SAMP=${SAMP:-512}; SUB=${SUB:-8000}
Q="--res $RES --samples $SAMP --subdiv $SUB --skip-dem"

CITIES=(xalapa cordoba orizaba coatzacoalcos poza_rica boca_del_rio minatitlan \
        tuxpan san_andres_tuxtla papantla coatepec perote catemaco huatusco \
        zongolica xico veracruz)

for slug in "${CITIES[@]}"; do
  cfg="examples/${slug}.toml"
  [ -f "$cfg" ] || { echo "!! no $cfg"; continue; }
  echo "=== $slug  A (clean)  $(date +%H:%M:%S) ==="
  $UV run reliefo build "$cfg" $Q --clean 2>&1 | grep -E "blender ·|saved|✓|Error|RuntimeError" | tail -2
  echo "=== $slug  B+C (streets)  $(date +%H:%M:%S) ==="
  $UV run reliefo build "$cfg" $Q 2>&1 | grep -E "blender ·|rasterised|zone labels|saved|✓|Error|RuntimeError" | tail -3
done
echo "=== ALL DONE  $(date +%H:%M:%S) ==="
