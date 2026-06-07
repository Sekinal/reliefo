"""Vintage hypsometric albedo for the municipio, stretched over its actual
elevation range (Blender does the relief shading). Plus a masked, shaded
preview to eyeball the cut-out terrain.
"""
from __future__ import annotations
import json
import numpy as np
from PIL import Image
from . import config as C

# Clean monochrome hypsometric (joewdavies / Greece style): pale lowlands
# -> deep saturated blue highlands. Strong, modern, minimal.
COLORS = ["#eef4f8", "#dbe8f3", "#bdd5ea", "#93b8dd",
          "#6695cb", "#4172b4", "#274f93", "#183a72", "#0e2a55"]
GAMMA = 1.6    # keep the low-mid ground pale; reserve deep blue for the heights


def ramp(n=256):
    cols = np.array([[int(c[i:i+2], 16) for i in (1, 3, 5)] for c in COLORS],
                    dtype=np.float64)
    xs = np.linspace(0, 1, len(COLORS))
    g = np.linspace(0, 1, n)
    return np.stack([np.interp(g, xs, cols[:, k]) for k in range(3)], axis=1)


def hypsometric(dem, vmin, vmax):
    lut = ramp(256)
    t = ((dem - vmin) / (vmax - vmin)).clip(0, 1) ** GAMMA
    return lut[(t * 255).astype(int)].astype(np.uint8)


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
    bg = np.array([233, 234, 236], dtype=np.float64)
    prev = (alb.astype(np.float64) * (0.4 + 0.75 * hs)).clip(0, 255)
    prev = np.where(mask[..., None] == 1, prev, bg)
    Image.fromarray(prev.astype(np.uint8), "RGB").save(C.DATA / "preview_shaded.png")
    print(f"albedo + preview  range {vmin:.0f}..{vmax:.0f} m  (monochrome)")


if __name__ == "__main__":
    main()
