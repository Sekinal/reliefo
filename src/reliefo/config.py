"""Typed, validated configuration loaded from a TOML file.

Everything region-specific lives here, so the same code renders any Mexican
municipio. Relative paths in the TOML are resolved against the config file's
directory. See ``examples/xalapa.toml``.
"""
from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ._util import utm_epsg


class BBox(BaseModel):
    """Render frame in WGS84 degrees."""

    model_config = ConfigDict(extra="forbid")
    west: float
    south: float
    east: float
    north: float

    @model_validator(mode="after")
    def _ordered(self) -> BBox:
        if self.east <= self.west or self.north <= self.south:
            raise ValueError("bbox must satisfy west<east and south<north")
        return self

    @property
    def center(self) -> tuple[float, float]:
        return ((self.west + self.east) / 2, (self.south + self.north) / 2)

    def as_dict(self) -> dict[str, float]:
        return {"west": self.west, "south": self.south,
                "east": self.east, "north": self.north}


class MapCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str                                  # used for filenames + default title
    title: str | None = None                   # poster headline (defaults to NAME)
    subtitle: str = ""                         # e.g. "VERACRUZ · MÉXICO"
    slug: str | None = None                    # output filename stem (defaults to name)
    bbox: BBox

    @property
    def headline(self) -> str:
        return self.title if self.title is not None else self.name.upper()


class BoundaryCfg(BaseModel):
    """Polygon the plate is cut to (a municipio outline)."""

    model_config = ConfigDict(extra="forbid")
    file: Path                                 # GeoJSON / GPKG / SHP
    where: str | None = None                   # optional OGR attribute filter


class DemCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["cem", "lidar", "local"] = "cem"
    res_m: float = 10.0                        # output grid (metres/pixel)
    charts: list[str] = Field(default_factory=list)   # source="lidar"
    file: Path | None = None                   # source="local" GeoTIFF
    height_sigma: float = 0.8                  # displacement denoise
    edge_taper_px: float = 14.0                # round the cut rim to the base
    smooth_mask: bool = True                   # tidy the silhouette


class ReliefCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    palette: str = "oslo"                      # crameri name or built-in ramp
    # Vertical exaggeration. 1.0 = true scale. VE is *scale-dependent*: these are
    # large-scale (single-municipio, ~20 km) maps, so keep it ~1 — high VE belongs
    # to small-scale continental maps; on a zoomed-in frame it over-verticalises
    # steep slopes into smooth-shaded "scale"/3D-print render artifacts.
    exaggeration: float = 1.4
    sun_azimuth: float = 318.0
    sun_altitude: float = 42.0
    sun_energy: float = 3.8
    sky: float = 0.6                           # world/ambient strength
    cam_tilt: float = 9.0
    # plate thickness (km). Kept thin: a thick solidify self-intersects at the
    # displaced municipio boundary and erupts into "tower" flap artifacts.
    solidify: float = 0.1


class StreetsCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    osm_file: Path | None = None               # pre-downloaded OSM lines; else Overpass
    minor_strength: float = 0.30               # faint grid
    major_strength: float = 0.70               # brighter arterials
    glow: float = 4.0                          # Blender emission multiplier


class LabelsCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    source: Literal["overpass", "denue", "file"] = "overpass"
    denue_csv: Path | None = None              # source="denue"
    cvemun: str | None = None                  # 3-digit DENUE municipio code
    file: Path | None = None                   # source="file" (GeoJSON points)
    include: list[str] = Field(default_factory=list)   # curated display names
    big: list[str] = Field(default_factory=list)       # larger labels


class RenderCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resolution: int = 4000                     # final width in px
    samples: int = 160                         # Cycles samples


class PathsCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: Path = Path("data")
    out: Path = Path("output")


