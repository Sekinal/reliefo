"""Fetch INEGI's 5 m LiDAR *terrain* (bare-earth) DEM for the Xalapa municipio —
the best elevation data available here (6x the global GLO-30). The 1:10,000
chart tiles are requested through INEGI's own download endpoint
(`getF10KDescarga.do`); the covering chart codes were derived from the
`caneva_10k` vector grid. Tiles are mosaicked, reprojected to UTM 14N and
clipped to the municipio, then the mask + heightmap are built as usual.
"""
from __future__ import annotations
import json
import subprocess
import zipfile
import numpy as np
import rasterio
import requests
from PIL import Image
from scipy.ndimage import (gaussian_filter, binary_erosion, binary_fill_holes,
                           binary_opening, binary_closing, distance_transform_edt)
from . import config as C

INFO = "https://www.inegi.org.mx/app/geo2/elevacionesmex/getF10KDescarga.do"
UTM = "EPSG:32614"
# 1:10,000 charts covering the municipio (from the caneva_10k MVT grid)
CHARTS = ["E14B27D1", "E14B27D2", "E14B27D3", "E14B27D4", "E14B37A1", "E14B37A2",
          "E14B27E1", "E14B27E3", "E14B37B1", "E14B27E2", "E14B27E4", "E14B37B2"]


def sh(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def chart_grid(cve, ddir):
    """Resolve + download the 5 m terrain GRID for one chart; return its dir."""
    r = requests.post(INFO, data={"res": "5", "mod": "T", "cve": cve}, timeout=60).json()
    g = next(x for x in r if "GRID" in x["titulo"] and x["mod"] == "T")
    url = g["url_descarga"] + "_gr.zip"
    z = ddir / f"{cve}.zip"
    if not z.exists() or z.stat().st_size < 10000:
        z.write_bytes(requests.get(url, timeout=240).content)
    d = ddir / cve
    # unzip returns 1 (warning) on the Windows-backslash paths but still extracts
    subprocess.run(["unzip", "-o", str(z), "-d", str(d)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    adf = next(d.rglob("w001001.adf"))
    return adf.parent


def build_dem(ddir):
    vrts = []
    for cve in CHARTS:
        try:
            grid = chart_grid(cve, ddir)
        except Exception as e:                          # noqa
            print("  skip", cve, e); continue
        v = ddir / f"{cve}.vrt"
        sh(["gdal_translate", "-a_srs", UTM, "-of", "VRT", str(grid), str(v)])
        vrts.append(str(v)); print("  ok", cve)
    if not vrts:
        raise RuntimeError("no LiDAR charts downloaded")
    mosaic = ddir / "mosaic.vrt"
    sh(["gdalbuildvrt", "-overwrite", "-vrtnodata", "-3.4028235e+38", str(mosaic), *vrts])
    bb = C.BBOX
    dem_tif = C.DATA / "dem_utm.tif"
    sh(["gdalwarp", "-overwrite", "-t_srs", UTM, "-te_srs", "EPSG:4326",
        "-te", str(bb["west"]), str(bb["south"]), str(bb["east"]), str(bb["north"]),
        "-tr", "5", "5", "-r", "bilinear", "-dstnodata", "-9999",
        "-co", "COMPRESS=DEFLATE", str(mosaic), str(dem_tif)])
    return dem_tif


def main():
    ddir = C.DATA / "lidar"; ddir.mkdir(exist_ok=True)
    dem_tif = build_dem(ddir)

    with rasterio.open(dem_tif) as ds:
        dem = ds.read(1).astype(np.float32)
        b = ds.bounds; W, H = ds.width, ds.height
        px = (ds.transform.a, -ds.transform.e)
    dem = np.where(dem < -1000, np.nan, dem)

    mun_utm = C.DATA / "mun_utm.gpkg"
    sh(["ogr2ogr", "-overwrite", "-t_srs", UTM, str(mun_utm), str(C.MUN_GEOJSON)])
    mask_tif = C.DATA / "mask.tif"
    sh(["gdal_rasterize", "-burn", "1", "-init", "0", "-ot", "Byte",
        "-te", str(b.left), str(b.bottom), str(b.right), str(b.top),
        "-ts", str(W), str(H), str(mun_utm), str(mask_tif)])
    with rasterio.open(mask_tif) as ms:
        mask = ms.read(1) > 0
    mask &= np.isfinite(dem)
    # tidy the municipio outline so the cut edge is clean (no pixel-scale
    # spikes/flaps): fill holes, open/close away protrusions, smooth + re-bin
    mask = binary_fill_holes(mask)
    mask = binary_opening(mask, iterations=2)
    mask = binary_closing(mask, iterations=2)
    mask = gaussian_filter(mask.astype(float), sigma=3.0) > 0.5
    mask = binary_erosion(mask, iterations=2).astype(np.uint8)

    inside = dem[mask == 1]
    vmin, vmax = float(np.nanmin(inside)), float(np.nanmax(inside))
    dem = np.nan_to_num(dem, nan=vmin)
    print(f"LiDAR DEM {dem.shape} px {px[0]:.1f}m  elev {vmin:.0f}..{vmax:.0f} m "
          f"({mask.sum()} px inside)")

    np.save(C.ELEV_NPY, dem)
    np.save(C.MASK_NPY, mask)
    # taper the height down to the base over the last ~10 px of the boundary so
    # the cut edge is a clean rounded rim, not a cliff of triangular flaps
    taper = np.clip(distance_transform_edt(mask) / 10.0, 0, 1)
    dem_s = gaussian_filter(dem, sigma=0.8)        # 5 m data -> barely touch it
    norm = ((dem_s - vmin) / (vmax - vmin)).clip(0, 1) * taper
    Image.fromarray((norm * 65535).astype(np.uint16)).save(C.HEIGHT_PNG)

    C.META_JSON.write_text(json.dumps(dict(
        bbox=C.BBOX, source="INEGI LiDAR 5 m (terreno, bare-earth)", crs=UTM, px_m=px,
        width=W, height=H, shape=[int(dem.shape[0]), int(dem.shape[1])],
        elev_min=vmin, elev_max=vmax,
        utm_bounds=[b.left, b.bottom, b.right, b.top]), indent=2))
    print("saved heightmap, elevation, mask, meta")


if __name__ == "__main__":
    main()
