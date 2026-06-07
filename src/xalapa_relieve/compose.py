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
from .make_textures import ramp, GAMMA

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


def label_zones(img, S):
    pts = json.loads((C.OUT / "points.json").read_text())
    zones = pts.get("zones", [])
    if not zones:
        return img
    big = {"city", "town", "suburb"}
    drop = {"Lomas Verdes"}            # too close to Las Trancas
    zones = [z for z in zones if z["name"] not in drop]
    zones.sort(key=lambda z: (z["place"] not in big, -z.get("n", 0)))
    d0 = ImageDraw.Draw(img)
    placed, chosen = [], []
    px_, py_ = 13 * S, 7 * S
    gap = 10 * S                                    # min clear space between chips
    for z in zones:
        x, y = z["xy"]
        isbig = z["place"] in big
        fnt = f((30 if isbig else 27) * S, "r")
        ls = 1.5 * S
        w = sum(d0.textlength(c, font=fnt) for c in z["name"]) + ls * (len(z["name"]) - 1)
        h = fnt.size
        box = (x - w / 2 - px_ - gap, y - py_ - gap, x + w / 2 + px_ + gap, y + h + py_ + gap)
        if any(box[0] < b[2] and b[0] < box[2] and box[1] < b[3] and b[1] < box[3]
               for b in placed):
            continue
        placed.append(box)
        chosen.append((x, y, z["name"], fnt, ls, w, h))

    # translucent chips behind the labels so they read over the busy streets
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    do = ImageDraw.Draw(ov)
    for x, y, name, fnt, ls, w, h in chosen:
        do.rounded_rectangle([x - w / 2 - px_, y - py_, x + w / 2 + px_, y + h + py_],
                             radius=h * 0.5, fill=(247, 248, 249, 200))
    img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")

    d = ImageDraw.Draw(img)
    for x, y, name, fnt, ls, w, h in chosen:
        tracked(d, (x, y), name, fnt, (26, 32, 44), ls=ls, anchor="ma")
    return img


def color_legend(img, S, vmin, vmax):
    """slim vertical elevation scale (same oslo ramp + gamma as the relief)."""
    import math
    lut = ramp(256)                                   # low -> high colours
    m = int(70 * S)
    bw, bh = int(22 * S), int(300 * S)
    x0, y0 = img.width - m - bw, img.height - m - bh
    col = np.array([lut[int(((1 - i / (bh - 1)) ** GAMMA) * 255)] for i in range(bh)])
    bar = np.repeat(col[:, None, :], bw, axis=1).clip(0, 255).astype(np.uint8)
    img.paste(Image.fromarray(bar, "RGB"), (x0, y0))
    d = ImageDraw.Draw(img)
    d.rectangle([x0, y0, x0 + bw - 1, y0 + bh - 1],
                outline=(208, 211, 216), width=max(1, int(S)))
    tracked(d, (x0 + bw / 2, y0 - 34 * S), "ALTITUD", f(19 * S, "l"),
            SOFT, ls=6 * S, anchor="ma")
    fnt = f(17 * S, "l")
    step = 300
    for e in range(int(math.ceil(vmin / step) * step), int(vmax) + 1, step):
        y = y0 + (1 - (e - vmin) / (vmax - vmin)) * bh
        d.line([(x0 - 8 * S, y), (x0 - 1, y)], fill=SOFT, width=max(1, int(S)))
        tracked(d, (x0 - 14 * S, y - fnt.size / 2), f"{e:,}".replace(",", " "),
                fnt, SOFT, ls=1 * S, anchor="ra")
    tracked(d, (x0 + bw / 2, y0 + bh + 12 * S), "m s. n. m.", f(13 * S, "i"),
            SOFT, ls=1 * S, anchor="ma")


def main():
    relief = Image.open(C.RENDER_PNG).convert("RGBA")
    rw, rh = relief.size
    S = rw / 2000.0
    streets = (C.DATA / "streets_emission.png").exists()

    img = clean_bg(rw, rh)
    img.paste(relief, (0, 0), relief)
    if streets:
        img = warm_bloom(img, relief)
        img = label_zones(img, S)

    meta = json.loads(C.META_JSON.read_text())
    color_legend(img, S, meta["elev_min"], meta["elev_max"])
    d = ImageDraw.Draw(img)

    m = int(70 * S)
    # ---- title (top-left, over the clean background) ----------------
    tracked(d, (m, m), "XALAPA", f(86 * S, "r"), INK, ls=22 * S)
    tracked(d, (m + 3 * S, m + 116 * S),
            "VERACRUZ · MÉXICO", f(23 * S, "l"), SOFT, ls=9 * S)

    # ---- credit (bottom-left) --------------------------------------
    cred = "DEM: INEGI · LiDAR 5 m" + ("   ·   red vial OSM" if streets else "")
    tracked(d, (m, rh - m), cred, f(17 * S, "l"), SOFT, ls=2 * S)

    img.save(C.FINAL_PNG, quality=95)
    print("saved", C.FINAL_PNG, img.size)


if __name__ == "__main__":
    main()
