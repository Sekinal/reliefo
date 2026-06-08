"""Fetch a DEM for the bbox, cut it to the municipio boundary, and write the
artefacts the renderer needs: a 16-bit heightmap, the raw elevation array, the
boundary mask and ``meta.json``.

Three interchangeable elevation sources, chosen by ``[dem] source``:

* ``cem``   — INEGI Continuo de Elevaciones Mexicano 4.0, 15 m, via the public
  GeoServer WCS. Zero setup: works for any bbox in Mexico.
* ``lidar`` — INEGI 5 m LiDAR *terrain* (bare-earth), the sharpest data
  available. Needs the covering 1:10,000 chart codes (``[dem] charts``).
* ``local`` — any GeoTIFF DEM you already have (``[dem] file``).
"""
from __future__ import annotations

import json
import subprocess
import zipfile  # noqa: F401  (kept for callers that inspect archives)

import httpx
import numpy as np
import rasterio
from PIL import Image
from scipy.ndimage import (
    binary_closing,
    binary_erosion,
    binary_fill_holes,
    binary_opening,
    distance_transform_edt,
    gaussian_filter,
)

from ._util import info, meters_per_degree, run, step, warn
from .charts import discover_charts
from .config import Config

CEM_WCS = "https://gaia.inegi.org.mx/geoserver/wcs"
CEM_COVERAGE = "cem4_workespace:cem15m_3857"        # INEGI CEM 4.0, 15 m
CEM_NATIVE_M = 15.0
LIDAR_INFO = "https://www.inegi.org.mx/app/geo2/elevacionesmex/getF10KDescarga.do"


# --------------------------------------------------------------------------- #
#  Elevation sources -> a single reprojected GeoTIFF in the job's UTM zone
# --------------------------------------------------------------------------- #
def _fetch_cem(cfg: Config) -> None:
    bb = cfg.map.bbox
    lon_m, _ = meters_per_degree(bb.center[1])
    w = round((bb.east - bb.west) * lon_m / CEM_NATIVE_M)
    h = round((bb.north - bb.south) * 110_540.0 / CEM_NATIVE_M)
    info(f"INEGI CEM 4.0 (15 m) WCS  {w}×{h}px")
    r = httpx.get(CEM_WCS, timeout=120.0, params={
        "service": "WCS", "version": "1.0.0", "request": "GetCoverage",
        "coverage": CEM_COVERAGE, "CRS": "EPSG:4326",
        "BBOX": f"{bb.west},{bb.south},{bb.east},{bb.north}",
        "FORMAT": "GeoTIFF", "WIDTH": w, "HEIGHT": h})
    if r.status_code != 200 or r.content[:2] not in (b"II", b"MM"):
        raise RuntimeError(f"CEM WCS failed ({r.status_code}): {r.content[:200]!r}")
    src = cfg.data / "cem_4326.tif"
    src.write_bytes(r.content)
    run(["gdalwarp", "-overwrite", "-t_srs", cfg.utm,
         "-tr", str(cfg.dem.res_m), str(cfg.dem.res_m), "-r", "cubicspline",
         "-co", "COMPRESS=DEFLATE", src, cfg.data / "dem_utm.tif"])


