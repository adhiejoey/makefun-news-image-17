#!/usr/bin/env python3
"""make.fun entry: news-image-20261117 -- "The World in One Day".

Draws one 1024x1024 PNG that sums up the world news of Tuesday
17 November 2026: a newspaper front page with a masthead naming the day,
a lead story (NVIDIA's record earnings) and six more stories across
regions and fields (Iran, Kerch Bridge, Trump in Asia, Japan, Gaza,
measles), each with its own pictogram and short labels, plus a footer
of further briefs from the same day.

Standard library only (zlib, struct, hashlib, os, sys). No network,
no files read besides fontdata.py beside this file. The output is fully
deterministic: two runs write byte-identical PNGs.

Run:  mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
"""
import hashlib
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fontdata import FONTS  # noqa: E402  (generated bitmap font)

W, H = 1024, 1024

PAPER = (247, 243, 234)
INK = (16, 24, 40)
NAVY = (16, 35, 63)
NAVY2 = (24, 52, 92)
GOLD = (201, 162, 39)
GOLD_LT = (232, 205, 120)
WHITE = (255, 255, 255)
CARD = (255, 255, 255)
BODY = (52, 60, 74)
MUTED = (110, 116, 130)
RED = (176, 38, 38)
BLUE = (36, 84, 160)
TEAL = (14, 122, 122)
GREEN = (34, 120, 62)
PURPLE = (104, 68, 150)
ORANGE = (196, 94, 20)
NV_GREEN = (74, 140, 0)


# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.px = bytearray(w * h * 3)
        self.fill_rect(0, 0, w, h, bg)

    def set(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i], self.px[i + 1], self.px[i + 2] = color

    def fill_rect(self, x, y, w, h, color):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        r, g, b = color
        for yy in range(y0, y1):
            base = (yy * self.w + x0) * 3
            for xx in range(x0, x1):
                i = base + (xx - x0) * 3
                self.px[i], self.px[i + 1], self.px[i + 2] = r, g, b

    def rect(self, x, y, w, h, color, t=1):
        self.fill_rect(x, y, w, t, color)
        self.fill_rect(x, y + h - t, w, t, color)
        self.fill_rect(x, y, t, h, color)
        self.fill_rect(x + w - t, y, t, h, color)

    def hline(self, x0, x1, y, color, t=1):
        for yy in range(y, y + t):
            for xx in range(min(x0, x1), max(x0, x1) + 1):
                self.set(xx, yy, color)

    def vline(self, x, y0, y1, color, t=1):
        for xx in range(x, x + t):
            for yy in range(min(y0, y1), max(y0, y1) + 1):
                self.set(xx, yy, color)

    def line(self, x0, y0, x1, y1, color, t=1):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        x, y = x0, y0
        while True:
            for a in range(t):
                for b in range(t):
                    self.set(x + a, y + b, color)
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x += sx
            if e2 <= dx:
                err += dx
                y += sy

    def fill_circle(self, cx, cy, r, color):
        for yy in range(cy - r, cy + r + 1):
            dx = int((r * r - (yy - cy) * (yy - cy)) ** 0.5) if abs(yy - cy) <= r else 0
            for xx in range(cx - dx, cx + dx + 1):
                self.set(xx, yy, color)

    def circle(self, cx, cy, r, color, t=2):
        import math
        steps = max(24, int(2 * math.pi * r))
        prev = None
        for i in range(steps + 1):
            a = 2 * math.pi * i / steps
            p = (int(cx + r * math.cos(a)), int(cy + r * math.sin(a)))
            if prev is not None:
                self.line(prev[0], prev[1], p[0], p[1], color, t)
            prev = p

    def fill_poly(self, pts, color):
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        for y in range(min(ys), max(ys) + 1):
            xs = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    x = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
                    xs.append(x)
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                for x in range(int(xs[k]), int(xs[k + 1]) + 1):
                    self.set(x, y, color)


