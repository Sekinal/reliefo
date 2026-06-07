"""Build the hypsometric albedo (Blender does the relief shading) and, when
streets are enabled, the self-lit emission map that makes the road grid glow
over the 3-D relief. Colour scale is chosen by ``[relief] palette``.
"""
from __future__ import annotations

import json

import numpy as np
from PIL import Image

from ._util import info, step
from .config import Config

try:
    from cmcrameri import cm as _crameri  # perceptually-uniform maps
except Exception:                                  # noqa: BLE001
    _crameri = None

# A spec is either
#   ("cm", crameri_name, reverse, lo, hi)   — a real perceptually-uniform map
#   ("hex", [hex, ...])                      — a hand-mixed ramp
# paired with a gamma (how much terrain stays pale vs goes deep).
PALETTES: dict[str, tuple[tuple, float]] = {
    # DEFAULT — genuine Crameri 'oslo', reversed: pale lowlands -> deep navy.
    "oslo":    (("cm", "oslo", True, 0.04, 0.97), 1.30),
    "lajolla": (("cm", "lajolla", False, 0.05, 0.98), 1.20),   # warm, uniform
    "davos":   (("cm", "davos", True, 0.05, 0.97), 1.25),      # teal, uniform
    "bukavu":  (("cm", "bukavu", False, 0.5, 1.0), 1.0),        # topo multihue
    "blue":    (("hex", ["#eef4f8", "#dbe8f3", "#bdd5ea", "#93b8dd", "#6695cb",
                         "#4172b4", "#274f93", "#183a72", "#0e2a55"]), 1.6),
    "copper":  (("hex", ["#f7f1e7", "#ecdcc2", "#dabd95", "#c39a6b", "#a8784b",
                         "#876035", "#664626", "#46301b", "#291c11"]), 1.55),
    "imhof":   (("hex", ["#3f6b46", "#5f8a4d", "#86a258", "#aeae6a", "#ccb277",
                         "#dcc596", "#e9d8b4", "#f4ead2", "#fbf5e8"]), 0.95),
}
_OSLO_FALLBACK = ["#f4f4f4", "#c6cad2", "#9dadc9", "#7b98c9", "#517bbd",
                  "#285991", "#173d62", "#0f2338", "#060c13"]


def palette(name: str) -> tuple[tuple, float]:
    if name not in PALETTES:
        raise ValueError(f"unknown palette {name!r}; choose from {sorted(PALETTES)}")
    return PALETTES[name]


def ramp(name: str, n: int = 256) -> np.ndarray:
    """A 0..255 RGB lookup table (low -> high) for ``name``."""
    spec, _ = palette(name)
    if spec[0] == "cm" and _crameri is not None:
        _, cname, rev, lo, hi = spec
        cmap = getattr(_crameri, cname)
        xs = np.linspace(lo, hi, n)
        if rev:
            xs = xs[::-1]
        return np.array([cmap(float(x))[:3] for x in xs]) * 255.0
    cols = spec[1] if spec[0] == "hex" else _OSLO_FALLBACK
    rgb = np.array([[int(c[i:i + 2], 16) for i in (1, 3, 5)] for c in cols], float)
    xs = np.linspace(0, 1, len(cols))
    g = np.linspace(0, 1, n)
    return np.stack([np.interp(g, xs, rgb[:, k]) for k in range(3)], axis=1)


def gamma(name: str) -> float:
    return palette(name)[1]


def _hypsometric(dem, vmin, vmax, name) -> np.ndarray:
    lut = ramp(name, 256)
    t = ((dem - vmin) / (vmax - vmin)).clip(0, 1) ** gamma(name)
    return lut[(t * 255).astype(int)].astype(np.uint8)


def _hillshade(dem, az=315.0, alt=45.0, z=0.00012) -> np.ndarray:
    gy, gx = np.gradient(dem * z)
    slope = np.pi / 2 - np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    azr, altr = np.radians(360 - az + 90), np.radians(alt)
    sh = np.sin(altr) * np.sin(slope) + np.cos(altr) * np.cos(slope) * np.cos(azr - aspect)
    return sh.clip(0, 1)


def build(cfg: Config) -> None:
    step("textures")
    meta = json.loads(cfg.meta_json.read_text())
    dem = np.load(cfg.elevation_npy)
    mask = np.load(cfg.mask_npy)
    vmin, vmax = meta["elev_min"], meta["elev_max"]

    alb = _hypsometric(dem, vmin, vmax, cfg.relief.palette)
    Image.fromarray(alb, "RGB").save(cfg.albedo_png)
    info(f"albedo · palette '{cfg.relief.palette}' · {vmin:.0f}–{vmax:.0f} m")

    # street network as an EMISSION map (Blender makes the grid self-lit)
    minor_npy = cfg.data / "roads_minor.npy"
    if cfg.streets.enabled and minor_npy.exists():
        from scipy.ndimage import gaussian_filter, grey_dilation
        minor = np.load(minor_npy).astype(np.float64)
        major = grey_dilation(np.load(cfg.data / "roads_major.npy").astype(np.float64),
                              size=(2, 2))
        road = gaussian_filter(np.maximum(minor * cfg.streets.minor_strength,
                                          major * cfg.streets.major_strength), sigma=0.5)
        road = np.clip(road, 0, 1) * (mask > 0)
        Image.fromarray((road * 255).astype(np.uint8)).save(cfg.emission_png)
        info("street emission map written")
    elif cfg.emission_png.exists():
        cfg.emission_png.unlink()

    # a quick shaded preview to eyeball the cut-out terrain
    hs = _hillshade(dem)[..., None]
    bg = np.array([233, 234, 236], dtype=np.float64)
    prev = (alb.astype(np.float64) * (0.4 + 0.75 * hs)).clip(0, 255)
    prev = np.where(mask[..., None] == 1, prev, bg)
    Image.fromarray(prev.astype(np.uint8), "RGB").save(cfg.data / "preview_shaded.png")
