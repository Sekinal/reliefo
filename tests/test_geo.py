from reliefo._util import meters_per_degree, utm_epsg


def test_utm_epsg_mexico():
    # Xalapa sits in UTM zone 14N
    assert utm_epsg(-96.917, 19.528) == "EPSG:32614"
    # Tijuana -> 11N, Cancún -> 16N
    assert utm_epsg(-117.0, 32.5) == "EPSG:32611"
    assert utm_epsg(-86.85, 21.16) == "EPSG:32616"


def test_utm_epsg_southern_hemisphere():
    assert utm_epsg(-58.4, -34.6) == "EPSG:32721"  # Buenos Aires, 21S


def test_meters_per_degree_shrinks_with_latitude():
    eq_lon, _ = meters_per_degree(0.0)
    hi_lon, _ = meters_per_degree(60.0)
    assert eq_lon > hi_lon > 0
