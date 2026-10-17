# -*- coding: utf-8 -*-
"""
把生成的「大肥鱼读书」图做成整套图标资产。

两个来源，各司其职：
  v2 (透明)     -> 界面内图标：顶栏、头像、目录树、陪读面板
  v4 (圆角底色) -> 应用图标：favicon、Windows 快捷方式、apple-touch

白色背景转透明用「从边缘洪水填充」，不是全局去白 ——
鱼的肚皮、眼镜镜片高光必须保留。
"""
from PIL import Image, ImageDraw
from collections import deque
import os, sys

OUT_DIR = r"C:\pictureAI\comfyui\output"
SRC_UI  = sys.argv[1] if len(sys.argv) > 1 else os.path.join(OUT_DIR, "fish_flat_v2_00001_.png")
SRC_APP = sys.argv[2] if len(sys.argv) > 2 else os.path.join(OUT_DIR, "fish_app_v4_00001_.png")

ASSETS = r"C:\StudyAI\_webapp\assets"
STATIC = r"C:\StudyAI\_webapp\static"
THRESH = 236


def remove_bg_flood(im, thresh=THRESH):
    """从四条边洪水填充去背景，保护内部白色"""
    im = im.convert("RGBA")
    w, h = im.size
    px = im.load()
    seen = bytearray(w * h)
    q = deque()

    def is_bg(x, y):
        r, g, b, a = px[x, y]
        return a > 0 and r >= thresh and g >= thresh and b >= thresh

    for x in range(w):
        for y in (0, h - 1):
            if is_bg(x, y) and not seen[y * w + x]:
                seen[y * w + x] = 1; q.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if is_bg(x, y) and not seen[y * w + x]:
                seen[y * w + x] = 1; q.append((x, y))

    while q:
        x, y = q.popleft()
        px[x, y] = (255, 255, 255, 0)
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and not seen[ny * w + nx] and is_bg(nx, ny):
                seen[ny * w + nx] = 1; q.append((nx, ny))

    bbox = im.getbbox()
    return im.crop(bbox) if bbox else im


def square(im, pad_ratio=0.06):
    w, h = im.size
    side = int(max(w, h) * (1 + pad_ratio * 2))
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(im, ((side - w) // 2, (side - h) // 2), im)
    return canvas


# ================= 1) 界面用：透明 PNG =================
print("界面图标源: %s" % SRC_UI)
ui = square(remove_bg_flood(Image.open(SRC_UI)))
print("  处理为 %dx%d" % ui.size)

ui.resize((512, 512), Image.LANCZOS).save(os.path.join(ASSETS, "mascot-fish.png"), "PNG")
for size, name in [(512, "mascot-512.png"), (256, "mascot-256.png"),
                   (64, "mascot-64.png"), (32, "fish-32.png"), (22, "fish-22.png")]:
    ui.resize((size, size), Image.LANCZOS).save(os.path.join(STATIC, name), "PNG")
    print("  static/%s  %dpx" % (name, size))

# ================= 2) 应用图标：带圆角底色 =================
print("\n应用图标源: %s" % SRC_APP)
app = Image.open(SRC_APP)
# v4 的圆角方块外面是白的，抠掉 -> 得到透明圆角图标
app = remove_bg_flood(app, thresh=248)
print("  去白角后 %dx%d" % app.size)
side = max(app.size)
canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
canvas.paste(app, ((side - app.width) // 2, (side - app.height) // 2), app)
app = canvas

for size, name, folder in [
    (256, "app-icon-256.png", ASSETS),
    (180, "apple-touch-icon.png", STATIC),
]:
    app.resize((size, size), Image.LANCZOS).save(os.path.join(folder, name), "PNG")
    print("  %s  %dpx" % (name, size))

ico = os.path.join(ASSETS, "mascot.ico")
app.save(ico, format="ICO", sizes=[(s, s) for s in [256, 128, 64, 48, 32, 24, 16]])
print("  mascot.ico  %.1f KB" % (os.path.getsize(ico) / 1024))

fav = os.path.join(STATIC, "favicon.ico")
app.save(fav, format="ICO", sizes=[(s, s) for s in [64, 48, 32, 16]])
print("  favicon.ico  %.1f KB" % (os.path.getsize(fav) / 1024))

# ================= 3) 预览表 =================
SIZES = [96, 48, 32, 22, 16]
PAD, H = 14, 200
total = PAD + sum(s + PAD for s in SIZES)
sheet = Image.new("RGB", (total, H * 2), (255, 255, 255))
d = ImageDraw.Draw(sheet)

for row, (img, bg) in enumerate([(ui, (255, 255, 255)), (app, (27, 31, 38))]):
    y0 = row * H
    d.rectangle([0, y0, total, y0 + H], fill=bg)
    x = PAD
    for s in SIZES:
        icon = img.resize((s, s), Image.LANCZOS)
        sheet.paste(icon, (x, y0 + (H - s) // 2), icon)
        d.text((x, y0 + H - 14), "%d" % s, fill=(150, 156, 166) if row else (140, 148, 158))
        x += s + PAD

prev = os.path.join(ASSETS, "_icon-preview.png")
sheet.save(prev, "PNG")
print("  _icon-preview.png  (上排=界面图标/白底, 下排=应用图标/深底)")

print("\n完成。")
