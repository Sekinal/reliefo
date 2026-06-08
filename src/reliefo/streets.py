"""Rasterise the OSM street network onto the DEM grid (UTM, clipped to the
municipio) so the textures step can bake it into a glowing emission map.

Streets come from either a pre-downloaded OSM lines file (``[streets] osm_file``)
or, by default, a live Overpass query for the bbox. Output:
``data/roads_minor.npy`` (all roads) and ``data/roads_major.npy`` (arterials).
"""
from __future__ import annotations

import json

import httpx
import numpy as np
import rasterio

from ._util import info, run, step
from .config import Config

OVERPASS = "https://overpass-api.de/api/interpreter"
UA = "reliefo/0.2 (relief poster generator; +https://github.com/Sekinal/reliefo)"
MAJOR = ("motorway", "trunk", "primary", "secondary", "tertiary",
         "motorway_link", "trunk_link", "primary_link", "secondary_link")


def _overpass_geojson(cfg: Config) -> object:
    """Download highways in the bbox from Overpass -> a GeoJSON lines file."""
    bb = cfg.map.bbox
    filt = ('["highway"~"motorway|trunk|primary|secondary"]'
            if cfg.streets.major_only else '["highway"]')
    q = (f"[out:json][timeout:300];"
         f"way{filt}({bb.south},{bb.west},{bb.north},{bb.east});"
         f"out geom;")
    info("querying Overpass for highways …")
    r = httpx.post(OVERPASS, data={"data": q}, headers={"User-Agent": UA},
                   timeout=300.0)
    r.raise_for_status()
    feats = []
    for el in r.json().get("elements", []):
        geom = el.get("geometry")
        if not geom:
            continue
        feats.append({
            "type": "Feature",
            "properties": {"highway": el.get("tags", {}).get("highway", "")},
            "geometry": {"type": "LineString",
                         "coordinates": [[p["lon"], p["lat"]] for p in geom]},
        })
    out = cfg.data / "streets_overpass.geojson"
    out.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    info(f"Overpass returned {len(feats):,} ways")
    return out


def build(cfg: Config) -> None:
    step("streets")
    meta = json.loads(cfg.meta_json.read_text())
    b = meta["utm_bounds"]
    W, H = meta["width"], meta["height"]

    src = cfg.streets.osm_file or _overpass_geojson(cfg)
    roads_utm = cfg.data / "roads_utm.gpkg"
    roads_utm.unlink(missing_ok=True)              # avoid stale layers
    # clip to the municipio and keep only highways; OSM files expose a 'lines'
    # layer, a GeoJSON just its single layer. Normalise the output to 'roads'.
    layer = ["lines"] if str(src).endswith((".gpkg", ".pbf", ".osm")) else []
    run(["ogr2ogr", "-t_srs", cfg.utm, "-nln", "roads",
         "-clipsrc", cfg.boundary_utm, "-where", "highway IS NOT NULL",
         roads_utm, src, *layer])

    def rasterize(where: str, out) -> np.ndarray:
        run(["gdal_rasterize", "-burn", "1", "-init", "0", "-ot", "Byte",
             "-l", "roads", "-where", where,
             "-te", str(b[0]), str(b[1]), str(b[2]), str(b[3]),
             "-ts", str(W), str(H), roads_utm, out])
        with rasterio.open(out) as ds:
            return (ds.read(1) > 0).astype(np.uint8)

    minor = rasterize("highway IS NOT NULL", cfg.data / "roads_all.tif")
    inq = "','".join(MAJOR)
    major = rasterize(f"highway IN ('{inq}')", cfg.data / "roads_major.tif")
    np.save(cfg.data / "roads_minor.npy", minor)
    np.save(cfg.data / "roads_major.npy", major)
    info(f"rasterised · minor {int(minor.sum()):,} px · major {int(major.sum()):,} px")
