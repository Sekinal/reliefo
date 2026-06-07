"""Compose the rendered relief plate into a vintage 1953-survey-style plate:
aged paper, double border, title cartouche, hypsometric LEYENDA, graticule
with degree labels, place names and a survey-style footer. Pure PIL.
"""
from __future__ import annotations
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from . import config as C
from .make_textures import STOPS

PAPER = (216, 206, 189)
INK = (62, 52, 42)
INK_SOFT = (120, 106, 88)
GRAT = (138, 122, 100)
FONT = "/usr/share/fonts/noto/NotoSerif-Regular.ttf"
FONT_L = "/usr/share/fonts/noto/NotoSerif-Light.ttf"
FONT_M = "/usr/share/fonts/noto/NotoSerif-Medium.ttf"


def f(size, w="r"):
    return ImageFont.truetype({"r": FONT, "l": FONT_L, "m": FONT_M}[w], size)


def tracked(draw, xy, text, font, fill, ls=0, anchor="la"):
    """draw text with letter-spacing; returns total width."""
    x, y = xy
    widths = [draw.textlength(c, font=font) for c in text]
    total = sum(widths) + ls * (len(text) - 1)
    if "m" in anchor:  # middle horizontal
        x -= total / 2
    elif "r" in anchor:
        x -= total
    for c, w in zip(text, widths):
        draw.text((x, y), c, font=font, fill=fill)
        x += w + ls
    return total


def paper_canvas(w, h):
    rng = np.random.default_rng(7)
    base = np.array(PAPER, dtype=np.float64)
    noise = rng.normal(0, 6, (h, w, 1))
    arr = np.clip(base + noise, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr, "RGB")
    # soft vignette
    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy = w / 2, h / 2
    d = np.sqrt(((xx - cx) / (w / 2)) ** 2 + ((yy - cy) / (h / 2)) ** 2)
    vig = np.clip(1 - 0.16 * np.clip(d - 0.6, 0, None), 0.8, 1)[..., None]
    img = Image.fromarray((np.asarray(img) * vig).clip(0, 255).astype(np.uint8))
    return img


def fmt_deg(v, pos):
    d = int(abs(v)); m = int(round((abs(v) - d) * 60))
    return f"{d}°{m:02d}'{pos}"


