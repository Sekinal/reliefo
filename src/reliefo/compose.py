"""Compose the cut-out relief onto a clean, modern minimal poster (joewdavies
style): soft light background, the floating monochrome plate, restrained spaced
serif type, a translucent-chip zone labels layer (when streets are on) and an
elevation colour scale. All text comes from the config.
"""
from __future__ import annotations

import json

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import gaussian_filter

from ._util import info, step
from .config import Config
from .textures import gamma, ramp

INK = (38, 46, 56)
SOFT = (96, 108, 122)
BG = (234, 235, 237)

# serif faces, tried in order; falls back to PIL's default if none are present
_SERIF = {
    "r": ["/usr/share/fonts/noto/NotoSerif-Regular.ttf",
          "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"],
    "l": ["/usr/share/fonts/noto/NotoSerif-Light.ttf",
          "/usr/share/fonts/noto/NotoSerif-Regular.ttf",
          "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"],
    "i": ["/usr/share/fonts/noto/NotoSerif-Italic.ttf",
          "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf"],
}


def f(size: float, w: str = "r") -> ImageFont.FreeTypeFont:
    for path in _SERIF[w]:
        try:
            return ImageFont.truetype(path, int(size))
        except OSError:
            continue
    return ImageFont.load_default(int(size))


def tracked(draw, xy, text, font, fill, ls=0, anchor="la"):
    x, y = xy
    ws = [draw.textlength(c, font=font) for c in text]
    total = sum(ws) + ls * (len(text) - 1)
    if "m" in anchor:
        x -= total / 2
    elif "r" in anchor:
        x -= total
    for c, w in zip(text, ws, strict=True):
        draw.text((x, y), c, font=font, fill=fill)
        x += w + ls
    return total


def clean_bg(w, h):
    yy, xx = np.mgrid[0:h, 0:w]
    grad = (xx / w * 0.5 + yy / h * 0.5)
    base = np.array(BG, float)[None, None, :]
    img = base - grad[..., None] * np.array([10, 10, 11])
    d = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    vig = np.clip(1 - 0.10 * np.clip(d - 0.7, 0, None), 0.86, 1)[..., None]
    img = img * vig
    img += np.random.default_rng(3).normal(0, 1.4, (h, w, 1))
    return Image.fromarray(img.clip(0, 255).astype(np.uint8), "RGB")


def warm_bloom(img, relief, strength=0.45, sigma=7):
    a = np.asarray(relief).astype(np.float64)
    rgb, alpha = a[..., :3], a[..., 3:4] / 255.0
    warm = np.clip((rgb[..., 0] - rgb[..., 2]) / 255.0, 0, 1)
    bright = np.clip(rgb.mean(2) / 255.0 - 0.45, 0, 1)
    src = ((warm ** 1.3) * bright)[..., None] * np.array([255, 205, 120.]) * alpha
    glow = np.stack([gaussian_filter(src[..., k], sigma) for k in range(3)], -1)
    out = np.asarray(img).astype(np.float64)
    out = 255 - (255 - out) * (255 - np.clip(glow * strength, 0, 255)) / 255
    return Image.fromarray(out.clip(0, 255).astype(np.uint8))


def label_zones(cfg: Config, img, S):
    pts = json.loads(cfg.points_json.read_text())
    zones = pts.get("zones", [])
    if not zones:
        return img
    big = {"city", "town", "suburb"}
    zones.sort(key=lambda z: (z["place"] not in big, -z.get("n", 0)))
    d0 = ImageDraw.Draw(img)
    placed, chosen = [], []
    px_, py_ = 13 * S, 7 * S
    gap = 10 * S
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

    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    do = ImageDraw.Draw(ov)
    for x, y, _name, _fnt, _ls, w, h in chosen:
        do.rounded_rectangle([x - w / 2 - px_, y - py_, x + w / 2 + px_, y + h + py_],
                             radius=h * 0.5, fill=(247, 248, 249, 200))
    img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")

    d = ImageDraw.Draw(img)
    for x, y, name, fnt, ls, _w, _h in chosen:
        tracked(d, (x, y), name, fnt, (26, 32, 44), ls=ls, anchor="ma")
    info(f"{len(chosen)} zone labels placed")
    return img


