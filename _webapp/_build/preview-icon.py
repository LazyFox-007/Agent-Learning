# -*- coding: utf-8 -*-
"""预览候选图标在 16/24/32/48/64/128 各尺寸下的可辨识度"""
from PIL import Image, ImageDraw
import os, sys

OUT = r"C:\StudyAI\_webapp\_shots"
SRC = sys.argv[1] if len(sys.argv) > 1 else r"C:\pictureAI\comfyui\output\fish_flat_v2_00001_.png"
NAME = os.path.splitext(os.path.basename(SRC))[0]

im = Image.open(SRC).convert("RGBA")

# 白底转透明，并按内容裁掉空白
px = im.load()
w, h = im.size
for y in range(h):
    for x in range(w):
        r, g, b, a = px[x, y]
        if r > 244 and g > 244 and b > 244:
            px[x, y] = (255, 255, 255, 0)
bbox = im.getbbox()
if bbox:
    im = im.crop(bbox)
print("裁切后尺寸: %dx%d" % im.size)

SIZES = [128, 64, 48, 32, 24, 16]
PAD = 16
area_w = PAD + sum(s + PAD for s in SIZES)
area_h = 160

sheet = Image.new("RGB", (area_w, area_h), (247, 248, 250))

# 第一行：浅色背景（模拟侧栏）
d = ImageDraw.Draw(sheet)
x = PAD
for s in SIZES:
    icon = im.resize((s, s), Image.LANCZOS)
    y = (area_h - s) // 2
    # 棋盘格底，方便看透明边缘
    for cy in range(y, y + s, 8):
        for cx in range(x, x + s, 8):
            if ((cx - x) // 8 + (cy - y) // 8) % 2 == 0:
                d.rectangle([cx, cy, min(cx + 7, x + s - 1), min(cy + 7, y + s - 1)],
                            fill=(232, 234, 237))
    sheet.paste(icon, (x, y), icon)
    d.text((x, area_h - 14), "%d" % s, fill=(120, 128, 140))
    x += s + PAD

dst = os.path.join(OUT, "icon_preview_%s.png" % NAME)
sheet.save(dst, "PNG")
print("预览已保存: %s  (%dx%d)" % (dst, area_w, area_h))
