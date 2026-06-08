"""End-to-end build: DEM -> (streets) -> (labels) -> textures -> Blender render
-> poster. Each stage is a module with a ``build(cfg)`` entry point.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from . import compose, dem, labels, streets, textures
from ._util import step
from .config import Config

BLENDER_SCRIPT = Path(__file__).parent / "blender_render.py"
EMISSION_COLOR = (1.0, 0.82, 0.48)              # warm lamp glow for streets


def _write_render_cfg(cfg: Config) -> None:
    cfg.render_cfg_json.write_text(json.dumps({
        "data": str(cfg.data), "out": str(cfg.out),
        "exaggeration": cfg.relief.exaggeration,
        "sun_azimuth": cfg.relief.sun_azimuth,
        "sun_altitude": cfg.relief.sun_altitude,
        "sun_energy": cfg.relief.sun_energy,
        "sky": cfg.relief.sky,
        "cam_tilt": cfg.relief.cam_tilt,
        "solidify": cfg.relief.solidify,
        "streets_glow": cfg.streets.glow,
        "emission_color": list(EMISSION_COLOR),
    }))


def _render(cfg: Config, res_x: int, samples: int) -> None:
    step(f"blender · {res_x}px · {samples} samples")
    _write_render_cfg(cfg)
    cmd = ["blender", "--background", "--factory-startup",
           "--python", str(BLENDER_SCRIPT), "--",
           str(cfg.render_cfg_json), str(res_x), str(samples)]
    subprocess.run(cmd, check=True)


def build(cfg: Config, *, draft: bool = False, skip_dem: bool = False,
          clean: bool = False, res: int | None = None,
          samples: int | None = None) -> Path:
    res = res or (1400 if draft else cfg.render.resolution)
    samples = samples or (48 if draft else cfg.render.samples)
    if clean:                                      # variant A: no streets/names
        cfg.streets.enabled = False
        cfg.labels.enabled = False

    if not skip_dem:
        dem.build(cfg)
    if cfg.streets.enabled:
        streets.build(cfg)
    if cfg.labels.enabled:
        labels.build(cfg)
    textures.build(cfg)
    _render(cfg, res, samples)
    compose.build(cfg)
    return cfg.poster_png
