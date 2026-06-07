"""Compose the cut-out Xalapa relief onto a clean, modern minimal poster
(joewdavies / Greece style): soft light background, the floating monochrome
relief, and restrained spaced-serif type. No cartouche, legend or graticule.
"""
from __future__ import annotations
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import gaussian_filter
from . import config as C

INK = (38, 46, 56)
SOFT = (96, 108, 122)
BG = (234, 235, 237)
FREG = "/usr/share/fonts/noto/NotoSerif-Regular.ttf"
FLIGHT = "/usr/share/fonts/noto/NotoSerif-Light.ttf"
FITAL = "/usr/share/fonts/noto/NotoSerif-Italic.ttf"


def f(size, w="r"):
    return ImageFont.truetype(
        {"r": FREG, "l": FLIGHT, "i": FITAL}[w], int(size))


def tracked(draw, xy, text, font, fill, ls=0, anchor="la"):
    x, y = xy
    ws = [draw.textlength(c, font=font) for c in text]
    total = sum(ws) + ls * (len(text) - 1)
    if "m" in anchor:
        x -= total / 2
    elif "r" in anchor:
        x -= total
    for c, w in zip(text, ws):
        draw.text((x, y), c, font=font, fill=fill)
        x += w + ls
    return total


def clean_bg(w, h):
    # cool light grey, a touch brighter top-left, soft darkening to the corners
    yy, xx = np.mgrid[0:h, 0:w]
    grad = (xx / w * 0.5 + yy / h * 0.5)            # 0 top-left -> 1 bottom-right
    base = np.array(BG, float)[None, None, :]
    img = base - grad[..., None] * np.array([10, 10, 11])
    d = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    vig = np.clip(1 - 0.10 * np.clip(d - 0.7, 0, None), 0.86, 1)[..., None]
    img = img * vig
    img += np.random.default_rng(3).normal(0, 1.4, (h, w, 1))
    return Image.fromarray(img.clip(0, 255).astype(np.uint8), "RGB")


def main():
    relief = Image.open(C.RENDER_PNG).convert("RGBA")
    rw, rh = relief.size
    S = rw / 2000.0

    img = clean_bg(rw, rh)
    # soft contact shadow already baked into the relief's alpha (shadow catcher)
    img.paste(relief, (0, 0), relief)
    d = ImageDraw.Draw(img)

    m = int(70 * S)
    # ---- title (top-left, over the clean background) ----------------
    tracked(d, (m, m), "XALAPA", f(86 * S, "r"), INK, ls=22 * S)
    tracked(d, (m + 3 * S, m + 116 * S),
            "MUNICIPIO  ·  VERACRUZ, MÉXICO", f(23 * S, "l"), SOFT, ls=9 * S)

    # ---- credit (bottom-left, à la the reference) -------------------
    by = rh - m
    tracked(d, (m, by - 30 * S), "Relieve sombreado · exageración vertical ×5",
            f(17 * S, "i"), SOFT, ls=2 * S)
    tracked(d, (m, by), "DEM: Copernicus GLO-30 (ESA)   ·   2026",
            f(17 * S, "l"), SOFT, ls=2 * S)

    img.save(C.FINAL_PNG, quality=95)
    print("saved", C.FINAL_PNG, img.size)


if __name__ == "__main__":
    main()
