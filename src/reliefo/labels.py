"""Named-zone labels for the poster, written to ``data/zones.json`` as
``[{name, lon, lat, place, n}]``.

Three sources (``[labels] source``):

* ``overpass`` — OSM ``place`` nodes (suburb/neighbourhood/quarter) in the bbox.
* ``denue``    — centroids of each *asentamiento* (colonia) from INEGI's DENUE
  business directory; authoritative for Mexico. Read with Polars.
* ``file``     — your own GeoJSON points with a ``name`` property.

An optional curated ``include`` list keeps only well-known zones (matched
accent/-case-insensitively); ``big`` marks the ones drawn larger.
"""
from __future__ import annotations

import io
import json
import unicodedata

import httpx
import polars as pl

from ._util import info, step, warn
from .config import Config

OVERPASS = "https://overpass-api.de/api/interpreter"
_PLACE_RANK = {"city": 0, "town": 1, "suburb": 2, "quarter": 3,
               "neighbourhood": 4, "village": 5, "hamlet": 6}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(c for c in s.upper().split() if c).strip()


def _curation(cfg: Config) -> tuple[dict[str, str], set[str]]:
    """normalized-name -> display, and the set of normalized 'big' names."""
    display = {_norm(name): name for name in cfg.labels.include}
    big = {_norm(name) for name in cfg.labels.big}
    return display, big


def _place(name_norm: str, big: set[str]) -> str:
    return "suburb" if name_norm in big else "neighbourhood"


# --------------------------------------------------------------------------- #
def _from_denue(cfg: Config) -> list[dict]:
    text = cfg.labels.denue_csv.read_bytes().decode("latin-1")
    df = pl.read_csv(io.StringIO(text),
                     columns=["cve_mun", "nomb_asent", "latitud", "longitud"],
                     schema_overrides={"cve_mun": pl.Utf8, "nomb_asent": pl.Utf8},
                     infer_schema_length=0)
    df = (df.filter(pl.col("cve_mun") == cfg.labels.cvemun)
            .with_columns(pl.col("latitud").cast(pl.Float64, strict=False),
                          pl.col("longitud").cast(pl.Float64, strict=False))
            .drop_nulls(["latitud", "longitud"]))
    agg = (df.group_by("nomb_asent")
             .agg(pl.len().alias("n"),
                  pl.col("longitud").mean().alias("lon"),
                  pl.col("latitud").mean().alias("lat")))

    display, big = _curation(cfg)
    zones = []
    for row in agg.iter_rows(named=True):
        nn = _norm(row["nomb_asent"])
        if display and nn not in display:
            continue
        name = display.get(nn, row["nomb_asent"].title())
        zones.append({"name": name, "lon": row["lon"], "lat": row["lat"],
                      "place": _place(nn, big), "n": int(row["n"])})
    if not display:                                    # no curation -> top by count
        zones.sort(key=lambda z: -z["n"])
        zones = zones[:15]
    return zones


def _from_overpass(cfg: Config) -> list[dict]:
    bb = cfg.map.bbox
    q = (f"[out:json][timeout:120];"
         f'node["place"~"city|town|suburb|quarter|neighbourhood"]'
         f"({bb.south},{bb.west},{bb.north},{bb.east});out;")
    r = httpx.post(OVERPASS, data={"data": q}, timeout=180.0)
    r.raise_for_status()
    display, big = _curation(cfg)
    zones = []
    for el in r.json().get("elements", []):
        name = el.get("tags", {}).get("name")
        if not name:
            continue
        nn = _norm(name)
        if display and nn not in display:
            continue
        zones.append({"name": display.get(nn, name),
                      "lon": el["lon"], "lat": el["lat"],
                      "place": el["tags"].get("place", "neighbourhood"),
                      "n": 0})
    return zones


def _from_file(cfg: Config) -> list[dict]:
    gj = json.loads(cfg.labels.file.read_text())
    display, big = _curation(cfg)
    zones = []
    for feat in gj.get("features", []):
        name = feat.get("properties", {}).get("name")
        lon, lat = feat["geometry"]["coordinates"][:2]
        if not name:
            continue
        nn = _norm(name)
        if display and nn not in display:
            continue
        zones.append({"name": display.get(nn, name), "lon": lon, "lat": lat,
                      "place": _place(nn, big), "n": 0})
    return zones


_SOURCES = {"denue": _from_denue, "overpass": _from_overpass, "file": _from_file}


def build(cfg: Config) -> None:
    step(f"labels · {cfg.labels.source}")
    zones = _SOURCES[cfg.labels.source](cfg)
    if not zones:
        warn("no zones found; the poster will have no labels")
    zones.sort(key=lambda z: _PLACE_RANK.get(z["place"], 9))
    cfg.zones_json.write_text(json.dumps(zones, ensure_ascii=False, indent=1))
    info(f"{len(zones)} zones -> {cfg.zones_json.name}")
