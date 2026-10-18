# -*- coding: utf-8 -*-
"""Small drawing helpers for the textbook figures (Pillow only)."""
import os
from PIL import Image, ImageDraw, ImageFont

SS = 2  # supersampling factor
FONT_CN = r"C:\Windows\Fonts\msyh.ttc"
FONT_CN_B = r"C:\Windows\Fonts\msyhbd.ttc"
FONT_MATH = r"C:\Windows\Fonts\cambria.ttc"
FONT_MONO = r"C:\Windows\Fonts\consola.ttf"

INK = (15, 23, 42)
BLUE = (29, 78, 216)
TEAL = (15, 118, 110)
AMBER = (180, 83, 9)
GRAY = (100, 116, 139)
LIGHT = (241, 245, 249)
RED = (185, 28, 28)
WHITE = (255, 255, 255)


def canvas(w, h, bg=WHITE):
    img = Image.new("RGB", (w * SS, h * SS), bg)
    return img, ImageDraw.Draw(img)


def font(size, kind="cn"):
    path = {"cn": FONT_CN, "cnb": FONT_CN_B, "math": FONT_MATH, "mono": FONT_MONO}[kind]
    return ImageFont.truetype(path, size * SS)


def text(d, x, y, s, size=22, color=INK, anchor="mm", kind="cn"):
    d.text((x * SS, y * SS), s, font=font(size, kind), fill=color, anchor=anchor)


def node(d, x, y, r=26, label="", fill=WHITE, outline=BLUE, width=3, size=22):
    d.ellipse([(x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS],
              fill=fill, outline=outline, width=width * SS)
    if label:
        text(d, x, y - 1, label, size=size, color=INK, kind="math")


def _arrowhead(d, p, q, color, size=12):
    import math
    (x1, y1), (x2, y2) = p, q
    ang = math.atan2(y2 - y1, x2 - x1)
    a = size * SS
    pts = [(x2 * SS, y2 * SS),
           ((x2) * SS - a * math.cos(ang - 0.4), (y2) * SS - a * math.sin(ang - 0.4)),
           ((x2) * SS - a * math.cos(ang + 0.4), (y2) * SS - a * math.sin(ang + 0.4))]
    d.polygon(pts, fill=color)


def arrow(d, p, q, color=BLUE, width=3, dashed=False, head=12):
    import math
    (x1, y1), (x2, y2) = p, q
    if dashed:
        dist = math.hypot(x2 - x1, y2 - y1)
        n = max(2, int(dist / 14))
        for i in range(n):
            if i % 2 == 0:
                t0, t1 = i / n, (i + 0.6) / n
                d.line([(x1 + (x2 - x1) * t0) * SS, (y1 + (y2 - y1) * t0) * SS,
                        (x1 + (x2 - x1) * t1) * SS, (y1 + (y2 - y1) * t1) * SS],
                       fill=color, width=width * SS)
    else:
        d.line([x1 * SS, y1 * SS, x2 * SS, y2 * SS], fill=color, width=width * SS)
    _arrowhead(d, p, q, color, head)


def self_loop(d, x, y, r=26, color=BLUE, label="", width=3):
    """A loop above the node, with an arrowhead at the right end."""
    import math
    cx, cy = x, y - r - 26
    rad = 26
    d.arc([(cx - rad) * SS, (cy - rad) * SS, (cx + rad) * SS, (cy + rad) * SS],
          start=200, end=520, fill=color, width=width * SS)
    # arrowhead at the lower-right end of the loop
    ang = math.radians(-20)
    px, py = cx + rad * math.cos(ang), cy + rad * math.sin(ang)
    _arrowhead(d, (px - 6, py - 6), (px, py), color, 11)
    if label:
        text(d, cx, cy - 10, label, size=20, color=color, kind="math")


def box(d, x, y, w, h, fill=LIGHT, outline=GRAY, width=2, radius=10):
    d.rounded_rectangle([x * SS, y * SS, (x + w) * SS, (y + h) * SS],
                        radius=radius * SS, fill=fill, outline=outline, width=width * SS)


def save(img, path):
    w, h = img.size
    img = img.resize((w // SS, h // SS), Image.LANCZOS)
    img.save(path, "PNG")
    print("saved", path, img.size)
