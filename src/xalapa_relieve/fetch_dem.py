"""Fetch the best free DEM for the Xalapa region: Copernicus DEM GLO-30
(ESA, 30 m, the authoritative global elevation model), straight from the
public AWS bucket via GDAL /vsicurl. Mosaic the needed 1-degree tiles,
crop to the bbox and reproject to UTM 14N (metres) so the relief has
true proportions. Then write a 16-bit heightmap + elevation array + meta.
"""
from __future__ import annotations
import json
import subprocess
import numpy as np
import rasterio
from PIL import Image
from . import config as C

BASE = ("https://copernicus-dem-30m.s3.amazonaws.com/"
        "Copernicus_DSM_COG_10_{t}_DEM/Copernicus_DSM_COG_10_{t}_DEM.tif")
# 1-degree tiles covering the bbox (SW-corner naming): lon -98..-96, lat 19..20
TILES = ["N19_00_W097_00", "N19_00_W098_00"]
UTM = "EPSG:32614"          # Xalapa is in UTM zone 14N
RES = 30                    # metres


def main():
    bb = C.BBOX
    srcs = [f"/vsicurl/{BASE.format(t=t)}" for t in TILES]
    dem_tif = C.DATA / "dem_utm.tif"
    cmd = [
        "gdalwarp", "-overwrite",
        "-t_srs", UTM, "-te_srs", "EPSG:4326",
        "-te", str(bb["west"]), str(bb["south"]), str(bb["east"]), str(bb["north"]),
        "-tr", str(RES), str(RES), "-r", "cubicspline",
        "-co", "COMPRESS=DEFLATE", "-co", "TILED=YES",
        *srcs, str(dem_tif),
    ]
    print("gdalwarp Copernicus GLO-30 ->", dem_tif.name)
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)

    with rasterio.open(dem_tif) as ds:
        dem = ds.read(1).astype(np.float32)
        nodata = ds.nodata
        tr = ds.transform
        px = (tr.a, -tr.e)  # metres per pixel (x, y)
    if nodata is not None:
        dem = np.where(dem == nodata, np.nan, dem)
    vmin = float(np.nanmin(dem)); vmax = float(np.nanmax(dem))
    dem = np.nan_to_num(dem, nan=vmin)
    print(f"DEM {dem.shape}  px {px[0]:.1f} m  elevation {vmin:.0f}..{vmax:.0f} m")

    np.save(C.ELEV_NPY, dem.astype(np.float32))
    norm = (dem - vmin) / (vmax - vmin)
    Image.fromarray((norm * 65535).clip(0, 65535).astype(np.uint16)).save(C.HEIGHT_PNG)

    meta = dict(bbox=bb, source="Copernicus DEM GLO-30 (ESA)", crs=UTM,
                px_m=px, shape=list(dem.shape), width=dem.shape[1],
                height=dem.shape[0], elev_min=vmin, elev_max=vmax)
    C.META_JSON.write_text(json.dumps(meta, indent=2))
    print("saved:", C.HEIGHT_PNG.name, C.ELEV_NPY.name, C.META_JSON.name)


if __name__ == "__main__":
    main()
