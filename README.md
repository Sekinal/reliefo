# xalapa-relieve

A vintage **1953 Geological-Survey-style raised-relief plate** of the
**municipio of Xalapa** (Veracruz, México), rendered in **Blender** and cut to
the municipal boundary so only Xalapa floats on the paper — like the islands
of the original Japan plate. Finished with an aged-paper cartouche,
hypsometric legend, graticule and serif place names.

![Xalapa relief plate](output/xalapa_relieve_1953.png)

The terrain spans the municipio's full range, **660 – 1,596 m**: brown
highlands in the west (with a volcanic cone near the centre) sloping to the
green lowlands of the east.

## Data

- **Elevation:** Copernicus DEM **GLO-30** (ESA) — the authoritative free
  global DEM — pulled from the public AWS bucket via GDAL `/vsicurl`,
  reprojected to **UTM 14N** and resampled to a smooth **10 m**.
- **Boundary:** INEGI **Marco Geoestadístico 2020** — the Xalapa municipio
  polygon (clave 30087), rasterised to a mask that cuts the Blender mesh to the
  municipal silhouette.

Not a fork of [geoblender](https://github.com/joewdavies/geoblender) — a fresh
pipeline written from scratch, but in the same raised-relief spirit.

## How it works

| Step | Module | Output |
|------|--------|--------|
| 1 | `fetch_dem.py` | Copernicus GLO-30 → 10 m heightmap + elevation + **municipio mask** + meta |
| 2 | `make_textures.py` | hypsometric albedo stretched over the municipio's elevation range |
| 3 | `blender_render.py` | subdivided grid → Displace → **Mask modifier cuts the mesh to the municipio** → hypsometric material → low sun → **Cycles/OptiX** render floating over paper (shadow catcher) |
| 4 | `compose.py` | aged-paper plate: double border, title cartouche, `LEYENDA`, graticule + degree labels, place names, survey footer (Pillow) |

## Run

```bash
uv sync
uv run xalapa-relieve            # full build (≈ 4.5K poster)
uv run xalapa-relieve --draft    # fast low-res preview
uv run xalapa-relieve --skip-dem # reuse the cached DEM
```

Requires a local **Blender** (5.x) on `PATH` and a CUDA/OptiX GPU for fast
Cycles rendering (falls back to CPU). DEM/heightmap/render artefacts land in
`data/` and `output/` (git-ignored); the finished plate is
`output/xalapa_relieve_1953.png`.

## Tuning

Edit the constants at the top of `blender_render.py`: vertical exaggeration
(`EXAG`), sun azimuth/altitude, camera tilt, paper colour.
