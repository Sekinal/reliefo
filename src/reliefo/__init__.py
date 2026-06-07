"""reliefo — clean monochrome shaded-relief posters of any Mexican municipio.

Point it at a municipio (a TOML config: bounding box + boundary polygon + a DEM
source) and it fetches the elevation data, cuts the terrain to the municipal
boundary, renders a raised-relief plate in Blender (Cycles/OptiX) and composes a
minimal poster — in the spirit of @joewdavies' country plates.

The pipeline is config-driven; nothing about Xalapa is hard-coded. See
``examples/xalapa.toml`` for the worked example and the README for a tutorial on
getting the data for your own municipio.
"""
from __future__ import annotations

from .config import Config, load_config

__version__ = "0.2.0"
__all__ = ["Config", "load_config", "__version__"]
