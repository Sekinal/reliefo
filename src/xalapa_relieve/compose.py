"""Compose the cut-out Xalapa relief plate into a vintage 1953-survey-style
poster: aged paper, double border, title cartouche, hypsometric LEYENDA
(stretched over the municipio's elevation range), graticule with degree
labels, place names and a survey footer. Pure PIL.
"""
from __future__ import annotations
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from . import config as C
from .make_textures import ramp

PAPER = (216, 206, 189)
INK = (60, 50, 40)
INK_SOFT = (118, 104, 86)
GRAT = (140, 124, 102)
FREG = "/usr/share/fonts/noto/NotoSerif-Regular.ttf"
FLIGHT = "/usr/share/fonts/noto/NotoSerif-Light.ttf"
FMED = "/usr/share/fonts/noto/NotoSerif-Medium.ttf"


def f(size, w="r"):
    return ImageFont.truetype({"r": FREG, "l": FLIGHT, "m": FMED}[w], int(size))


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


def paper_canvas(w, h):
    rng = np.random.default_rng(7)
    arr = np.clip(np.array(PAPER, float) + rng.normal(0, 6, (h, w, 1)), 0, 255)
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    vig = np.clip(1 - 0.16 * np.clip(d - 0.6, 0, None), 0.8, 1)[..., None]
    return Image.fromarray((arr * vig).clip(0, 255).astype(np.uint8), "RGB")


def fmt_deg(v, pos):
    d = int(abs(v)); m = int(round((abs(v) - d) * 60))
    return f"{d}°{m:02d}'{pos}"


