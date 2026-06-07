"""Fetch INEGI's Continuo de Elevaciones Mexicano (CEM 4.0, 15 m) for the
Xalapa municipio via the public INEGI GeoServer WCS — twice the resolution of
the global GLO-30 — reproject to UTM 14N and rasterise the municipio polygon
to a mask aligned to the DEM grid.
"""
from __future__ import annotations
import json
import math
import subprocess
import numpy as np
import rasterio
import requests
from PIL import Image
from scipy.ndimage import gaussian_filter, binary_erosion
from . import config as C

WCS = "https://gaia.inegi.org.mx/geoserver/wcs"
COVERAGE = "cem4_workespace:cem15m_3857"   # INEGI CEM 4.0, 15 m
NATIVE_M = 15.0
UTM = "EPSG:32614"


def sh(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def fetch_wcs(bb, out):
    midlat = (bb["south"] + bb["north"]) / 2
    w = round((bb["east"] - bb["west"]) * 111320 * math.cos(math.radians(midlat)) / NATIVE_M)
    h = round((bb["north"] - bb["south"]) * 111320 / NATIVE_M)
    r = requests.get(WCS, timeout=120, params={
        "service": "WCS", "version": "1.0.0", "request": "GetCoverage",
        "coverage": COVERAGE, "CRS": "EPSG:4326",
        "BBOX": f'{bb["west"]},{bb["south"]},{bb["east"]},{bb["north"]}',
        "FORMAT": "GeoTIFF", "WIDTH": w, "HEIGHT": h})
    if r.status_code != 200 or r.content[:2] not in (b"II", b"MM"):
        raise RuntimeError(f"WCS failed ({r.status_code}): {r.content[:200]!r}")
    out.write_bytes(r.content)
    print(f"INEGI CEM 4.0 (15 m) WCS -> {out.name}  {w}x{h}px")


def main():
    bb = C.BBOX
    cem = C.DATA / "cem_4326.tif"
    fetch_wcs(bb, cem)
    dem_tif = C.DATA / "dem_utm.tif"
    sh(["gdalwarp", "-overwrite", "-t_srs", UTM, "-tr", str(C.RES_M), str(C.RES_M),
        "-r", "cubicspline", "-co", "COMPRESS=DEFLATE", str(cem), str(dem_tif)])

    with rasterio.open(dem_tif) as ds:
        dem = ds.read(1).astype(np.float32)
        b = ds.bounds
        W, H = ds.width, ds.height
        px = (ds.transform.a, -ds.transform.e)

    # rasterise municipio polygon -> mask on the exact DEM grid
    mun_utm = C.DATA / "mun_utm.gpkg"
    sh(["ogr2ogr", "-overwrite", "-t_srs", UTM, str(mun_utm), str(C.MUN_GEOJSON)])
    mask_tif = C.DATA / "mask.tif"
    sh(["gdal_rasterize", "-burn", "1", "-init", "0", "-ot", "Byte",
        "-te", str(b.left), str(b.bottom), str(b.right), str(b.top),
        "-ts", str(W), str(H), str(mun_utm), str(mask_tif)])
    with rasterio.open(mask_tif) as ms:
        mask = (ms.read(1) > 0).astype(np.uint8)

    # clean the silhouette: trim boundary cells that cause displacement spikes
    mask = binary_erosion(mask, iterations=3, border_value=0).astype(np.uint8)

    inside = dem[mask == 1]
    vmin, vmax = float(inside.min()), float(inside.max())
    print(f"DEM {dem.shape} px {px[0]:.1f}m  municipio elev {vmin:.0f}..{vmax:.0f} m "
          f"({mask.sum()} px inside)")

    np.save(C.ELEV_NPY, dem)            # raw, for accurate legend
    np.save(C.MASK_NPY, mask)
    # 15 m data carries real detail -> only a light denoise
    dem_s = gaussian_filter(dem, sigma=1.2)
    norm = ((dem_s - vmin) / (vmax - vmin)).clip(0, 1)
    Image.fromarray((norm * 65535).astype(np.uint16)).save(C.HEIGHT_PNG)

    C.META_JSON.write_text(json.dumps(dict(
        bbox=bb, source="INEGI CEM 4.0 (15 m)", crs=UTM, px_m=px,
        width=W, height=H, shape=[int(dem.shape[0]), int(dem.shape[1])],
        elev_min=vmin, elev_max=vmax,
        utm_bounds=[b.left, b.bottom, b.right, b.top]), indent=2))
    print("saved heightmap, elevation, mask, meta")


if __name__ == "__main__":
    main()
