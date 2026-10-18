# -*- coding: utf-8 -*-
"""Generate all figures for the textbook."""
import math, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from figlib import *
from figlib import _arrowhead
from PIL import Image, ImageDraw, ImageFont

OUT = r"D:\AI\AFARules\figures"
os.makedirs(OUT, exist_ok=True)


def edge_pt(p, q, r):
    dx, dy = q[0] - p[0], q[1] - p[1]
    d = math.hypot(dx, dy) or 1
    return (p[0] + dx / d * r, p[1] + dy / d * r)


def node_arrow(d, p, q, r=26, color=BLUE, width=3, label=None, dashed=False,
               lx=None, ly=None, size=20, lcolor=None):
    a = edge_pt(p, q, r)
    b = edge_pt(q, p, r)
    arrow(d, a, b, color=color, width=width, dashed=dashed)
    if label:
        mx = (a[0] + b[0]) / 2 if lx is None else lx
        my = (a[1] + b[1]) / 2 if ly is None else ly
        text(d, mx, my - 14, label, size=size, color=lcolor or color, kind="math")


def loop(d, x, y, r=26, color=BLUE, label=None, size=20, up=None):
    cy = y - r - 20 if up is None else y - up
    rad = 22
    d.ellipse([(x - rad) * SS, (cy - rad) * SS, (x + rad) * SS, (cy + rad) * SS],
              outline=color, width=3 * SS)
    # arrowhead on the right side, pointing down (clockwise)
    _arrowhead(d, (x + rad, cy - 4), (x + rad, cy + 8), color, 11)
    if label:
        text(d, x, cy - 12, label, size=size, color=color, kind="math")


# ---------------------------------------------------------------- cover
def cover():
    W, H = 1600, 560
    img, d = canvas(W, H, (12, 20, 38))
    # dot grid
    for x in range(40, W, 40):
        for y in range(40, H, 40):
            d.ellipse([(x - 1) * SS, (y - 1) * SS, (x + 1) * SS, (y + 1) * SS],
                      fill=(24, 36, 60))
    # big faint Omega
    text(d, 1180, 280, "Ω", size=300, color=(22, 34, 58), kind="math")
    # cycle
    pts = [(250, 330), (390, 180), (520, 330)]
    for i in range(3):
        node_arrow(d, pts[i], pts[(i + 1) % 3], r=22, color=(96, 165, 250), width=3)
    for p in pts:
        node(d, p[0], p[1], 22, "", fill=(12, 20, 38), outline=(147, 197, 253), width=3)
        d.ellipse([(p[0]-4)*SS, (p[1]-4)*SS, (p[0]+4)*SS, (p[1]+4)*SS], fill=(147, 197, 253))
    # chain
    xs = [700, 830, 960, 1090]
    ys = [310, 250, 350, 290]
    for i in range(len(xs) - 1):
        node_arrow(d, (xs[i], ys[i]), (xs[i+1], ys[i+1]), r=14,
                   color=(45, 212, 191), width=2)
    for i, (x, y) in enumerate(zip(xs, ys)):
        node(d, x, y, 12, "", fill=(12, 20, 38), outline=(94, 234, 212), width=2)
    save(img, os.path.join(OUT, "fig-cover.png"))


# ---------------------------------------------------------------- map
def course_map():
    W, H = 1500, 850
    img, d = canvas(W, H)
    text(d, 80, 60, "《AFA 与进程代数》结构", size=30, color=INK, anchor="lm", kind="cnb")
    bands = [
        ("第一篇", "非良基集合论", "第 1–5 章　ZFA · 装饰 · 互模拟 · 解引理 · 余代数", (219, 234, 254), BLUE),
        ("第二篇", "进程代数", "第 6–10 章　LTS · CCS · 弱互模拟 · ACP · π-演算", (204, 251, 241), TEAL),
        ("第三篇", "统一", "第 11–12 章　进程即超集合 · 终语义 · 变体与前沿", (254, 243, 199), AMBER),
        ("附录", "工具箱", "A 公理速查 · B 习题解答 · C 术语表 · D 文献导读", (241, 245, 249), GRAY),
    ]
    y = 120
    for tag, title, sub, fill, color in bands:
        box(d, 80, y, 1340, 120, fill=fill, outline=color, width=2, radius=14)
        d.rectangle([80 * SS, y * SS, 92 * SS, (y + 120) * SS], fill=color)
        text(d, 120, y + 34, tag, size=18, color=color, anchor="lm", kind="cnb")
        text(d, 120, y + 78, title, size=26, color=INK, anchor="lm", kind="cnb")
        text(d, 430, y + 74, sub, size=18, color=(51, 65, 85), anchor="lm", kind="cn")
        y += 170
    for yy in (240, 410, 580):
        arrow(d, (750, yy), (750, yy + 50), color=GRAY, width=3)
    text(d, 750, 790, "主线：装饰 → 互模拟 → 指称", size=20, color=GRAY, kind="cn")
    save(img, os.path.join(OUT, "fig-map.png"))


