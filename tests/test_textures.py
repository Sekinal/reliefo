import pytest

from reliefo.labels import _norm
from reliefo.textures import PALETTES, gamma, ramp


@pytest.mark.parametrize("name", list(PALETTES))
def test_ramp_shape_and_range(name):
    lut = ramp(name, 256)
    assert lut.shape == (256, 3)
    assert lut.min() >= 0 and lut.max() <= 255.0001


def test_gamma_oslo():
    assert gamma("oslo") == pytest.approx(1.30)


def test_unknown_palette_raises():
    with pytest.raises(ValueError, match="unknown palette"):
        ramp("not-a-palette")


def test_norm_strips_accents_and_case():
    assert _norm("Las Ánimas") == "LAS ANIMAS"
    assert _norm("REVOLUCIÓN") == "REVOLUCION"
    assert _norm("  Progreso   Macuiltépetl ") == "PROGRESO MACUILTEPETL"
