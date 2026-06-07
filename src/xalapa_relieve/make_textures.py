"""Vintage hypsometric albedo for the municipio, stretched over its actual
elevation range (Blender does the relief shading). Plus a masked, shaded
preview to eyeball the cut-out terrain.
"""
from __future__ import annotations
import json
import numpy as np
from PIL import Image
from . import config as C

# low -> high, evenly spaced; temperate earth tones (no snow at ~1.6 km)
COLORS = ["#33502f", "#4d6b38", "#728c45", "#9a9a54",
          "#b89a5c", "#a87a50", "#8f6f5c", "#c4b8a6"]


def ramp(n=256):
    cols = np.array([[int(c[i:i+2], 16) for i in (1, 3, 5)] for c in COLORS],
                    dtype=np.float64)
    xs = np.linspace(0, 1, len(COLORS))
    g = np.linspace(0, 1, n)
    return np.stack([np.interp(g, xs, cols[:, k]) for k in range(3)], axis=1)


def hypsometric(dem, vmin, vmax):
    lut = ramp(256)
    idx = (((dem - vmin) / (vmax - vmin)).clip(0, 1) * 255).astype(int)
    return lut[idx].astype(np.uint8)


def hillshade(dem, az=315.0, alt=45.0, z=0.00012):
    gy, gx = np.gradient(dem * z)
    slope = np.pi / 2 - np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    azr, altr = np.radians(360 - az + 90), np.radians(alt)
    sh = np.sin(altr) * np.sin(slope) + np.cos(altr) * np.cos(slope) * np.cos(azr - aspect)
    return sh.clip(0, 1)


def main():
    meta = json.loads(C.META_JSON.read_text())
    dem = np.load(C.ELEV_NPY)
    mask = np.load(C.MASK_NPY)
    vmin, vmax = meta["elev_min"], meta["elev_max"]
    alb = hypsometric(dem, vmin, vmax)
    Image.fromarray(alb, "RGB").save(C.ALBEDO_PNG)

    hs = hillshade(dem)[..., None]
    paper = np.array([216, 206, 189], dtype=np.float64)
    prev = (alb * (0.35 + 0.8 * hs)).clip(0, 255)
    prev = np.where(mask[..., None] == 1, prev, paper)
    Image.fromarray(prev.astype(np.uint8), "RGB").save(C.DATA / "preview_shaded.png")
    print(f"albedo + preview  range {vmin:.0f}..{vmax:.0f} m")


if __name__ == "__main__":
    main()
