"""Vintage hypsometric albedo for the municipio, stretched over its actual
elevation range (Blender does the relief shading). Plus a masked, shaded
preview to eyeball the cut-out terrain.
"""
from __future__ import annotations
import json
import os
import numpy as np
from PIL import Image
from . import config as C

try:
    from cmcrameri import cm as _crameri          # perceptually-uniform maps
except Exception:                                  # noqa
    _crameri = None

# Colour scales (low -> high), gamma. A spec is either
#   ("cm", crameri_name, reverse, lo, hi)   — the real perceptually-uniform map
#   ("hex", [hex, ...])                      — a hand-mixed ramp
PALETTES = {
    # DEFAULT — the genuine Crameri 'oslo', reversed (pale low -> deep navy):
    # perceptually uniform, clean and modern. The recommended scale.
    "oslo":   (("cm", "oslo", True, 0.04, 0.97), 1.30),
    "lajolla":(("cm", "lajolla", False, 0.05, 0.98), 1.20),   # warm, uniform
    "davos":  (("cm", "davos", True, 0.05, 0.97), 1.25),      # teal, uniform
    "bukavu": (("cm", "bukavu", False, 0.5, 1.0), 1.0),        # topo multihue
    "blue":   (("hex", ["#eef4f8", "#dbe8f3", "#bdd5ea", "#93b8dd", "#6695cb",
                         "#4172b4", "#274f93", "#183a72", "#0e2a55"]), 1.6),
    "copper": (("hex", ["#f7f1e7", "#ecdcc2", "#dabd95", "#c39a6b", "#a8784b",
                         "#876035", "#664626", "#46301b", "#291c11"]), 1.55),
    "imhof":  (("hex", ["#3f6b46", "#5f8a4d", "#86a258", "#aeae6a", "#ccb277",
                         "#dcc596", "#e9d8b4", "#f4ead2", "#fbf5e8"]), 0.95),
}
_OSLO_FALLBACK = ["#f4f4f4", "#c6cad2", "#9dadc9", "#7b98c9", "#517bbd",
                  "#285991", "#173d62", "#0f2338", "#060c13"]
_SPEC, GAMMA = PALETTES[os.environ.get("PALETTE", "oslo")]


def ramp(n=256):
    if _SPEC[0] == "cm" and _crameri is not None:
        _, name, rev, lo, hi = _SPEC
        cmap = getattr(_crameri, name)
        xs = np.linspace(lo, hi, n)
        if rev:
            xs = xs[::-1]
        return np.array([cmap(float(x))[:3] for x in xs]) * 255.0
    cols = _SPEC[1] if _SPEC[0] == "hex" else _OSLO_FALLBACK
    rgb = np.array([[int(c[i:i+2], 16) for i in (1, 3, 5)] for c in cols], float)
    xs = np.linspace(0, 1, len(cols)); g = np.linspace(0, 1, n)
    return np.stack([np.interp(g, xs, rgb[:, k]) for k in range(3)], axis=1)


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
    alb = hypsometric(dem, vmin, vmax).astype(np.float64)

    alb = alb.clip(0, 255).astype(np.uint8)
    Image.fromarray(alb, "RGB").save(C.ALBEDO_PNG)

    # street network as an EMISSION map: Blender makes the grid self-lit so it
    # glows over the (sharp) relief. Cleared when STREETS is off.
    emi = C.DATA / "streets_emission.png"
    if os.environ.get("STREETS") and (C.DATA / "roads_minor.npy").exists():
        from scipy.ndimage import gaussian_filter, grey_dilation
        minor = np.load(C.DATA / "roads_minor.npy").astype(np.float64)   # thin
        major = grey_dilation(np.load(C.DATA / "roads_major.npy").astype(np.float64),
                              size=(2, 2))
        # minor grid stays faint so the relief shows through; majors a bit brighter
        road = gaussian_filter(np.maximum(minor * 0.30, major * 0.7), sigma=0.5)
        road = np.clip(road, 0, 1) * (mask > 0)
        Image.fromarray((road * 255).astype(np.uint8)).save(emi)
    elif emi.exists():
        emi.unlink()

    hs = hillshade(dem)[..., None]
    bg = np.array([233, 234, 236], dtype=np.float64)
    prev = (alb.astype(np.float64) * (0.4 + 0.75 * hs)).clip(0, 255)
    prev = np.where(mask[..., None] == 1, prev, bg)
    Image.fromarray(prev.astype(np.uint8), "RGB").save(C.DATA / "preview_shaded.png")
    print(f"albedo + preview  range {vmin:.0f}..{vmax:.0f} m  (monochrome)")


if __name__ == "__main__":
    main()
