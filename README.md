# xalapa-relieve

A vintage **1953 Geological-Survey-style raised-relief plate** of the Xalapa
region (Veracruz, México), rendered in **Blender** from the best free DEM and
finished with an aged-paper cartouche, hypsometric legend, graticule and
serif place names.

![Xalapa relief plate](output/xalapa_relieve_1953.png)

It captures the dramatic west–east gradient: **Cofre de Perote (4,282 m)** in
the west falling to the Gulf lowlands in the east, with Xalapa perched on the
mid-slope.

## Data

- **Elevation:** Copernicus DEM **GLO-30** (ESA, 30 m) — the authoritative free
  global DEM — pulled straight from the public AWS bucket via GDAL `/vsicurl`,
  mosaicked, cropped and reprojected to **UTM 14N** for true proportions.
  Range in frame: **0 – 4,179 m**.

Not a fork of [geoblender](https://github.com/joewdavies/geoblender) — a fresh
pipeline written from scratch, but in the same raised-relief spirit.

## How it works

| Step | Module | Output |
|------|--------|--------|
| 1 | `fetch_dem.py` | Copernicus GLO-30 → 16-bit heightmap + elevation array + meta |
| 2 | `make_textures.py` | vintage hypsometric albedo (+ shaded preview) |
| 3 | `blender_render.py` | subdivided grid → Displace → hypsometric material → low sun → **Cycles/OptiX** render of a plate floating over paper (shadow catcher), orthographic slightly-tilted camera |
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
