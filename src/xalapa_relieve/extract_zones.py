"""Main named zones of Xalapa with positions from a reliable INEGI source:
the centroid of each *asentamiento* (colonia) computed from the geocoded
establishments of INEGI's DENUE directory. A curated list of the well-known
zones keeps the labels clean. -> data/zones.json

(OSM place=suburb nodes would be the other option, but Overpass/Geofabrik were
unavailable; DENUE is authoritative and already local.)
"""
from __future__ import annotations
import csv
import json
from . import config as C

DENUE = ("/home/ieqr/Desktop/research/denue_xalapa/data/conjunto_de_datos/"
         "denue_inegi_30_.csv")

# DENUE asentamiento name -> display label (proper case + accents)
ZONES = {
    "CENTRO": "Centro",
    "LAS ANIMAS": "Las Ánimas",
    "EL CASTILLO": "El Castillo",
    "LAS TRANCAS": "Las Trancas",
    "REVOLUCION": "Revolución",
    "OBRERO CAMPESINA": "Obrero Campesina",
    "PROGRESO MACUILTEPETL": "Progreso Macuiltépetl",
    "RAFAEL LUCIO": "Rafael Lucio",
    "CAROLINO ANAYA": "Carolino Anaya",
    "VERACRUZ": "Veracruz",
    "EL MIRADOR": "El Mirador",
    "BADILLO": "Badillo",
    "EL SUMIDERO": "El Sumidero",
    "LOMAS VERDES": "Lomas Verdes",
    "ENCINAL": "Encinal",
    "CAMPO DE TIRO": "Campo de Tiro",
}
BIG = {"Centro", "Las Ánimas", "Las Trancas", "El Castillo"}   # larger labels


def main():
    csv.field_size_limit(10 ** 7)
    acc = {k: [0, 0.0, 0.0] for k in ZONES}
    with open(DENUE, encoding="latin-1") as fh:
        r = csv.reader(fh); hdr = next(r); col = {h: i for i, h in enumerate(hdr)}
        iM, iA, iLa, iLo = (col["cve_mun"], col["nomb_asent"],
                            col["latitud"], col["longitud"])
        for row in r:
            if row[iM] != "087" or row[iA] not in acc:
                continue
            try:
                la, lo = float(row[iLa]), float(row[iLo])
            except ValueError:
                continue
            a = acc[row[iA]]; a[0] += 1; a[1] += lo; a[2] += la

    zones = []
    for key, disp in ZONES.items():
        n, lo, la = acc[key]
        if n == 0:
            continue
        zones.append({"name": disp, "lon": lo / n, "lat": la / n,
                      "place": "suburb" if disp in BIG else "neighbourhood",
                      "n": n})
    (C.DATA / "zones.json").write_text(json.dumps(zones, ensure_ascii=False, indent=1))
    print(f"zones: {len(zones)} (source: DENUE asentamiento centroids)")
    for z in zones:
        print(f"  {z['name']:24s} {z['lon']:.5f},{z['lat']:.5f}  (n={z['n']})")


if __name__ == "__main__":
    main()