def main():
    meta = json.loads(C.META_JSON.read_text())
    relief = Image.open(C.RENDER_PNG).convert("RGBA")
    rw, rh = relief.size
    pts = json.loads((C.OUT / "points.json").read_text())
    S = rw / 1700.0

    pad = int(0.05 * rh)
    legendW = int(0.42 * rh)
    titleH = int(0.20 * rh)
    footerH = int(0.10 * rh)
    rx, ry = pad + legendW, pad + titleH
    W = rx + rw + pad
    H = ry + rh + footerH + pad

    img = paper_canvas(W, H)
    d = ImageDraw.Draw(img)
    grid = pts["grid"]

    def gp(lo, la):
        x, y = grid["pts"][f"{lo},{la}"]
        return (x + rx, y + ry)

    # ---- graticule --------------------------------------------------
    for lo in grid["lons"]:
        d.line([gp(lo, la) for la in grid["lats"]], fill=GRAT, width=max(1, int(S)))
    for la in grid["lats"]:
        d.line([gp(lo, la) for lo in grid["lons"]], fill=GRAT, width=max(1, int(S)))
    fg = f(18 * S, "l")
    for lo in grid["lons"]:
        x, y = gp(lo, grid["lats"][0])
        tracked(d, (x, y + 8 * S), fmt_deg(lo, "O"), fg, INK_SOFT, ls=S, anchor="ma")
    for la in grid["lats"]:
        x, y = gp(grid["lons"][0], la)
        tracked(d, (x - 12 * S, y - 10 * S), fmt_deg(la, "N"), fg, INK_SOFT, ls=S, anchor="ra")

    img.paste(relief, (rx, ry), relief)

    # ---- place labels ----------------------------------------------
    big = {"Xalapa"}
    OFF = {"Xalapa": (16, -18, "la"), "El Castillo": (12, 6, "la"),
           "Las Trancas": (12, -26, "la")}
    for name, (px, py) in pts["places"].items():
        x, y = px + rx, py + ry
        r = int((7 if name in big else 4) * S)
        d.ellipse([x - r, y - r, x + r, y + r], fill=INK, outline=PAPER,
                  width=max(1, int(S)))
        dx, dy, anc = OFF.get(name, (10, -14, "la"))
        fnt = f((34 if name in big else 22) * S, "m" if name in big else "r")
        tracked(d, (x + dx * S, y + dy * S), name.upper() if name in big else name,
                fnt, INK, ls=3 * S if name in big else S, anchor=anc)

    # ---- double border ---------------------------------------------
    b = int(pad * 0.45)
    d.rectangle([b, b, W - b, H - b], outline=INK, width=max(2, int(2 * S)))
    d.rectangle([int(b * 1.5), int(b * 1.5), W - int(b * 1.5), H - int(b * 1.5)],
                outline=INK, width=max(1, int(S)))

    # ---- title cartouche -------------------------------------------
    cw, ch = int(rw * 0.50), int(titleH * 0.76)
    cx0 = rx + (rw - cw) // 2
    cy0 = pad + int(titleH * 0.06)
    d.rectangle([cx0, cy0, cx0 + cw, cy0 + ch], fill=PAPER, outline=INK,
                width=max(2, int(1.6 * S)))
    mx = cx0 + cw / 2
    tracked(d, (mx, cy0 + ch * 0.11), "MAPA DE RELIEVE", f(32 * S, "r"), INK,
            ls=9 * S, anchor="ma")
    tracked(d, (mx, cy0 + ch * 0.34), "DEL MUNICIPIO DE", f(18 * S, "l"), INK_SOFT,
            ls=6 * S, anchor="ma")
    tracked(d, (mx, cy0 + ch * 0.47), "XALAPA", f(48 * S, "m"), INK, ls=13 * S,
            anchor="ma")
    # scale bar (px/km from two adjacent meridians)
    la0 = grid["lats"][len(grid["lats"]) // 2]
    p1, p2 = gp(grid["lons"][0], la0), gp(grid["lons"][1], la0)
    km_per_step = abs(grid["lons"][1] - grid["lons"][0]) * 111.32 * np.cos(np.radians(19.54))
    ppk = abs(p2[0] - p1[0]) / km_per_step
    sblen = 5 * ppk
    sx = mx - sblen / 2; sy = cy0 + ch * 0.84
    d.line([(sx, sy), (sx + sblen, sy)], fill=INK, width=max(2, int(1.6 * S)))
    for i in range(6):
        xx = sx + sblen * i / 5
        d.line([(xx, sy - 5 * S), (xx, sy + 5 * S)], fill=INK, width=max(1, int(S)))
    tracked(d, (mx, sy - 24 * S), "0          5 km", f(15 * S, "l"), INK_SOFT,
            ls=2 * S, anchor="ma")

    # ---- legend (hypsometric, municipio range) ----------------------
    vmin, vmax = meta["elev_min"], meta["elev_max"]
    lx0 = pad + int(legendW * 0.12); lw = int(legendW * 0.76)
    ly0 = ry + int(rh * 0.05); lh = int(rh * 0.60)
    d.rectangle([lx0, ly0, lx0 + lw, ly0 + lh], fill=PAPER, outline=INK,
                width=max(2, int(1.4 * S)))
    tracked(d, (lx0 + lw / 2, ly0 + 18 * S), "LEYENDA", f(28 * S, "r"), INK,
            ls=8 * S, anchor="ma")
    tracked(d, (lx0 + lw / 2, ly0 + 52 * S), "Altitud (m s. n. m.)", f(17 * S, "l"),
            INK_SOFT, ls=S, anchor="ma")
    lut = ramp(256)
    bx0 = lx0 + int(26 * S); bx1 = bx0 + int(50 * S)
    by0 = ly0 + int(82 * S); by1 = ly0 + lh - int(24 * S)
    nseg = by1 - by0
    for i in range(nseg):
        cc = tuple(int(c) for c in lut[int((1 - i / nseg) * 255)])
        d.line([(bx0, by0 + i), (bx1, by0 + i)], fill=cc)
    d.rectangle([bx0, by0, bx1, by1], outline=INK, width=max(1, int(S)))
    lo_t = int(np.ceil(vmin / 200) * 200); hi_t = int(np.floor(vmax / 200) * 200)
    for e in range(lo_t, hi_t + 1, 200):
        yy = by0 + (1 - (e - vmin) / (vmax - vmin)) * (by1 - by0)
        d.line([(bx1, yy), (bx1 + 8 * S, yy)], fill=INK, width=max(1, int(S)))
        tracked(d, (bx1 + 14 * S, yy - 11 * S), f"{e:,}".replace(",", " "),
                f(18 * S, "l"), INK, ls=1)
    tracked(d, (lx0 + lw / 2, by1 + 10 * S),
            f"{vmin:.0f} – {vmax:.0f} m", f(16 * S, "l"), INK_SOFT, ls=1,
            anchor="ma")

    # ---- footer -----------------------------------------------------
    fy = H - pad - int(footerH * 0.55); mf = W / 2
    tracked(d, (mf, fy), "MODELO DIGITAL DE ELEVACION  ·  COPERNICUS DEM GLO-30 (ESA)",
            f(21 * S, "r"), INK, ls=4 * S, anchor="ma")
    tracked(d, (mf, fy + 28 * S),
            "Recorte: Marco Geoestadistico INEGI  ·  Render Blender  ·  2026",
            f(16 * S, "l"), INK_SOFT, ls=2 * S, anchor="ma")

    img.convert("RGB").save(C.FINAL_PNG, quality=95)
    print("saved", C.FINAL_PNG, img.size)


if __name__ == "__main__":
    main()
