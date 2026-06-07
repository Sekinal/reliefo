# reliefo

Clean, modern **shaded-relief posters of any Mexican municipio**, rendered in
**Blender** from INEGI elevation data and cut to the municipal boundary so only
your city floats on a soft background — a monochrome hypsometric relief in the
spirit of [@joewdavies](https://github.com/joewdavies)' country plates.

Everything region-specific lives in a small **TOML config**. Point it at a
municipio and it fetches the DEM, cuts the terrain to the boundary, renders the
plate (Cycles/OptiX) and composes the poster — title, elevation colour scale,
optional glowing street grid and zone labels.

![Xalapa relief](output/xalapa.png)

> The bundled example is **Xalapa, Veracruz** (`examples/xalapa.toml`): INEGI
> 5 m LiDAR terrain, Crameri `oslo` relief, OSM streets and DENUE zone labels.

---

## Install

```bash
# 1. Python deps (uv handles the venv for you)
uv sync

# 2. System tools used by the pipeline:
#    - Blender 5.x on PATH        (the renderer; a CUDA/OptiX GPU makes it fast)
#    - GDAL CLI (gdalwarp, ogr2ogr, gdal_rasterize, gdalbuildvrt, gdal_translate)
#    - unzip                      (only for the 5 m LiDAR source)
# On Arch:   sudo pacman -S blender gdal unzip
# On Debian: sudo apt install blender gdal-bin unzip
```

Render the example to check your setup:

```bash
uv run reliefo build examples/xalapa.toml --draft   # fast, low-res
uv run reliefo build examples/xalapa.toml           # full 4K poster
```

The poster lands in the config's output dir (here `output/xalapa.png`).

---

## Tutorial — a poster of *your* municipio

Say you want **Coatepec, Veracruz**. You need three things: a **bounding box**,
a **boundary polygon**, and a **DEM source**. Streets and labels are optional.

### 1 · Pick the bounding box

Grab a rectangle around your municipio (WGS84 degrees) from any map — e.g.
[bboxfinder.com](http://bboxfinder.com). Add a small margin. You'll put it in
the config as `west / south / east / north`.

### 2 · Get the boundary polygon (INEGI Marco Geoestadístico)

The plate is cut to this polygon. INEGI publishes every municipio in the
**Marco Geoestadístico 2020**:

1. Download your state's package from INEGI → *Marco Geoestadístico* (one ZIP
   per *entidad*; Veracruz is `30`). Inside is a municipal layer, e.g.
   `conjunto_de_datos/30mun.shp`, with a `CVEGEO` field (state + municipio code).
2. Extract just your municipio to GeoJSON in WGS84. Coatepec is CVEGEO `30038`:

   ```bash
   ogr2ogr -f GeoJSON -t_srs EPSG:4326 \
       data/coatepec_mun.geojson 30mun.shp -where "CVEGEO = '30038'"
   ```

   *(Find your CVEGEO with INEGI's catalogue, or* `ogrinfo -al 30mun.shp | grep -i <name>`*.)*

Alternatively, point `[boundary] file` straight at the state shapefile and let
reliefo select the feature with `[boundary] where = "CVEGEO = '30038'"`.

### 3 · Choose a DEM source

| Source | `[dem] source` | Resolution | Setup | When |
|--------|----------------|-----------|-------|------|
| **CEM 4.0** | `"cem"` | 15 m | none — just the bbox | **start here**; great for most municipios |
| **5 m LiDAR** | `"lidar"` | 5 m | list chart codes | sharpest; worth it at poster size |
| **Local file** | `"local"` | yours | a GeoTIFF | you already have a DEM |

**CEM (easiest):** nothing to download — reliefo pulls it from INEGI's public
WCS for your bbox. Just set `source = "cem"` and `res_m = 10`.

**5 m LiDAR (sharpest):** you supply the 1:10,000 chart codes covering your
bbox. Find them in INEGI's elevation tool
([`/app/geo2/elevacionesmex`](https://www.inegi.org.mx/app/geo2/elevacionesmex/)):
pan to your area, turn on the 1:10,000 grid, and read the codes (like
`E14B27D1`) of the cells that cover your bbox. List them in `[dem] charts`.
reliefo downloads each chart's bare-earth terrain GRID, mosaics, reprojects and
clips automatically.

**Local:** set `source = "local"` and `file = "path/to/dem.tif"` (any CRS;
reliefo reprojects to the right UTM zone for you).

> The **UTM zone** is detected from your bbox automatically — no need to set it.

### 4 · Streets *(optional)*

Set `[streets] enabled = true` to bake a faint glowing road grid onto the
relief. By default reliefo fetches highways from **Overpass** for your bbox.
If you already have an OSM lines file (e.g. a Geofabrik extract converted with
`ogr2ogr`), point `[streets] osm_file` at it to skip the network.

### 5 · Labels *(optional)*

Set `[labels] enabled = true` for named-zone chips. Three sources:

- `source = "overpass"` — OSM `place` nodes (suburb/neighbourhood) in the bbox.
- `source = "denue"` — colonia centroids from INEGI's DENUE directory. Set
  `cvemun` (the 3-digit municipio code, e.g. `"038"`) and `denue_csv`. Add a
  curated `include = [...]` of display names to keep only well-known zones
  (matched ignoring case/accents) and `big = [...]` for the larger labels.
- `source = "file"` — your own GeoJSON points with a `name` property.

### 6 · Write the config

```toml
[map]
name     = "Coatepec"
subtitle = "VERACRUZ · MÉXICO"
bbox     = { west = -97.00, south = 19.42, east = -96.92, north = 19.50 }

[boundary]
file = "data/coatepec_mun.geojson"

[dem]
source = "cem"      # 15 m, zero setup
res_m  = 10

[relief]
palette      = "oslo"
exaggeration = 4.2
```

### 7 · Render

```bash
uv run reliefo check examples/coatepec.toml      # validate + print settings
uv run reliefo build examples/coatepec.toml      # render the poster
```

That's it — `output/coatepec.png`.

---

## Config reference

| Section | Key | Default | Meaning |
|---------|-----|---------|---------|
| `[map]` | `name` | — | municipio name (filenames + default title) |
| | `title` | `NAME` | poster headline |
| | `subtitle` | `""` | small line under the title |
| | `bbox` | — | `{west, south, east, north}` in degrees |
| `[boundary]` | `file` | — | polygon to cut to (GeoJSON/GPKG/SHP) |
| | `where` | — | OGR filter to pick one feature, e.g. `CVEGEO='30038'` |
| `[dem]` | `source` | `cem` | `cem` \| `lidar` \| `local` |
| | `res_m` | `10` | output grid (metres/pixel) |
| | `charts` | `[]` | 1:10,000 chart codes (`lidar`) |
| | `file` | — | GeoTIFF DEM (`local`) |
| | `height_sigma` | `0.8` | displacement denoise |
| | `edge_taper_px` | `10` | round the cut rim to the base |
| `[relief]` | `palette` | `oslo` | colour scale (see below) |
| | `exaggeration` | `4.2` | vertical exaggeration |
| | `sun_azimuth` / `sun_altitude` | `318` / `42` | key-light direction (deg) |
| | `cam_tilt` | `9` | camera tilt off vertical (deg) |
| `[streets]` | `enabled` | `false` | bake the glowing road grid |
| | `osm_file` | — | pre-downloaded OSM lines; else Overpass |
| | `glow` | `4.0` | emission strength |
| `[labels]` | `enabled` | `false` | draw named-zone chips |
| | `source` | `overpass` | `overpass` \| `denue` \| `file` |
| | `cvemun` / `denue_csv` | — | DENUE municipio code + CSV path |
| | `include` / `big` | `[]` | curated display names / larger ones |
| `[render]` | `resolution` | `4000` | final width (px) |
| | `samples` | `160` | Cycles samples |
| `[paths]` | `data` / `out` | `data` / `output` | working + output dirs |

Relative paths are resolved against the **config file's** directory.

## How it works

| Step | Module | Output |
|------|--------|--------|
| 1 | `dem.py` | DEM → 16-bit heightmap, elevation array, **municipio mask**, `meta.json` |
| 2 | `streets.py` *(opt.)* | OSM roads → `roads_{minor,major}.npy` on the DEM grid |
| 3 | `labels.py` *(opt.)* | named-zone centroids → `zones.json` |
| 4 | `textures.py` | **hypsometric albedo** (+ street emission map) |
| 5 | `blender_render.py` | grid → Displace → **Mask cut to the municipio** → soft NW key + cool fill → Cycles/OptiX render on transparency + shadow catcher |
| 6 | `compose.py` | light background, the floating relief, **elevation colour scale**, spaced-serif title, zone chips (Pillow) |

## Colour scales

The default `oslo` is the genuine **Crameri** perceptually-uniform colormap
(reversed: pale lowlands → deep navy heights), so equal elevation steps look
equal and a monochrome scale reads unambiguously as elevation. Other options:
`lajolla`/`copper` (warm), `davos` (teal), `blue`, `imhof` (green→tan), `bukavu`.

## Development

```bash
uv run pytest        # tests (pure functions: UTM, palettes, config, name matching)
uv run ruff check    # lint
```

## Data sources & credits

- **Elevation:** INEGI — *Continuo de Elevaciones Mexicano* (CEM 4.0, 15 m) and
  the 5 m LiDAR bare-earth terrain charts.
- **Boundary:** INEGI — *Marco Geoestadístico 2020*.
- **Streets:** OpenStreetMap contributors (via Overpass).
- **Labels:** OpenStreetMap, or INEGI's DENUE business directory.
- **Colormaps:** Fabio Crameri's [Scientific Colour Maps](https://www.fabiocrameri.ch/colourmaps/).

Code is MIT-licensed. The data belongs to its respective providers — check
INEGI's and OSM's terms before redistributing derivatives.