def main():
    relief = Image.open(C.RENDER_PNG).convert("RGBA")
    rw, rh = relief.size
    pts = json.loads((C.OUT / "points.json").read_text())
    S = rw / 1700.0  # scale factor

    pad = int(0.05 * rh)
    legendW = int(0.40 * rh)
    titleH = int(0.205 * rh)
    footerH = int(0.105 * rh)
    rx, ry = pad + legendW, pad + titleH
    W = rx + rw + pad
    H = ry + rh + footerH + pad

    img = paper_canvas(W, H)
    d = ImageDraw.Draw(img)

    # ---- graticule (under the relief edges, on the paper) -----------
    grid = pts["grid"]
    def gp(lo, la):
        x, y = grid["pts"][f"{lo},{la}"]
        return (x + rx, y + ry)
    for lo in grid["lons"]:
        line = [gp(lo, la) for la in grid["lats"]]
        d.line(line, fill=GRAT, width=max(1, int(S)))
    for la in grid["lats"]:
        line = [gp(lo, la) for lo in grid["lons"]]
        d.line(line, fill=GRAT, width=max(1, int(S)))
    # degree labels along bottom (lons) and left (lats)
    fg = f(int(20 * S), "l")
    for lo in grid["lons"]:
        x, y = gp(lo, grid["lats"][0])
        tracked(d, (x, y + 8 * S), fmt_deg(lo, "O"), fg, INK_SOFT, ls=S, anchor="ma")
    for la in grid["lats"]:
        x, y = gp(grid["lons"][0], la)
        tracked(d, (x - 12 * S, y - 10 * S), fmt_deg(la, "N"), fg, INK_SOFT, ls=S, anchor="ra")

    # ---- relief plate ----------------------------------------------
    img.paste(relief, (rx, ry), relief)

    # ---- place labels ----------------------------------------------
    big = {"Xalapa"}
    # per-label text offset (dx, dy) and anchor, to dodge peaks/edges
    OFF = {"Cofre de Perote": (14, 10, "la"), "Perote": (-12, -28, "ra"),
           "Banderilla": (10, -26, "la"), "Coatepec": (10, 4, "la"),
           "Xalapa": (14, -16, "la")}
    for name, (px, py) in pts["places"].items():
        x, y = px + rx, py + ry
        peak = name == "Cofre de Perote"
        r = int((6 if name in big else 4) * S)
        if peak:  # little triangle for the volcano
            s = int(7 * S)
            d.polygon([(x, y - s), (x - s, y + s), (x + s, y + s)],
                      fill=INK, outline=PAPER)
        else:
            d.ellipse([x - r, y - r, x + r, y + r], fill=INK,
                      outline=PAPER, width=max(1, int(S)))
        dx, dy, anc = OFF.get(name, (10, -14, "la"))
        fnt = f(int((30 if name in big else 22) * S), "m" if name in big else "r")
        tracked(d, (x + dx * S, y + dy * S),
                name.upper() if name in big else name,
                fnt, INK, ls=2 * S if name in big else S, anchor=anc)

    # ---- double border frame ---------------------------------------
    b = int(pad * 0.45)
    d.rectangle([b, b, W - b, H - b], outline=INK, width=max(2, int(2 * S)))
    d.rectangle([int(b * 1.5), int(b * 1.5), W - int(b * 1.5), H - int(b * 1.5)],
                outline=INK, width=max(1, int(S)))

    # ---- title cartouche -------------------------------------------
    cw, ch = int(rw * 0.52), int(titleH * 0.74)
    cx0 = rx + (rw - cw) // 2
    cy0 = pad + int(titleH * 0.08)
    d.rectangle([cx0, cy0, cx0 + cw, cy0 + ch], fill=PAPER, outline=INK,
                width=max(2, int(1.6 * S)))
    midx = cx0 + cw / 2
    tracked(d, (midx, cy0 + ch * 0.10), "MAPA DE RELIEVE", f(int(34 * S), "r"),
            INK, ls=9 * S, anchor="ma")
    tracked(d, (midx, cy0 + ch * 0.33), "DE LA REGION DE", f(int(19 * S), "l"),
            INK_SOFT, ls=6 * S, anchor="ma")
    tracked(d, (midx, cy0 + ch * 0.47), "XALAPA", f(int(46 * S), "m"),
            INK, ls=12 * S, anchor="ma")
    # scale bar
    sb_km = 20.0
    px_per_km = rw / (C.BBOX["east"] - C.BBOX["west"]) / 111.32 / \
        np.cos(np.radians(19.5)) if False else rw / 97.0  # ~plate km
    sblen = sb_km * (rw / 97.0)
    sx = midx - sblen / 2
    sy = cy0 + ch * 0.86
    d.line([(sx, sy), (sx + sblen, sy)], fill=INK, width=max(2, int(1.6 * S)))
    for i in range(5):
        xx = sx + sblen * i / 4
        d.line([(xx, sy - 5 * S), (xx, sy + 5 * S)], fill=INK, width=max(1, int(S)))
    tracked(d, (midx, sy - 26 * S), "0          10          20 km", f(int(15 * S), "l"),
            INK_SOFT, ls=2 * S, anchor="ma")

    # ---- legend (hypsometric) --------------------------------------
    lx0 = pad + int(legendW * 0.12)
    lw = int(legendW * 0.76)
    ly0 = ry + int(rh * 0.04)
    lh = int(rh * 0.62)
    d.rectangle([lx0, ly0, lx0 + lw, ly0 + lh], fill=PAPER, outline=INK,
                width=max(2, int(1.4 * S)))
    tracked(d, (lx0 + lw / 2, ly0 + 18 * S), "LEYENDA", f(int(28 * S), "r"),
            INK, ls=8 * S, anchor="ma")
    tracked(d, (lx0 + lw / 2, ly0 + 52 * S), "Altitud (m s. n. m.)",
            f(int(17 * S), "l"), INK_SOFT, ls=1 * S, anchor="ma")
    # vertical gradient bar from STOPS
    bx0 = lx0 + int(20 * S); bx1 = bx0 + int(48 * S)
    by0 = ly0 + int(80 * S); by1 = ly0 + lh - int(28 * S)
    elevs = [s[0] for s in STOPS]; emin, emax = min(elevs), max(elevs)
    nseg = by1 - by0
    for i in range(nseg):
        e = emax - (i / nseg) * (emax - emin)
        # interp colour
        cols = [tuple(int(s[1][j:j+2], 16) for j in (1, 3, 5)) for s in STOPS]
        cc = [int(np.interp(e, elevs, [c[k] for c in cols])) for k in range(3)]
        d.line([(bx0, by0 + i), (bx1, by0 + i)], fill=tuple(cc))
    d.rectangle([bx0, by0, bx1, by1], outline=INK, width=max(1, int(S)))
    for e in [0, 1000, 2000, 3000, 4000]:
        yy = by0 + (1 - (e - emin) / (emax - emin)) * (by1 - by0)
        d.line([(bx1, yy), (bx1 + 8 * S, yy)], fill=INK, width=max(1, int(S)))
        tracked(d, (bx1 + 14 * S, yy - 11 * S), f"{e:,}".replace(",", " "),
                f(int(19 * S), "l"), INK, ls=1)
    tracked(d, (lx0 + lw / 2, by1 + 8 * S), "Cofre de Perote · 4 282 m",
            f(int(16 * S), "l"), INK_SOFT, ls=1, anchor="ma")

    # ---- footer -----------------------------------------------------
    fy = H - pad - int(footerH * 0.55)
    midf = W / 2
    tracked(d, (midf, fy), "MODELO DIGITAL DE ELEVACION  ·  COPERNICUS DEM GLO-30 (ESA)",
            f(int(22 * S), "r"), INK, ls=4 * S, anchor="ma")
    tracked(d, (midf, fy + 30 * S),
            "Renderizado con Blender (Cycles)  ·  Elaboracion propia  ·  2026",
            f(int(17 * S), "l"), INK_SOFT, ls=2 * S, anchor="ma")

    img.convert("RGB").save(C.FINAL_PNG, quality=95)
    print("saved", C.FINAL_PNG, img.size)


if __name__ == "__main__":
    main()
