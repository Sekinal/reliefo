"""Small shared helpers: logging, shell-out to GDAL, and geodesy."""
from __future__ import annotations

import math
import subprocess
from pathlib import Path

from rich.console import Console

# A single stderr console so stdout stays clean for piping/redirects.
console = Console(stderr=True, highlight=False)


def step(title: str) -> None:
    """Announce a pipeline stage."""
    console.rule(f"[bold cyan]{title}", align="left")


def info(msg: str) -> None:
    console.print(f"[dim]·[/dim] {msg}")


def warn(msg: str) -> None:
    console.print(f"[yellow]![/yellow] {msg}")


def run(cmd: list[str | Path], *, quiet: bool = True) -> None:
    """Run a subprocess (typically a GDAL tool), raising on failure."""
    cmd = [str(c) for c in cmd]
    out = subprocess.DEVNULL if quiet else None
    subprocess.run(cmd, check=True, stdout=out, stderr=out)


def utm_epsg(lon: float, lat: float) -> str:
    """EPSG code of the UTM zone containing ``(lon, lat)`` (WGS84).

    Mexico spans zones 11N–16N; this works anywhere on Earth.
    """
    zone = int(math.floor((lon + 180.0) / 6.0)) % 60 + 1
    return f"EPSG:{(32600 if lat >= 0 else 32700) + zone}"


def meters_per_degree(lat: float) -> tuple[float, float]:
    """Approximate metres per degree of longitude/latitude at ``lat``."""
    lon_m = 111_320.0 * math.cos(math.radians(lat))
    return lon_m, 110_540.0