# ---------------------------------------------------------------- omega
def omega():
    W, H = 1500, 470
    img, d = canvas(W, H)
    # (a) self loop
    node(d, 200, 260, 30, "x")
    loop(d, 200, 260, 30, label="")
    text(d, 200, 400, "x = {x}", size=24, color=INK, kind="math")
    # (b) 2-cycle
    p, q = (560, 220), (560, 340)
    node(d, *p, 28, "x"); node(d, *q, 28, "y")
    node_arrow(d, p, q, 28); node_arrow(d, q, p, 28, lx=610)
    text(d, 560, 415, "x = {y},  y = {x}", size=22, color=INK, kind="math")
    # (c) 3-cycle
    a, b, c = (930, 210), (1030, 330), (830, 330)
    for u, v in ((a, b), (b, c), (c, a)):
        node(d, *u, 26, ""); 
    node(d, *a, 26, "x"); node(d, *b, 26, "y"); node(d, *c, 26, "z")
    node_arrow(d, a, b, 26); node_arrow(d, b, c, 26); node_arrow(d, c, a, 26)
    text(d, 930, 415, "三点循环", size=22, color=INK, kind="cn")
    # arrow and Omega
    arrow(d, (1150, 270), (1250, 270), color=AMBER, width=4, head=16)
    text(d, 1375, 265, "Ω", size=78, color=BLUE, kind="math")
    save(img, os.path.join(OUT, "fig-omega.png"))


# ---------------------------------------------------------------- equations
def equations():
    W, H = 1200, 520
    img, d = canvas(W, H)
    # left
    node(d, 260, 270, 34, "x")
    loop(d, 260, 270, 34)
    text(d, 260, 430, "x = {x}", size=26, color=INK, kind="math")
    # divider
    d.line([600 * SS, 100 * SS, 600 * SS, 460 * SS], fill=(226, 232, 240), width=2 * SS)
    # right
    node(d, 860, 240, 32, "x")
    loop(d, 860, 240, 32)
    node(d, 1000, 360, 26, "∅")
    node_arrow(d, (860, 240), (1000, 360), 32)
    text(d, 880, 450, "x = {∅, x}", size=26, color=INK, kind="math")
    save(img, os.path.join(OUT, "fig-equations.png"))


# ---------------------------------------------------------------- bisimulation
def bisim():
    W, H = 1450, 640
    img, d = canvas(W, H)
    P = {"0": (300, 100), "1": (150, 290), "2": (450, 290), "3": (300, 470)}
    Q = {"0": (1050, 100), "1": (900, 290), "2": (1200, 290), "3": (1050, 470)}
    for s, (x, y) in P.items():
        node(d, x, y, 30, s, fill=WHITE, outline=BLUE)
    for s, (x, y) in Q.items():
        node(d, x, y, 30, s, fill=WHITE, outline=TEAL)
    node_arrow(d, P["0"], P["1"], 30, label="a", lx=195, ly=200)
    node_arrow(d, P["0"], P["2"], 30, label="b", lx=405, ly=200)
    node_arrow(d, P["1"], P["3"], 30, label="b", lx=200, ly=395)
    node_arrow(d, P["2"], P["3"], 30, label="a", lx=400, ly=395)
    node_arrow(d, Q["0"], Q["1"], 30, color=TEAL, label="a", lx=945, ly=200)
    node_arrow(d, Q["0"], Q["2"], 30, color=TEAL, label="b", lx=1155, ly=200)
    node_arrow(d, Q["1"], Q["3"], 30, color=TEAL, label="b", lx=950, ly=395)
    node_arrow(d, Q["2"], Q["3"], 30, color=TEAL, label="a", lx=1150, ly=395)
    text(d, 300, 565, "P = a.0 | b.0", size=24, color=BLUE, kind="math")
    text(d, 1050, 565, "Q = a.b.0 + b.a.0", size=24, color=TEAL, kind="math")
    text(d, 675, 610, "编号相同 = 互模拟对应", size=18, color=GRAY, kind="cn")
    save(img, os.path.join(OUT, "fig-bisim.png"))


