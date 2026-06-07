"""Fetch Copernicus DEM GLO-30 for the Xalapa municipio bbox, reproject to
UTM 14N (resampled to a smooth 10 m), and rasterise the municipio polygon to
a mask aligned to the DEM grid. Heightmap is normalised over the elevation
range *inside* the municipio so the hypsometric palette uses its full span.
"""
from __future__ import annotations
import json
import subprocess
import numpy as np
import rasterio
from PIL import Image
from scipy.ndimage import gaussian_filter, binary_erosion
from . import config as C

BASE = ("https://copernicus-dem-30m.s3.amazonaws.com/"
        "Copernicus_DSM_COG_10_{t}_DEM/Copernicus_DSM_COG_10_{t}_DEM.tif")
TILES = ["N19_00_W097_00"]          # municipio sits inside lon -97..-96, lat 19..20
UTM = "EPSG:32614"


def sh(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    bb = C.BBOX
    dem_tif = C.DATA / "dem_utm.tif"
    sh(["gdalwarp", "-overwrite", "-t_srs", UTM, "-te_srs", "EPSG:4326",
        "-te", str(bb["west"]), str(bb["south"]), str(bb["east"]), str(bb["north"]),
        "-tr", str(C.RES_M), str(C.RES_M), "-r", "cubicspline",
        f"/vsicurl/{BASE.format(t=TILES[0])}", str(dem_tif)])

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
    # balanced generalisation: clean ridges without crumpled micro-noise
    dem_s = gaussian_filter(dem, sigma=1.9)
    norm = ((dem_s - vmin) / (vmax - vmin)).clip(0, 1)
    Image.fromarray((norm * 65535).astype(np.uint16)).save(C.HEIGHT_PNG)

    C.META_JSON.write_text(json.dumps(dict(
        bbox=bb, source="Copernicus DEM GLO-30 (ESA)", crs=UTM, px_m=px,
        width=W, height=H, shape=[int(dem.shape[0]), int(dem.shape[1])],
        elev_min=vmin, elev_max=vmax,
        utm_bounds=[b.left, b.bottom, b.right, b.top]), indent=2))
    print("saved heightmap, elevation, mask, meta")


if __name__ == "__main__":
    main()
