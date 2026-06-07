"""Shared configuration for the Xalapa raised-relief map."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUT = ROOT / "output"
DATA.mkdir(exist_ok=True)
OUT.mkdir(exist_ok=True)

# Region framing: Cofre de Perote (4,282 m, W) -> Xalapa -> Gulf slope (E).
# West-east gradient gives dramatic hypsometric relief.
BBOX = dict(west=-97.34, east=-96.42, south=19.24, north=19.82)
ZOOM = 12                      # AWS Terrarium tiles (~30 m at this latitude)

# Xalapa city centre (Parque Juarez) for an annotation marker.
XALAPA = (-96.9170, 19.5285)
COFRE = (-97.150, 19.492)      # Cofre de Perote summit

# Files
HEIGHT_PNG = DATA / "heightmap_16bit.png"
ALBEDO_PNG = DATA / "albedo_hypsometric.png"
ELEV_NPY = DATA / "elevation.npy"
META_JSON = DATA / "meta.json"
RENDER_PNG = OUT / "xalapa_render.png"
FINAL_PNG = OUT / "xalapa_relieve_1953.png"
