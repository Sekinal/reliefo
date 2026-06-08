"""Export print-grade posters to social-media-ready JPEGs.

The 8K posters are built for print; Facebook/Instagram cap uploads far smaller
(FB ~2048 px, IG ~1080 px, low-tens-of-MB files), so an 8K/80 MB PNG just hangs.
This downscales every PNG in a folder to a long-edge size as optimized JPEG.

    uv run python scripts/social_export.py <folder> [--size 2048] [--quality 90]
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", type=Path, help="folder of poster PNGs")
    ap.add_argument("--size", type=int, default=2048, help="long-edge px")
    ap.add_argument("--quality", type=int, default=90)
    a = ap.parse_args()

    out = a.folder / "social"
    out.mkdir(exist_ok=True)
    for f in sorted(a.folder.glob("*.png")):
        im = Image.open(f).convert("RGB")
        w, h = im.size
        s = a.size / max(w, h)
        im = im.resize((round(w * s), round(h * s)), Image.LANCZOS)
        dst = out / f"{f.stem}.jpg"
        im.save(dst, "JPEG", quality=a.quality, optimize=True)
        print(f"{f.name:38s} {w}x{h} -> {im.size}  {dst.stat().st_size // 1024} KB")
    print(f"-> {out}")


if __name__ == "__main__":
    main()