def _lidar_chart(cfg: Config, cve: str) -> object:
    """Resolve + download one 5 m terrain GRID chart; return its directory."""
    ddir = cfg.data / "lidar"
    ddir.mkdir(exist_ok=True)
    r = httpx.post(LIDAR_INFO, data={"res": "5", "mod": "T", "cve": cve},
                   timeout=60.0).json()
    g = next(x for x in r if "GRID" in x["titulo"] and x["mod"] == "T")
    url = g["url_descarga"] + "_gr.zip"
    z = ddir / f"{cve}.zip"
    if not z.exists() or z.stat().st_size < 10_000:
        z.write_bytes(httpx.get(url, timeout=240.0, follow_redirects=True).content)
    out = ddir / cve
    # unzip exits 1 on the Windows-backslash paths but still extracts
    subprocess.run(["unzip", "-o", str(z), "-d", str(out)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    return next(out.rglob("w001001.adf")).parent


def _fetch_lidar(cfg: Config) -> None:
    bb = cfg.map.bbox
    charts = cfg.dem.charts or discover_charts(bb)
    vrts = []
    for cve in charts:
        try:
            grid = _lidar_chart(cfg, cve)
        except Exception as e:                          # noqa: BLE001
            warn(f"skip chart {cve}: {e}")
            continue
        v = cfg.data / "lidar" / f"{cve}.vrt"
        run(["gdal_translate", "-a_srs", cfg.utm, "-of", "VRT", grid, v])
        vrts.append(str(v))
        info(f"chart {cve} ok")
    if not vrts:
        raise RuntimeError("no LiDAR charts downloaded — check dem.charts codes")
    mosaic = cfg.data / "lidar" / "mosaic.vrt"
    run(["gdalbuildvrt", "-overwrite", "-vrtnodata", "-3.4028235e+38", mosaic, *vrts])
    run(["gdalwarp", "-overwrite", "-t_srs", cfg.utm, "-te_srs", "EPSG:4326",
         "-te", str(bb.west), str(bb.south), str(bb.east), str(bb.north),
         "-tr", str(cfg.dem.res_m), str(cfg.dem.res_m), "-r", "bilinear",
         "-dstnodata", "-9999", "-co", "COMPRESS=DEFLATE",
         mosaic, cfg.data / "dem_utm.tif"])


def _fetch_local(cfg: Config) -> None:
    bb = cfg.map.bbox
    run(["gdalwarp", "-overwrite", "-t_srs", cfg.utm, "-te_srs", "EPSG:4326",
         "-te", str(bb.west), str(bb.south), str(bb.east), str(bb.north),
         "-tr", str(cfg.dem.res_m), str(cfg.dem.res_m), "-r", "cubicspline",
         "-co", "COMPRESS=DEFLATE", cfg.dem.file, cfg.data / "dem_utm.tif"])


_SOURCES = {"cem": _fetch_cem, "lidar": _fetch_lidar, "local": _fetch_local}


# --------------------------------------------------------------------------- #
#  Boundary -> mask, on the exact DEM grid
# --------------------------------------------------------------------------- #
def _boundary_mask(cfg: Config, bounds, W: int, H: int) -> np.ndarray:
    cmd = ["ogr2ogr", "-overwrite", "-t_srs", cfg.utm]
    if cfg.boundary.where:
        cmd += ["-where", cfg.boundary.where]
    run([*cmd, cfg.boundary_utm, cfg.boundary.file])
    mask_tif = cfg.data / "mask.tif"
    run(["gdal_rasterize", "-burn", "1", "-init", "0", "-ot", "Byte",
         "-te", str(bounds.left), str(bounds.bottom),
         str(bounds.right), str(bounds.top),
         "-ts", str(W), str(H), cfg.boundary_utm, mask_tif])
    with rasterio.open(mask_tif) as ms:
        return ms.read(1) > 0


def _clean_mask(mask: np.ndarray) -> np.ndarray:
    """Tidy the silhouette so the cut edge has no pixel-scale spikes/flaps."""
    mask = binary_fill_holes(mask)
    mask = binary_opening(mask, iterations=3)      # strip thin peninsulas
    mask = binary_closing(mask, iterations=3)
    mask = gaussian_filter(mask.astype(float), sigma=4.0) > 0.5   # smooth perimeter
    mask = binary_erosion(mask, iterations=2)
    return mask.astype(np.uint8)


# --------------------------------------------------------------------------- #
#  Public entry point
# --------------------------------------------------------------------------- #
def build(cfg: Config) -> None:
    step(f"DEM · {cfg.dem.source}")
    source_used = cfg.dem.source
    try:
        _SOURCES[cfg.dem.source](cfg)
    except RuntimeError as e:
        if cfg.dem.source != "lidar":
            raise
        # not all of Mexico has 5 m LiDAR (e.g. parts of the coast / altiplano);
        # fall back to the always-available 15 m CEM so the city still renders.
        warn(f"LiDAR unavailable ({e}); falling back to CEM 15 m")
        _fetch_cem(cfg)
        source_used = "cem"

    with rasterio.open(cfg.data / "dem_utm.tif") as ds:
        dem = ds.read(1).astype(np.float32)
        bounds, W, H = ds.bounds, ds.width, ds.height
        px = (ds.transform.a, -ds.transform.e)
    dem = np.where(dem < -1000, np.nan, dem)

    mask = _boundary_mask(cfg, bounds, W, H) & np.isfinite(dem)
    if cfg.dem.smooth_mask:
        mask = _clean_mask(mask)
    else:
        mask = mask.astype(np.uint8)

    inside = dem[mask == 1]
    vmin, vmax = float(np.nanmin(inside)), float(np.nanmax(inside))
    dem = np.nan_to_num(dem, nan=vmin)
    info(f"{dem.shape} @ {px[0]:.1f} m · elev {vmin:.0f}–{vmax:.0f} m "
         f"· {int(mask.sum()):,} px inside")

    np.save(cfg.elevation_npy, dem)
    np.save(cfg.mask_npy, mask)

    # taper the height to the base near the boundary so the rim is a clean
    # rounded edge, not a cliff of triangular flaps. A small pad forces the
    # outermost ring flat to the base (kills edge flaps on steep boundaries),
    # then the height ramps up over edge_taper_px.
    rim_pad = 4.0
    taper = np.clip((distance_transform_edt(mask) - rim_pad)
                    / max(cfg.dem.edge_taper_px, 1e-6), 0, 1)
    dem_s = gaussian_filter(dem, sigma=cfg.dem.height_sigma)
    norm = ((dem_s - vmin) / (vmax - vmin)).clip(0, 1) * taper
    Image.fromarray((norm * 65535).astype(np.uint16)).save(cfg.heightmap_png)

    source_label = {"cem": "INEGI CEM 4.0 (15 m)",
                    "lidar": "INEGI LiDAR 5 m (terreno, bare-earth)",
                    "local": "local DEM"}[source_used]
    cfg.meta_json.write_text(json.dumps(dict(
        bbox=cfg.map.bbox.as_dict(), source=source_label, crs=cfg.utm, px_m=px,
        width=W, height=H, shape=[int(dem.shape[0]), int(dem.shape[1])],
        elev_min=vmin, elev_max=vmax,
        utm_bounds=[bounds.left, bounds.bottom, bounds.right, bounds.top]), indent=2))
    info(f"wrote heightmap, elevation, mask, meta  ({source_label})")