# ------------------------------------------------------------------- text
def text_width(s, scale=1, size=20):
    _h, glyphs = FONTS[size]
    total = 0
    for ch in s:
        g = glyphs.get(ch)
        if g is None:
            total += 8 * scale
        else:
            total += g[0] * scale
    return total


def draw_text(cv, s, x, y, scale, color, size=20):
    _height, glyphs = FONTS[size]
    pen = x
    for ch in s:
        g = glyphs.get(ch)
        if g is None:
            pen += 8 * scale
            continue
        adv, off, w, rows = g
        for row_i, bits in enumerate(rows):
            if not bits:
                continue
            for j in range(w):
                if bits & (1 << (w - 1 - j)):
                    bx = pen + (off + j) * scale
                    by = y + row_i * scale
                    cv.fill_rect(bx, by, scale, scale, color)
        pen += adv * scale
    return pen


def draw_centered(cv, s, cx, y, scale, color, size=20):
    draw_text(cv, s, cx - text_width(s, scale, size) // 2, y, scale, color, size)


def wrap(text, max_w, scale=1, size=20):
    words = text.split(" ")
    lines, cur = [], ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if text_width(trial, scale, size) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_lines(cv, lines, x, y, scale, color, leading, size=20):
    for i, ln in enumerate(lines):
        draw_text(cv, ln, x, y + i * leading, scale, color, size)


# -------------------------------------------------------------- pictograms
def pic_burst(cv, cx, cy, r, c1, c2):
    import math
    pts = []
    for i in range(24):
        a = math.pi * i / 12
        rr = r if i % 2 == 0 else int(r * 0.45)
        pts.append((int(cx + rr * math.cos(a)), int(cy + rr * math.sin(a))))
    cv.fill_poly(pts, c1)
    cv.fill_circle(cx, cy, int(r * 0.34), c2)


def pic_bridge(cv, x, y, w, h, color, deck):
    cv.fill_rect(x, y + h // 2, w, 6, deck)
    cv.line(x + 8, y + h // 2, x + w // 2, y + 8, color, 4)
    cv.line(x + w // 2, y + 8, x + w - 8, y + h // 2, color, 4)
    for fx in (w // 4, w // 2, 3 * w // 4):
        cv.vline(x + fx, y + 16, y + h // 2, color, 3)
    cv.fill_rect(x + 6, y + h // 2 + 6, 8, h // 2 - 6, deck)
    cv.fill_rect(x + w - 14, y + h // 2 + 6, 8, h // 2 - 6, deck)
    for wy in (y + h - 12, y + h - 4):
        for wx in range(x, x + w, 18):
            cv.line(wx, wy, wx + 9, wy + 4, color, 2)


def pic_globe(cv, cx, cy, r, color, dot):
    cv.circle(cx, cy, r, color, 4)
    cv.circle(cx, cy, int(r * 0.55), color, 3)
    cv.line(cx - r, cy, cx + r, cy, color, 3)
    cv.line(cx, cy - r, cx, cy + r, color, 3)
    for dx, dy in ((-r // 2, -r // 3), (r // 3, r // 4), (0, -r // 2)):
        cv.fill_circle(cx + dx, cy + dy, 6, dot)


def pic_jet(cv, x, y, w, h, color, sun):
    cv.fill_circle(x + w - 22, y + 22, 18, sun)
    pts = [(x + 8, y + h // 2 + 4), (x + w - 30, y + h // 2 - 14),
           (x + w - 6, y + h // 2 - 4), (x + w - 30, y + h // 2 + 6),
           (x + w - 52, y + h - 8), (x + w - 62, y + h // 2 + 10),
           (x + w - 78, y + h // 2 + 14)]
    cv.fill_poly(pts, color)
    cv.line(x, y + h - 14, x + w - 70, y + h - 14, MUTED, 2)
    cv.line(x + 10, y + h - 4, x + w - 80, y + h - 4, MUTED, 2)


def pic_aid(cv, cx, cy, s, color):
    cv.fill_rect(cx - s // 2, cy - s // 2, s, s, WHITE)
    cv.rect(cx - s // 2, cy - s // 2, s, s, color, 3)
    cv.fill_rect(cx - 7, cy - s // 2 + 14, 14, s - 28, color)
    cv.fill_rect(cx - s // 2 + 14, cy - 7, s - 28, 14, color)


def pic_virus(cv, cx, cy, r, color):
    import math
    for i in range(8):
        a = math.pi * i / 4
        x1 = int(cx + r * math.cos(a))
        y1 = int(cy + r * math.sin(a))
        x2 = int(cx + (r + 12) * math.cos(a))
        y2 = int(cy + (r + 12) * math.sin(a))
        cv.line(x1, y1, x2, y2, color, 4)
        cv.fill_circle(x2, y2, 5, color)
    cv.fill_circle(cx, cy, r, color)
    cv.fill_circle(cx - 8, cy - 8, 6, WHITE)
    cv.fill_circle(cx + 10, cy + 6, 4, WHITE)


def pic_chip(cv, x, y, s, color, arrow):
    for k in range(3):
        cv.fill_rect(x - 12, y + 14 + k * 22, 12, 6, color)
        cv.fill_rect(x + s, y + 14 + k * 22, 12, 6, color)
        cv.fill_rect(x + 14 + k * 22, y - 12, 6, 12, color)
        cv.fill_rect(x + 14 + k * 22, y + s, 6, 12, color)
    cv.fill_rect(x, y, s, s, color)
    cv.fill_rect(x + 14, y + 14, s - 28, s - 28, WHITE)
    cv.line(x + 22, y + s - 22, x + s // 2, y + 26, arrow, 5)
    cv.line(x + s // 2, y + 26, x + s - 22, y + 40, arrow, 5)
    cv.line(x + s - 22, y + 40, x + s - 22, y + 26, arrow, 5)
    cv.line(x + s - 22, y + 40, x + s - 36, y + 40, arrow, 5)


# ------------------------------------------------------------------ layout
STORIES = [
    # kicker, title, body, accent, pictogram key
    ("MIDDLE EAST", "US STRIKES IRAN",
     "US jets hit Iranian missile sites after tanker attacks in the Strait "
     "of Hormuz. Iran drones a US radar base in Bahrain.",
     RED, "burst"),
    ("UKRAINE WAR", "KERCH BRIDGE HIT",
     "Ukrainian drones collapse a section of the Kerch Bridge to Crimea. "
     "Russia hits bridges in Kyiv in reply.",
     BLUE, "bridge"),
    ("DIPLOMACY", "TRUMP'S ASIA TRIP",
     "Trump opens his Asia trip with a Quad summit in Manila, ahead of a "
     "three-way summit with Xi and Putin in China.",
     NAVY2, "globe"),
    ("ASIA SECURITY", "JAPAN SENDS JETS",
     "Japan sends fighter jets up after Russian aircraft enter its "
     "airspace. Tokyo lodges a strong protest.",
     TEAL, "jet"),
    ("HUMANITARIAN", "GAZA AID PLEA",
     "Britain, Australia, Canada and Italy urge Israel to open Gaza "
     "crossings as aid groups warn of catastrophe.",
     GREEN, "aid"),
    ("HEALTH", "MEASLES RETURNS",
     "The US loses its measles elimination status for the first time since "
     "2000 as vaccination rates fall.",
     PURPLE, "virus"),
]

LEAD_BODY = ("Chip giant reports record quarterly revenue of $115.8 billion, "
             "beating forecasts. Its board refuses to reinstate ex-CEO Jensen "
             "Huang, who resigned days earlier in a spy scandal.")

FOOTER = ("ALSO: Depardieu admits assault  -  Tiger Woods returns to golf  -  "
          "Mongolia's president quits")


def tint(color, bg, f=0.13):
    return tuple(int(c * f + b * (1 - f)) for c, b in zip(color, bg))


def draw_panel(cv, x, y, w, h, story):
    kicker, title, body, accent, pic = story
    cv.fill_rect(x, y, w, h, CARD)
    cv.rect(x, y, w, h, (214, 208, 194), 1)
    cv.fill_rect(x, y, w, 8, accent)
    # pictogram band
    band_h = 76
    cv.fill_rect(x + 1, y + 9, w - 2, band_h, tint(accent, PAPER, 0.10))
    cx, cy = x + w // 2, y + 9 + band_h // 2
    if pic == "burst":
        pic_burst(cv, cx, cy, 26, ORANGE, RED)
    elif pic == "bridge":
        pic_bridge(cv, cx - 62, cy - 26, 124, 54, BLUE, NAVY)
    elif pic == "globe":
        pic_globe(cv, cx, cy, 28, NAVY2, GOLD)
    elif pic == "jet":
        pic_jet(cv, cx - 62, cy - 24, 124, 50, TEAL, RED)
    elif pic == "aid":
        pic_aid(cv, cx, cy, 50, GREEN)
    elif pic == "virus":
        pic_virus(cv, cx, cy, 19, PURPLE)
    ty = y + 9 + band_h + 10
    draw_text(cv, kicker, x + 18, ty, 1, accent)
    title_lines = wrap(title, w - 36, 2)
    draw_lines(cv, title_lines, x + 18, ty + 26, 2, INK, 40)
    body_lines = wrap(body, w - 36, 1, 16)
    draw_lines(cv, body_lines, x + 18, ty + 26 + len(title_lines) * 40 + 6,
               1, BODY, 21, 16)


def build():
    cv = Canvas(W, H, PAPER)
    # masthead
    cv.fill_rect(0, 0, W, 140, NAVY)
    draw_centered(cv, "THE WORLD IN ONE DAY", W // 2, 16, 3, WHITE)
    draw_centered(cv, "TUESDAY, 17 NOVEMBER 2026", W // 2, 88, 2, GOLD_LT)
    cv.fill_rect(0, 140, W, 4, GOLD)
    # lead story
    lx, ly, lw, lh = 16, 156, 992, 168
    cv.fill_rect(lx, ly, lw, lh, CARD)
    cv.rect(lx, ly, lw, lh, (214, 208, 194), 1)
    cv.fill_rect(lx, ly, 10, lh, NV_GREEN)
    draw_text(cv, "LEAD  -  MARKETS", lx + 30, ly + 14, 1, NV_GREEN)
    draw_text(cv, "NVIDIA SMASHES RECORDS", lx + 30, ly + 40, 2, INK)
    body_lines = wrap(LEAD_BODY, 800, 1)
    draw_lines(cv, body_lines, lx + 30, ly + 96, 1, BODY, 25)
    pic_chip(cv, lx + lw - 128, ly + 52, 72, NV_GREEN, GOLD)
    # story grid: 3 cols x 2 rows
    cols_x = [16, 351, 686]
    rows_y = [336, 662]
    pw, ph = 322, 314
    for i, story in enumerate(STORIES):
        draw_panel(cv, cols_x[i % 3], rows_y[i // 3], pw, ph, story)
    # footer
    cv.fill_rect(0, 988, W, 36, NAVY)
    draw_centered(cv, FOOTER, W // 2, 994, 1, WHITE, 16)
    return cv


# --------------------------------------------------------------------- png
def png_bytes(cv):
    raw = bytearray()
    stride = cv.w * 3
    for y in range(cv.h):
        raw.append(0)
        raw += cv.px[y * stride:(y + 1) * stride]

    def chunk(kind, data):
        out = struct.pack(">I", len(data)) + kind + data
        out += struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


def main():
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(outdir, exist_ok=True)
    data = png_bytes(build())
    path = os.path.join(outdir, "entry.png")
    with open(path, "wb") as fh:
        fh.write(data)
    print("wrote %s (%d bytes, sha256 %s)"
          % (path, len(data), hashlib.sha256(data).hexdigest()))


if __name__ == "__main__":
    main()
