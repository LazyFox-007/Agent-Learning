# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from PIL import Image, ImageDraw, ImageFont

samples = [
    ("msyh", r"C:\Windows\Fonts\msyh.ttc"),
    ("cambria", r"C:\Windows\Fonts\cambria.ttc"),
    ("simhei", r"C:\Windows\Fonts\simhei.ttf"),
]
text = "Ω τ λ ∈ ∉ ⊆ → ⟹ ⟺ { } ⟨ ⟩ ℘ ∅ ≠ ≤ ∞ ↾ ⟦ ⟧ ∘ × ⋃ ⋂ ∼ ≈ ≡ ⊑ ⊢"
img = Image.new("RGB", (1500, 260), "white")
d = ImageDraw.Draw(img)
y = 20
for name, path in samples:
    f = ImageFont.truetype(path, 30)
    d.text((20, y), name + ": " + text, font=f, fill=(10, 10, 10))
    y += 75
img.save(r"D:\AI\AFARules\figures\glyphtest.png")
print("ok")
