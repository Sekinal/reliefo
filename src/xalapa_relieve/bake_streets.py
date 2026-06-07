"""Rasterise Xalapa's OSM street network onto the DEM grid (UTM, clipped to the
municipio) so make_textures can bake it into the albedo — the grid then drapes
on the 3-D relief in Blender. Produces data/roads_minor.npy + roads_major.npy.
"""
from __future__ import annotations
import json
import subprocess
import numpy as np
import rasterio
from . import config as C

SRC = "/home/ieqr/Desktop/research/denue_xalapa/data/osm/xalapa_lines_wide.gpkg"
UTM = "EPSG:32614"
MAJOR = ("motorway", "trunk", "primary", "secondary", "tertiary",
         "motorway_link", "trunk_link", "primary_link", "secondary_link")


def sh(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    meta = json.loads(C.META_JSON.read_text())
    b = meta["utm_bounds"]; W, H = meta["width"], meta["height"]
    roads_utm = C.DATA / "roads_utm.gpkg"
    sh(["ogr2ogr", "-overwrite", "-t_srs", UTM,
        "-clipsrc", str(C.DATA / "mun_utm.gpkg"),
        "-where", "highway IS NOT NULL", str(roads_utm), SRC, "lines"])

    def rasterize(where, out):
        sh(["gdal_rasterize", "-burn", "1", "-init", "0", "-ot", "Byte", "-l", "lines",
            "-where", where, "-te", str(b[0]), str(b[1]), str(b[2]), str(b[3]),
            "-ts", str(W), str(H), str(roads_utm), str(out)])
        with rasterio.open(out) as ds:
            return (ds.read(1) > 0).astype(np.uint8)

    minor = rasterize("highway IS NOT NULL", C.DATA / "roads_all.tif")
    inq = "','".join(MAJOR)
    major = rasterize(f"highway IN ('{inq}')", C.DATA / "roads_major.tif")
    np.save(C.DATA / "roads_minor.npy", minor)
    np.save(C.DATA / "roads_major.npy", major)
    print(f"streets rasterised: minor {minor.sum()} px, major {major.sum()} px")


if __name__ == "__main__":
    main()
