"""Build a vintage hypsometric albedo texture (flat colour by elevation;
Blender adds the relief shading) plus a quick numpy hillshade preview to
sanity-check the DEM.
"""
from __future__ import annotations
import json
import numpy as np
from PIL import Image
from . import config as C

# Vintage hypsometric control points: (elevation_m, R, G, B) — muted earth
# tones in the spirit of the 1953 Geological Survey plate.
STOPS = [
    (-30,  "#8a9b86"),   # near sea level — soft grey-green
    (150,  "#9aa977"),   # lowlands — sage
    (450,  "#bcbb78"),   # foothills — olive yellow
    (850,  "#d2bd74"),   # — wheat
    (1250, "#cfa45f"),   # Xalapa belt — warm ochre
    (1700, "#c2814e"),   # — terracotta
    (2300, "#a85f3f"),   # — brick
    (2950, "#824a3c"),   # — dark sienna
    (3550, "#6f4f54"),   # high — brown-violet
    (4000, "#9c8e86"),   # — bare rock grey
    (4300, "#e6ded2"),   # summit — pale snow
]


def hex2rgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float64)


def hypsometric(dem):
    elevs = np.array([s[0] for s in STOPS])
    cols = np.stack([hex2rgb(s[1]) for s in STOPS])
    out = np.empty((*dem.shape, 3), dtype=np.float64)
    for c in range(3):
        out[:, :, c] = np.interp(dem, elevs, cols[:, c])
    return out.clip(0, 255).astype(np.uint8)


def hillshade(dem, az=315.0, alt=45.0, z=0.00004):
    # quick preview shading (Blender does the real lighting)
    gy, gx = np.gradient(dem * z)
    slope = np.pi / 2.0 - np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    azr, altr = np.radians(360 - az + 90), np.radians(alt)
    sh = np.sin(altr) * np.sin(slope) + np.cos(altr) * np.cos(slope) * \
        np.cos(azr - aspect)
    return (255 * (sh.clip(0, 1))).astype(np.uint8)


def main():
    dem = np.load(C.ELEV_NPY)
    alb = hypsometric(dem)
    Image.fromarray(alb, "RGB").save(C.ALBEDO_PNG)
    # preview: albedo * hillshade so we can eyeball the terrain
    hs = hillshade(dem).astype(np.float64) / 255.0
    prev = (alb.astype(np.float64) * (0.35 + 0.75 * hs[..., None])).clip(0, 255)
    Image.fromarray(prev.astype(np.uint8), "RGB").save(C.DATA / "preview_shaded.png")
    print("elev range:", float(dem.min()), float(dem.max()))
    print("saved:", C.ALBEDO_PNG.name, "preview_shaded.png")


if __name__ == "__main__":
    main()
