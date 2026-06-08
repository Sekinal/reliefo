#!/usr/bin/env bash
# Render all variants with N cities in parallel so the GPU stays saturated:
# while one city renders on the GPU, the others build their meshes on the CPU.
# Per-slug render outputs make this safe. Resumes (skips finished variants).
#   J=3 RES=8000 SAMP=512 SUB=6000 bash scripts/render_parallel.sh
set -u
cd "$(dirname "$0")/.."
UV=~/.local/bin/uv
RES=${RES:-8000}; SAMP=${SAMP:-512}; SUB=${SUB:-6000}; J=${J:-3}
Q="--res $RES --samples $SAMP --subdiv $SUB --skip-dem"

if [ $# -gt 0 ]; then
  CITIES=("$@")
else
  CITIES=(xalapa cordoba orizaba coatzacoalcos poza_rica boca_del_rio minatitlan \
          tuxpan san_andres_tuxtla papantla coatepec perote catemaco huatusco \
          zongolica xico veracruz)
fi

render_one() {
  local slug=$1 cfg="examples/$1.toml"
  [ -f "$cfg" ] || { echo "!! no $cfg"; return; }
  if [ ! -f "output/${slug}.png" ]; then
    echo "[$(date +%H:%M:%S)] $slug A  start"
    $UV run reliefo build "$cfg" $Q --clean >"output/_log_${slug}_A.txt" 2>&1 \
      && echo "[$(date +%H:%M:%S)] $slug A  done" || echo "!! $slug A FAILED"
  fi
  if [ ! -f "output/${slug}_streets_names.png" ]; then
    echo "[$(date +%H:%M:%S)] $slug BC start"
    $UV run reliefo build "$cfg" $Q >"output/_log_${slug}_BC.txt" 2>&1 \
      && echo "[$(date +%H:%M:%S)] $slug BC done" || echo "!! $slug BC FAILED"
  fi
}

for slug in "${CITIES[@]}"; do
  render_one "$slug" &
  while [ "$(jobs -rp | wc -l)" -ge "$J" ]; do wait -n; done
done
wait
echo "=== ALL DONE $(date +%H:%M:%S) ==="
