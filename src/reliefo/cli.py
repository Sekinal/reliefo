"""``reliefo`` command-line interface (Typer)."""
from __future__ import annotations

from pathlib import Path

import typer

from . import pipeline
from ._util import console, warn
from .config import load_config

app = typer.Typer(add_completion=False, no_args_is_help=True,
                  help="Render a clean shaded-relief poster of a Mexican municipio.")


@app.command()
def build(
    config: Path = typer.Argument(..., exists=True, dir_okay=False,
                                  help="Path to a TOML config (see examples/)."),
    draft: bool = typer.Option(False, "--draft", help="Fast low-res preview."),
    skip_dem: bool = typer.Option(False, "--skip-dem",
                                  help="Reuse the cached DEM (skip download)."),
    clean: bool = typer.Option(False, "--clean",
                               help="Force streets/labels off (variant A)."),
    res: int | None = typer.Option(None, help="Override render width (px)."),
    samples: int | None = typer.Option(None, help="Override Cycles samples."),
) -> None:
    """Run the full pipeline for CONFIG and write the poster to its output dir."""
    cfg = load_config(config)
    pipeline.build(cfg, draft=draft, skip_dem=skip_dem, clean=clean,
                   res=res, samples=samples)
    console.print("[bold green]✓[/bold green] done")


@app.command()
def check(config: Path = typer.Argument(..., exists=True, dir_okay=False)) -> None:
    """Validate a config and print the resolved settings (no rendering)."""
    cfg = load_config(config)
    console.print_json(cfg.model_dump_json(indent=2))
    console.print(f"[dim]UTM zone:[/dim] {cfg.utm}   "
                  f"[dim]poster:[/dim] {cfg.poster_png}")
    if cfg.streets.enabled and cfg.streets.osm_file and not cfg.streets.osm_file.exists():
        warn(f"streets.osm_file not found: {cfg.streets.osm_file}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
