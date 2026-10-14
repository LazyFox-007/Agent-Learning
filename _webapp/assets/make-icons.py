# -*- coding: utf-8 -*-
"""把吉祥物图转成 Windows 快捷方式图标 + 网页图标"""
from PIL import Image
import os

ASSETS = r"C:\StudyAI\_webapp\assets"
SRC    = os.path.join(ASSETS, "mascot-source.jpg")

im = Image.open(SRC).convert("RGB")
W, H = im.size
print("原图尺寸: %dx%d" % (W, H))

# --- 1) 裁掉右下角"豆包AI生成"水印 ---
# 水印在底部约 6% 区域，裁掉后居中裁成正方形
cut = int(H * 0.065)
im2 = im.crop((0, 0, W, H - cut))
w2, h2 = im2.size
side = min(w2, h2)
left = (w2 - side) // 2
top  = (h2 - side) // 2
im2 = im2.crop((left, top, left + side, top + side))
print("裁水印后: %dx%d -> 正方形 %dx%d" % (w2, h2, side, side))

# --- 2) 生成多尺寸 .ico ---
SIZES = [256, 128, 64, 48, 32, 24, 16]
ico = os.path.join(ASSETS, "mascot.ico")
im2.save(ico, format="ICO", sizes=[(s, s) for s in SIZES])
print("已生成 %s (%.1f KB)  尺寸: %s" % (ico, os.path.getsize(ico)/1024, SIZES))

# --- 3) 网页用 PNG ---
for size, name in [(512, "mascot-512.png"), (256, "mascot-256.png"),
                   (180, "apple-touch-icon.png"), (64, "mascot-64.png")]:
    im2.resize((size, size), Image.LANCZOS).save(os.path.join(ASSETS, name), "PNG")
    print("  %s  %dpx" % (name, size))

# --- 4) favicon.ico 放到 static 根 ---
fav = r"C:\StudyAI\_webapp\static\favicon.ico"
im2.save(fav, format="ICO", sizes=[(s, s) for s in [64, 48, 32, 16]])
print("已生成 %s (%.1f KB)" % (fav, os.path.getsize(fav)/1024))

# --- 5) 各尺寸预览图（用于目视检查清晰度）---
sheet = Image.new("RGB", (16 + 64 + 48 + 32 + 16 + 4*12, 80), (255, 255, 255))
x = 8
for s in [64, 48, 32, 16]:
    sheet.paste(im2.resize((s, s), Image.LANCZOS), (x, (80-s)//2))
    x += s + 12
sheet.save(os.path.join(ASSETS, "_preview-sizes.png"), "PNG")
print("已生成 _preview-sizes.png（图标清晰度预览）")
