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


def warm_bloom(img, relief, strength=0.45, sigma=7):
    """soft glow isolated to the warm (street-emission) pixels of the relief."""
    a = np.asarray(relief).astype(np.float64)
    rgb, alpha = a[..., :3], a[..., 3:4] / 255.0
    warm = np.clip((rgb[..., 0] - rgb[..., 2]) / 255.0, 0, 1)      # R - B
    bright = np.clip(rgb.mean(2) / 255.0 - 0.45, 0, 1)
    src = ((warm ** 1.3) * bright)[..., None] * np.array([255, 205, 120.]) * alpha
    glow = np.stack([gaussian_filter(src[..., k], sigma) for k in range(3)], -1)
    out = np.asarray(img).astype(np.float64)
    out = 255 - (255 - out) * (255 - np.clip(glow * strength, 0, 255)) / 255   # screen
    return Image.fromarray(out.clip(0, 255).astype(np.uint8))


def label_zones(d, S):
    pts = json.loads((C.OUT / "points.json").read_text())
    zones = pts.get("zones", [])
    if not zones:
        return
    big = {"city", "town", "suburb"}
    # draw important zones first; skip any that would collide with a placed one
    zones.sort(key=lambda z: (z["place"] not in big, -z.get("n", 0)))
    placed = []
    mind = 150 * S
    for z in zones:
        x, y = z["xy"]
        if any((x - px) ** 2 + (y - py) ** 2 < mind ** 2 for px, py in placed):
            continue
        placed.append((x, y))
        name = z["name"]
        isbig = z["place"] in big
        fnt = f((31 if isbig else 25) * S, "r" if isbig else "l")
        for ox, oy in [(-2, 0), (2, 0), (0, -2), (0, 2), (-1.5, -1.5),
                       (1.5, 1.5), (-1.5, 1.5), (1.5, -1.5)]:
            tracked(d, (x + ox * S, y + oy * S), name, fnt, (236, 237, 238),
                    ls=1.5 * S, anchor="ma")
        tracked(d, (x, y), name, fnt, (24, 30, 42), ls=1.5 * S, anchor="ma")


def main():
    relief = Image.open(C.RENDER_PNG).convert("RGBA")
    rw, rh = relief.size
    S = rw / 2000.0
    streets = (C.DATA / "streets_emission.png").exists()

    img = clean_bg(rw, rh)
    img.paste(relief, (0, 0), relief)
    if streets:
        img = warm_bloom(img, relief)
    d = ImageDraw.Draw(img)

    m = int(70 * S)
    # ---- title (top-left, over the clean background) ----------------
    tracked(d, (m, m), "XALAPA", f(86 * S, "r"), INK, ls=22 * S)
    tracked(d, (m + 3 * S, m + 116 * S),
            "VERACRUZ · MÉXICO", f(23 * S, "l"), SOFT, ls=9 * S)

    if streets:
        label_zones(d, S)

    # ---- credit (bottom-left) --------------------------------------
    cred = "DEM: INEGI · LiDAR 5 m" + ("   ·   red vial OSM" if streets else "")
    tracked(d, (m, rh - m), cred, f(17 * S, "l"), SOFT, ls=2 * S)

    img.save(C.FINAL_PNG, quality=95)
    print("saved", C.FINAL_PNG, img.size)


if __name__ == "__main__":
    main()
