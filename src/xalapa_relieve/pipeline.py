"""End-to-end build of the Xalapa raised-relief plate.

Steps:
  1. fetch_dem      Copernicus GLO-30 -> heightmap + elevation + meta
  2. make_textures  vintage hypsometric albedo (+ shaded preview)
  3. blender        displace + light + render (Cycles/OptiX) -> RGBA plate
  4. compose        aged-paper plate: cartouche, legend, graticule, labels

Usage:
  uv run xalapa-relieve              # full build, final resolution
  uv run xalapa-relieve --draft      # fast low-res preview
  uv run xalapa-relieve --skip-dem   # reuse cached DEM
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BLENDER_SCRIPT = ROOT / "src" / "xalapa_relieve" / "blender_render.py"


def run_blender(res_x: int, samples: int):
    cmd = ["blender", "--background", "--factory-startup",
           "--python", str(BLENDER_SCRIPT), "--", str(res_x), str(samples)]
    print(f"[blender] render {res_x}px samples={samples}")
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--draft", action="store_true", help="fast low-res preview")
    ap.add_argument("--skip-dem", action="store_true", help="reuse cached DEM")
    ap.add_argument("--res", type=int, default=None)
    ap.add_argument("--samples", type=int, default=None)
    a = ap.parse_args()

    res = a.res or (1400 if a.draft else 3400)
    samples = a.samples or (48 if a.draft else 160)

    from . import fetch_dem, make_textures, compose
    if not a.skip_dem:
        fetch_dem.main()
    make_textures.main()
    run_blender(res, samples)
    compose.main()
    print("\nDone ->", ROOT / "output" / "xalapa_relieve_1953.png")


if __name__ == "__main__":
    sys.exit(main())