# ---------------------------------------------------------------- vending
def bezier_arrow(d, p0, c, p1, color=TEAL, width=3, label=None, lx=None, ly=None, size=22):
    pts = []
    for i in range(61):
        t = i / 60
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * c[0] + t ** 2 * p1[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * c[1] + t ** 2 * p1[1]
        pts.append((x, y))
    for i in range(len(pts) - 1):
        d.line([pts[i][0] * SS, pts[i][1] * SS, pts[i + 1][0] * SS, pts[i + 1][1] * SS],
               fill=color, width=width * SS)
    _arrowhead(d, pts[-3], pts[-1], color, 12)
    if label:
        text(d, lx if lx is not None else (p0[0] + p1[0]) / 2,
             ly if ly is not None else (p0[1] + p1[1]) / 2,
             label, size=size, color=color, kind="math")


def vending():
    W, H = 1100, 520
    img, d = canvas(W, H)
    node(d, 260, 280, 36, "q0")
    node(d, 700, 280, 36, "q1")
    node_arrow(d, (260, 280), (700, 280), 36, label="coin", lx=480, ly=245, size=22)
    bezier_arrow(d, (668, 258), (480, 90), (292, 258), color=TEAL,
                 label="tea", lx=480, ly=105)
    bezier_arrow(d, (668, 302), (480, 470), (292, 302), color=AMBER,
                 label="coffee", lx=480, ly=455)
    save(img, os.path.join(OUT, "fig-vending.png"))


# ---------------------------------------------------------------- commuting square
def commute():
    W, H = 1050, 600
    img, d = canvas(W, H)
    b1 = (150, 100, 240, 90); b2 = (650, 100, 240, 90)
    b3 = (150, 390, 240, 90); b4 = (650, 390, 240, 90)
    for b, lab in ((b1, "X"), (b2, "F(X)"), (b3, "Y"), (b4, "F(Y)")):
        box(d, *b, fill=(239, 246, 255), outline=BLUE)
        text(d, b[0] + b[2] / 2, b[1] + b[3] / 2, lab, size=26, kind="math")
    # top arrow
    arrow(d, (395, 145), (645, 145), color=BLUE, width=3)
    text(d, 520, 120, "ξ", size=24, color=BLUE, kind="math")
    # bottom arrow
    arrow(d, (395, 435), (645, 435), color=BLUE, width=3)
    text(d, 520, 410, "θ", size=24, color=BLUE, kind="math")
    # left arrow
    arrow(d, (270, 195), (270, 385), color=BLUE, width=3)
    text(d, 235, 290, "f", size=24, color=BLUE, kind="math")
    # right arrow
    arrow(d, (770, 195), (770, 385), color=BLUE, width=3)
    text(d, 805, 290, "F(f)", size=24, color=BLUE, kind="math")
    text(d, 520, 540, "θ ∘ f = F(f) ∘ ξ", size=26, color=INK, kind="math")
    save(img, os.path.join(OUT, "fig-commute.png"))


# ---------------------------------------------------------------- span
def span():
    W, H = 1250, 640
    img, d = canvas(W, H)

    def square(x0, title_x, title_fx, bottom, proj, fproj):
        R = (x0, 80, 180, 80)
        FR = (x0 + 300, 80, 180, 80)
        X = (x0, 380, 180, 80)
        FX = (x0 + 300, 380, 180, 80)
        for b, lab in ((R, "R"), (FR, "F(R)"), (X, title_x), (FX, title_fx)):
            box(d, *b, fill=(240, 253, 250), outline=TEAL)
            text(d, b[0] + b[2] / 2, b[1] + b[3] / 2, lab, size=24, kind="math")
        arrow(d, (x0 + 185, 120), (x0 + 295, 120), color=TEAL, width=2)
        text(d, x0 + 240, 98, "ρ", size=20, color=TEAL, kind="math")
        arrow(d, (x0 + 185, 420), (x0 + 295, 420), color=TEAL, width=2)
        text(d, x0 + 240, 398, bottom, size=20, color=TEAL, kind="math")
        arrow(d, (x0 + 85, 165), (x0 + 85, 375), color=TEAL, width=2)
        text(d, x0 + 55, 270, proj, size=20, color=TEAL, kind="math")
        arrow(d, (x0 + 385, 165), (x0 + 385, 375), color=TEAL, width=2)
        text(d, x0 + 415, 270, fproj, size=19, color=TEAL, kind="math")

    square(80, "X", "F(X)", "ξ", "π₁", "F(π₁)")
    square(680, "Y", "F(Y)", "θ", "π₂", "F(π₂)")
    text(d, 625, 560, "两个投影都是同态：R 是互模拟", size=20, color=GRAY, kind="cn")
    save(img, os.path.join(OUT, "fig-span.png"))


# ---------------------------------------------------------------- triangle
def triangle():
    W, H = 1050, 620
    img, d = canvas(W, H)
    top = (370, 60, 310, 90)
    left = (110, 420, 300, 90)
    right = (640, 420, 300, 90)
    for b, lab in ((top, "语法  T_Σ"), (left, "T_Σ / ~"), (right, "行为  V_A(L)")):
        box(d, *b, fill=(239, 246, 255), outline=BLUE)
        text(d, b[0] + b[2] / 2, b[1] + b[3] / 2, lab, size=24, kind="cn")
    arrow(d, (540, 155), (760, 415), color=BLUE, width=3)
    text(d, 800, 250, "指称", size=24, color=BLUE, kind="cn")
    arrow(d, (420, 155), (300, 415), color=BLUE, width=3)
    text(d, 250, 250, "q", size=24, color=BLUE, kind="math")
    arrow(d, (415, 465), (635, 465), color=TEAL, width=3)
    text(d, 525, 440, "≅", size=26, color=TEAL, kind="math")
    text(d, 525, 545, "先商去互模拟，再取指称 = 直接取指称", size=18, color=GRAY, kind="cn")
    save(img, os.path.join(OUT, "fig-triangle.png"))


# ---------------------------------------------------------------- spectrum
def spectrum():
    W, H = 1450, 430
    img, d = canvas(W, H)
    labels = ["迹等价", "失败等价", "准备模拟", "模拟", "互模拟"]
    xs = [110, 380, 650, 920, 1190]
    for i, (x, lab) in enumerate(zip(xs, labels)):
        fill = (241, 245, 249) if i < 4 else (219, 234, 254)
        out = GRAY if i < 4 else BLUE
        box(d, x, 140, 210, 80, fill=fill, outline=out)
        text(d, x + 105, 180, lab, size=22, color=INK, kind="cn")
        if i < 4:
            arrow(d, (x + 215, 180), (xs[i + 1] - 5, 180), color=GRAY, width=2)
    arrow(d, (110, 290), (1290, 290), color=AMBER, width=3)
    text(d, 700, 330, "越靠右越细（实际构成偏序，非线性）", size=20, color=AMBER, kind="cn")
    text(d, 110, 90, "常见行为等价（粗略谱系）", size=26, color=INK, anchor="lm", kind="cnb")
    save(img, os.path.join(OUT, "fig-spectrum.png"))


# ---------------------------------------------------------------- ccs difference
def ccs():
    W, H = 1400, 620
    img, d = canvas(W, H)
    # left P = a.(b+c)
    node(d, 220, 170, 30, "p0", outline=BLUE)
    node(d, 220, 360, 30, "p1", outline=BLUE)
    node(d, 460, 300, 26, "0", outline=BLUE)
    node(d, 460, 430, 26, "0", outline=BLUE)
    node_arrow(d, (220, 170), (220, 360), 30, label="a", lx=265, ly=265)
    node_arrow(d, (220, 360), (460, 300), 30, label="b", lx=340, ly=305)
    node_arrow(d, (220, 360), (460, 430), 30, label="c", lx=340, ly=420)
    text(d, 220, 540, "P = a.(b.0 + c.0)", size=24, color=BLUE, kind="math")
    # right Q = a.b + a.c
    node(d, 900, 170, 30, "q0", outline=TEAL)
    node(d, 800, 360, 30, "q1", outline=TEAL)
    node(d, 1000, 360, 30, "q2", outline=TEAL)
    node(d, 800, 500, 26, "0", outline=TEAL)
    node(d, 1000, 500, 26, "0", outline=TEAL)
    node_arrow(d, (900, 170), (800, 360), 30, color=TEAL, label="a", lx=830, ly=260)
    node_arrow(d, (900, 170), (1000, 360), 30, color=TEAL, label="a", lx=970, ly=260)
    node_arrow(d, (800, 360), (800, 500), 30, color=TEAL, label="b", lx=750, ly=430)
    node_arrow(d, (1000, 360), (1000, 500), 30, color=TEAL, label="c", lx=1050, ly=430)
    text(d, 900, 585, "Q = a.b.0 + a.c.0", size=24, color=TEAL, kind="math")
    # separator and verdict
    text(d, 700, 70, "P 与 Q 不互模拟", size=20, color=RED, kind="cn")
    d.line([700 * SS, 110 * SS, 700 * SS, 540 * SS], fill=(254, 202, 202), width=2 * SS)
    save(img, os.path.join(OUT, "fig-ccs.png"))


if __name__ == "__main__":
    cover()
    course_map()
    omega()
    equations()
    bisim()
    vending()
    commute()
    span()
    triangle()
    spectrum()
    ccs()