def color_legend(img, S, vmin, vmax, palette):
    import math
    lut = ramp(palette, 256)
    g = gamma(palette)
    m = int(70 * S)
    bw, bh = int(22 * S), int(300 * S)
    x0, y0 = img.width - m - bw, img.height - m - bh
    col = np.array([lut[int(((1 - i / (bh - 1)) ** g) * 255)] for i in range(bh)])
    bar = np.repeat(col[:, None, :], bw, axis=1).clip(0, 255).astype(np.uint8)
    img.paste(Image.fromarray(bar, "RGB"), (x0, y0))
    d = ImageDraw.Draw(img)
    d.rectangle([x0, y0, x0 + bw - 1, y0 + bh - 1],
                outline=(208, 211, 216), width=max(1, int(S)))
    tracked(d, (x0 + bw / 2, y0 - 34 * S), "ALTITUD", f(19 * S, "l"),
            SOFT, ls=6 * S, anchor="ma")
    fnt = f(17 * S, "l")
    span = max(vmax - vmin, 1.0)
    for e in range(int(math.ceil(vmin / 300) * 300), int(vmax) + 1, 300):
        y = y0 + (1 - (e - vmin) / span) * bh
        d.line([(x0 - 8 * S, y), (x0 - 1, y)], fill=SOFT, width=max(1, int(S)))
        tracked(d, (x0 - 14 * S, y - fnt.size / 2), f"{e:,}".replace(",", " "),
                fnt, SOFT, ls=1 * S, anchor="ra")
    tracked(d, (x0 + bw / 2, y0 + bh + 12 * S), "m s. n. m.", f(13 * S, "i"),
            SOFT, ls=1 * S, anchor="ma")


def _overlays(cfg, img, S, meta, streets):
    """Elevation legend + title + subtitle + credit, drawn in place."""
    color_legend(img, S, meta["elev_min"], meta["elev_max"], cfg.relief.palette)
    d = ImageDraw.Draw(img)
    m = int(70 * S)
    tracked(d, (m, m), cfg.map.headline, f(86 * S, "r"), INK, ls=22 * S)
    if cfg.map.subtitle:
        tracked(d, (m + 3 * S, m + 116 * S),
                cfg.map.subtitle, f(23 * S, "l"), SOFT, ls=9 * S)
    cred = f"DEM: {meta['source']}" + ("   ·   red vial OSM" if streets else "")
    tracked(d, (m, img.height - m), cred, f(17 * S, "l"), SOFT, ls=2 * S)
    return img


def build(cfg: Config) -> None:
    step("compose")
    relief = Image.open(cfg.render_png).convert("RGBA")
    rw, rh = relief.size
    S = rw / 2000.0
    streets = cfg.emission_png.exists()
    meta = json.loads(cfg.meta_json.read_text())

    def base():
        img = clean_bg(rw, rh)
        img.paste(relief, (0, 0), relief)
        return img

    if streets:
        # B — streets, no names
        b = _overlays(cfg, warm_bloom(base(), relief), S, meta, True)
        b.save(cfg.poster_streets_png, quality=95)
        # C — streets + names
        c = label_zones(cfg, warm_bloom(base(), relief), S)
        c = _overlays(cfg, c, S, meta, True)
        c.save(cfg.poster_streets_names_png, quality=95)
        info(f"saved {cfg.poster_streets_png.name} + {cfg.poster_streets_names_png.name}")
    else:
        # A — clean (relief + legend + title)
        a = _overlays(cfg, base(), S, meta, False)
        a.save(cfg.poster_png, quality=95)
        info(f"saved {cfg.poster_png.name}")
