from pathlib import Path

import pytest
from pydantic import ValidationError

from reliefo.config import BBox, Config, load_config

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "xalapa.toml"


def test_load_example():
    cfg = load_config(EXAMPLE)
    assert cfg.map.headline == "XALAPA"
    assert cfg.slug == "xalapa"
    assert cfg.utm == "EPSG:32614"
    assert cfg.poster_png.name == "xalapa.png"
    assert cfg.dem.source == "lidar" and len(cfg.dem.charts) == 12
    # relative paths resolved to absolute
    assert cfg.boundary.file.is_absolute()
    assert cfg.map.bbox.center == pytest.approx((-96.885, 19.542))


def test_bbox_must_be_ordered():
    with pytest.raises(ValidationError):
        BBox(west=0, south=0, east=-1, north=1)


def test_lidar_charts_optional(tmp_path):
    # charts are auto-discovered from the bbox, so none need be given
    toml = tmp_path / "m.toml"
    toml.write_text(
        '[map]\nname="X"\nbbox={west=-97,south=19,east=-96,north=20}\n'
        '[boundary]\nfile="b.geojson"\n'
        '[dem]\nsource="lidar"\n')
    cfg = load_config(toml)
    assert cfg.dem.source == "lidar" and cfg.dem.charts == []


def test_minimal_cem_config(tmp_path):
    toml = tmp_path / "m.toml"
    toml.write_text(
        '[map]\nname="Coatepec"\nbbox={west=-97.0,south=19.4,east=-96.9,north=19.5}\n'
        '[boundary]\nfile="coatepec.geojson"\n')
    cfg = load_config(toml)
    assert isinstance(cfg, Config)
    assert cfg.dem.source == "cem"          # default
    assert cfg.utm == "EPSG:32614"
