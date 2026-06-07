# xalapa-relieve

A clean, modern **shaded-relief poster of the municipio of Xalapa**
(Veracruz, México), rendered in **Blender** from Copernicus GLO-30 and cut to
the municipal boundary so only Xalapa floats on a soft light background —
a monochrome hypsometric relief in the spirit of @joewdavies' country plates.

![Xalapa relief](output/xalapa_relieve.png)

Pale lowlands in the east rise to the deep-blue volcanic highlands of the
west; the cone near the centre is **Cerro de Macuiltépetl (1,522 m)**, the
high point of the city. Elevation range in frame: **663 – 1,596 m**.

## Data

- **Elevation:** INEGI **LiDAR terrain (bare-earth) DEM at 5 m** — the best
  data available for Xalapa, ~6× the resolution of the global GLO-30 (≈4.9 M
  real samples inside the municipio). The 1:10,000 chart tiles are pulled via
  INEGI's own `getF10KDescarga.do` endpoint, mosaicked (ESRI grids), reprojected
  to UTM 14N and clipped to the municipio. See `fetch_lidar.py`.
  *(`fetch_dem.py` keeps the simpler 15 m CEM-via-WCS path as a fallback; on a
  small area, resolution matters — 30 m global data looks soft at poster size.)*
- **Boundary:** INEGI **Marco Geoestadístico 2020** — Xalapa municipio
  (clave 30087), rasterised to a mask that cuts the Blender mesh.

> The 5 m chart codes were found by reading INEGI's elevation tool: its
> `caneva_10k` vector grid (decoded as MVT) gives the 1:10,000 chart codes over
> the municipio, and `getF10KDescarga.do` returns each chart's direct download
> URL — no UI clicking required.

## How it works

| Step | Module | Output |
|------|--------|--------|
| 1 | `fetch_dem.py` | GLO-30 → 10 m heightmap (lightly generalised) + elevation + **municipio mask** |
| 2 | `make_textures.py` | **monochrome hypsometric** albedo (pale → deep blue, γ-curved) |
| 3 | `blender_render.py` | subdivided grid → Displace → **Mask modifier cuts to the municipio** → soft NW key + cool fill → **Cycles/OptiX** render on transparent + shadow catcher |
| 4 | `compose.py` | clean light background, the floating relief, restrained spaced-serif title + credit (Pillow) |

## Run

```bash
uv sync
uv run xalapa-relieve            # full build (~4K poster)
uv run xalapa-relieve --draft    # fast low-res preview
uv run xalapa-relieve --skip-dem # reuse the cached DEM
```

Needs a local **Blender** (5.x) on `PATH`; a CUDA/OptiX GPU makes Cycles fast
(falls back to CPU). The finished poster is `output/xalapa_relieve.png`.

## Tuning

Top of `blender_render.py`: vertical exaggeration (`EXAG`), sun azimuth/altitude.
Top of `make_textures.py`: the `COLORS` ramp and `GAMMA` (how much ground stays
pale vs how much goes deep blue). `config.py`: the bbox / municipio.