class Config(BaseModel):
    """The whole job. Build with :func:`load_config`."""

    model_config = ConfigDict(extra="forbid")
    map: MapCfg
    boundary: BoundaryCfg
    dem: DemCfg = Field(default_factory=DemCfg)
    relief: ReliefCfg = Field(default_factory=ReliefCfg)
    streets: StreetsCfg = Field(default_factory=StreetsCfg)
    labels: LabelsCfg = Field(default_factory=LabelsCfg)
    render: RenderCfg = Field(default_factory=RenderCfg)
    paths: PathsCfg = Field(default_factory=PathsCfg)

    # filled in by load_config (not from TOML)
    root: Path = Field(default=Path("."), exclude=True)

    # ---- derived locations ------------------------------------------------
    @property
    def utm(self) -> str:
        return utm_epsg(*self.map.bbox.center)

    @property
    def slug(self) -> str:
        stem = self.map.slug or self.map.name
        return stem.lower().replace(" ", "_")

    @property
    def data(self) -> Path:
        return self.paths.data

    @property
    def out(self) -> Path:
        return self.paths.out

    @property
    def heightmap_png(self) -> Path:
        return self.data / "heightmap_16bit.png"

    @property
    def albedo_png(self) -> Path:
        return self.data / "albedo.png"

    @property
    def emission_png(self) -> Path:
        return self.data / "streets_emission.png"

    @property
    def elevation_npy(self) -> Path:
        return self.data / "elevation.npy"

    @property
    def mask_npy(self) -> Path:
        return self.data / "mask.npy"

    @property
    def meta_json(self) -> Path:
        return self.data / "meta.json"

    @property
    def zones_json(self) -> Path:
        return self.data / "zones.json"

    @property
    def boundary_utm(self) -> Path:
        return self.data / "boundary_utm.gpkg"

    @property
    def render_png(self) -> Path:
        return self.out / "render.png"

    @property
    def points_json(self) -> Path:
        return self.out / "points.json"

    @property
    def render_cfg_json(self) -> Path:
        # the slice of config the Blender subprocess needs
        return self.data / "render_cfg.json"

    @property
    def poster_png(self) -> Path:                  # A: clean (relief + legend)
        return self.out / f"{self.slug}.png"

    @property
    def poster_streets_png(self) -> Path:          # B: + streets
        return self.out / f"{self.slug}_streets.png"

    @property
    def poster_streets_names_png(self) -> Path:    # C: + streets + names
        return self.out / f"{self.slug}_streets_names.png"


def _resolve(p: Path | None, root: Path) -> Path | None:
    if p is None:
        return None
    p = Path(p)
    return p if p.is_absolute() else (root / p).resolve()


def load_config(path: str | Path) -> Config:
    """Load + validate a TOML config, resolving relative paths against its dir."""
    path = Path(path).resolve()
    with path.open("rb") as fh:
        raw = tomllib.load(fh)
    cfg = Config.model_validate(raw)
    cfg.root = path.parent

    # resolve every path against the config directory
    cfg.paths.data = _resolve(cfg.paths.data, cfg.root)  # type: ignore[assignment]
    cfg.paths.out = _resolve(cfg.paths.out, cfg.root)     # type: ignore[assignment]
    cfg.boundary.file = _resolve(cfg.boundary.file, cfg.root)  # type: ignore[assignment]
    cfg.dem.file = _resolve(cfg.dem.file, cfg.root)
    cfg.streets.osm_file = _resolve(cfg.streets.osm_file, cfg.root)
    cfg.labels.denue_csv = _resolve(cfg.labels.denue_csv, cfg.root)
    cfg.labels.file = _resolve(cfg.labels.file, cfg.root)

    cfg.data.mkdir(parents=True, exist_ok=True)
    cfg.out.mkdir(parents=True, exist_ok=True)

    # validate source-specific requirements early, with friendly messages
    # (dem.source='lidar' needs no charts: they're auto-discovered from the bbox)
    if cfg.dem.source == "local" and cfg.dem.file is None:
        raise ValueError("dem.source='local' needs dem.file = 'path/to/dem.tif'")
    if cfg.labels.enabled and cfg.labels.source == "denue" and not cfg.labels.cvemun:
        raise ValueError("labels.source='denue' needs labels.cvemun (3-digit code)")
    return cfg
