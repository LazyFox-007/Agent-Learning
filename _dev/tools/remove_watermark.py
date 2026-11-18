"""去掉图片右下角的「豆包AI生成」水印（v3）。

三轮尝试
  v1 按行水平插值  → 留下矩形接缝
  v2 cv2.inpaint   → 涂抹痕，且把卡片白色圆角边啃掉一块

v3 的做法（背景重建法）
  1. 用大核中值滤波估出「如果没有文字，这里该是什么样」
     —— 文字笔画很细，会被中值滤掉；而卡片的白色圆角边是粗结构，会被保留
  2. 只在「原图与背景估计差异明显」的像素上替换，其余一律不动
     —— 所以白边、蓝渐变都不受影响
  3. 用模糊后的 mask 做羽化混合，避免出现硬边
"""
import cv2
import numpy as np

SRC = r'C:\StudyAI\_webapp\shots\wm-in.jpg'
OUT = r'C:\StudyAI\_webapp\shots\wm-out.png'

img = cv2.imread(SRC, cv2.IMREAD_COLOR)
h, w = img.shape[:2]

# ---- 1. 背景估计 ----
# 核要足够大，把文字完全吃掉；51 在 1280 图上约等于 4% 宽度
bg = cv2.medianBlur(img, 51)

# 边缘被中值滤波平滑了一点点，再对 bg 做一次轻度高斯让它更连续
bg = cv2.GaussianBlur(bg, (9, 9), 0)

# ---- 2. 只在右下角算差异 ----
X0, Y0 = 990, 1170
roi_img = img[Y0:h, X0:w].astype(np.int16)
roi_bg = bg[Y0:h, X0:w].astype(np.int16)

diff = np.abs(roi_img - roi_bg).max(axis=2).astype(np.float32)

# 文字比背景亮或暗都会有差值；阈值取 9 能盖住抗锯齿边缘又不动平滑渐变
mask = (diff > 9).astype(np.float32)

# 去掉零星噪点
mask_u8 = (mask * 255).astype(np.uint8)
mask_u8 = cv2.morphologyEx(mask_u8, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
mask_u8 = cv2.dilate(mask_u8, np.ones((3, 3), np.uint8), iterations=1)

print('需要替换的像素:', int((mask_u8 > 0).sum()))

# ---- 3. 羽化混合 ----
alpha = cv2.GaussianBlur(mask_u8.astype(np.float32) / 255.0, (5, 5), 0)[..., None]

full_alpha = np.zeros((h, w, 1), np.float32)
full_alpha[Y0:h, X0:w] = alpha

out = img.astype(np.float32) * (1 - full_alpha) + bg.astype(np.float32) * full_alpha
out = np.clip(out, 0, 255).astype(np.uint8)

cv2.imwrite(OUT, out)
print('已输出:', OUT)

# ---- 4. 放大检查 ----
z = out[1120:1280, 940:1280]
z = cv2.resize(z, (680, 320), interpolation=cv2.INTER_LANCZOS4)
cv2.imwrite(r'C:\StudyAI\_webapp\shots\wm-fixed-zoom.png', z)

# 顺便出一张「整图缩略」方便看整体有没有被破坏
thumb = cv2.resize(out, (640, 640), interpolation=cv2.INTER_AREA)
cv2.imwrite(r'C:\StudyAI\_webapp\shots\wm-fixed-thumb.png', thumb)
print('放大图 + 缩略图已存')
