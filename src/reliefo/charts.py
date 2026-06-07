"""Auto-discover the INEGI 1:10,000 chart codes covering a bbox.

INEGI's elevation tool draws a ``caneva_10k`` grid (the 1:10,000 chart index)
as Mapbox vector tiles; each cell carries its chart code in ``cve_carta``. We
fetch the tiles over the bbox, decode them, and return the codes whose cell
intersects the bbox — exactly the charts the 5 m LiDAR source needs, with no
manual hunting in the web UI.

The grid layer is per-state (``cem<NN>_workespace:caneva_10k``); the default is
Veracruz (30). Override via ``layer`` for another state.
"""
from __future__ import annotations

import math

import httpx
import mapbox_vector_tile as mvt
from shapely.geometry import box, shape

from ._util import info

TILE_URL = "https://www.inegi.org.mx/app/geo2/elevacionesmex/GetMap.do"
DEFAULT_LAYER = "cem30_workespace:caneva_10k"          # Veracruz
PROP = "cve_carta"
_R = 6378137.0                                          # web-mercator radius
_UA = "Mozilla/5.0 reliefo/0.2 (+https://github.com/Sekinal/reliefo)"


def _lonlat_to_tile(lon: float, lat: float, z: int) -> tuple[int, int]:
    n = 2 ** z
    lr = math.radians(lat)
    return (int((lon + 180) / 360 * n),
            int((1 - math.log(math.tan(lr) + 1 / math.cos(lr)) / math.pi) / 2 * n))


def _tile_merc_bounds(x: int, y: int, z: int) -> tuple[float, float, float, float]:
    c = 2 * math.pi * _R
    res = c / (2 ** z)
    return (-c / 2 + x * res, c / 2 - (y + 1) * res,
            -c / 2 + (x + 1) * res, c / 2 - y * res)     # minx, miny, maxx, maxy


def _merc_to_lonlat(mx: float, my: float) -> tuple[float, float]:
    return (mx / _R * 180 / math.pi,
            (2 * math.atan(math.exp(my / _R)) - math.pi / 2) * 180 / math.pi)


def _map_coords(c, fn):
    if c and isinstance(c[0], (int, float)):
        return list(fn(c))
    return [_map_coords(x, fn) for x in c]


def discover_charts(bbox, z: int = 12, layer: str = DEFAULT_LAYER) -> list[str]:
    """Return the sorted 1:10,000 chart codes whose cell intersects ``bbox``.

    ``bbox`` is anything with ``.west/.south/.east/.north`` (a config ``BBox``).
    """
    bpoly = box(bbox.west, bbox.south, bbox.east, bbox.north)
    x0, y0 = _lonlat_to_tile(bbox.west, bbox.north, z)
    x1, y1 = _lonlat_to_tile(bbox.east, bbox.south, z)
    found: set[str] = set()
    with httpx.Client(headers={"User-Agent": _UA}, timeout=60.0) as client:
        for tx in range(x0, x1 + 1):
            for ty in range(y0, y1 + 1):
                tms_y = (2 ** z - 1) - ty                # URL uses TMS y ({-y})
                r = client.get(TILE_URL,
                               params={"layer": layer, "z": z, "x": tx, "y": tms_y})
                if r.status_code != 200 or not r.content:
                    continue
                try:
                    data = mvt.decode(r.content)
                except Exception:                        # noqa: BLE001
                    continue
                minx, miny, maxx, maxy = _tile_merc_bounds(tx, ty, z)
                for lyr in data.values():
                    ext = lyr.get("extent", 4096)

                    def to_ll(pt, _b=(minx, miny, maxx, maxy), _e=ext):
                        px, py = pt
                        mx = _b[0] + px / _e * (_b[2] - _b[0])
                        my = _b[1] + py / _e * (_b[3] - _b[1])
                        return _merc_to_lonlat(mx, my)

                    for feat in lyr["features"]:
                        cve = feat["properties"].get(PROP)
                        if not cve:
                            continue
                        geom = feat["geometry"]
                        try:
                            shp = shape({"type": geom["type"],
                                         "coordinates": _map_coords(geom["coordinates"], to_ll)})
                            if shp.intersects(bpoly):
                                found.add(cve)
                        except Exception:                # noqa: BLE001
                            continue
    if not found:
        raise RuntimeError("no charts found for bbox — is it inside Veracruz? "
                           f"(layer={layer})")
    info(f"discovered {len(found)} charts: {', '.join(sorted(found))}")
    return sorted(found)
