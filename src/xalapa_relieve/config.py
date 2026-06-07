"""Shared configuration for the Xalapa raised-relief map.

The plate is cut to the **municipio of Xalapa** (clave 30087) so only Xalapa
floats on the paper — like the islands of the 1953 Japan plate.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUT = ROOT / "output"
DATA.mkdir(exist_ok=True)
OUT.mkdir(exist_ok=True)

# Municipio de Xalapa bounding box (+ small margin) -> the render frame.
BBOX = dict(west=-96.978, east=-96.792, south=19.478, north=19.606)
RES_M = 10                      # metres/pixel (GLO-30 resampled, smooth)

MUN_GEOJSON = DATA / "xalapa_mun.geojson"
XALAPA = (-96.9170, 19.5285)    # Parque Juarez

HEIGHT_PNG = DATA / "heightmap_16bit.png"
ALBEDO_PNG = DATA / "albedo_hypsometric.png"
ELEV_NPY = DATA / "elevation.npy"
MASK_NPY = DATA / "mask.npy"
META_JSON = DATA / "meta.json"
RENDER_PNG = OUT / "xalapa_render.png"
FINAL_PNG = OUT / "xalapa_relieve_1953.png"
