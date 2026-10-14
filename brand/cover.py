# Facebook cover 1640x624 (key content kept in the centre ~1100px for mobile crop)
import math, random
from PIL import Image, ImageDraw, ImageFilter, ImageFont
W, H = 1640, 624
img = Image.new("RGB", (W, H))
d = ImageDraw.Draw(img)
for y in range(H):
    t = y / H
    d.line([(0, y), (W, y)], fill=(int(14 - 8 * t), int(10 - 6 * t), int(34 - 22 * t)))
glow = Image.new("RGB", (W, H)); g = ImageDraw.Draw(glow)
rng = random.Random(4)
cols = [(255, 59, 92), (60, 140, 255), (61, 255, 140), (255, 210, 63), (180, 92, 255), (255, 138, 43)]
rings = [(250, 330, 220, 40), (1390, 300, 260, 35)]
for cx, cy, R, gap in rings:
    for k in range(3):
        r = R - k * 55
        a0 = rng.uniform(0, 360)
        g.arc([cx - r, cy - r, cx + r, cy + r], a0 + gap / 2, a0 + 360 - gap / 2, fill=(60 + 60 * k, 120, 255 - 40 * k), width=12)
balls = []
for cx, cy, R, _ in rings:
    for _ in range(4):
        a, dd = rng.uniform(0, 6.28), rng.uniform(0, R - 150)
        balls.append((cx + dd * math.cos(a), cy + dd * math.sin(a), rng.choice(cols)))
for x, y, c in balls:
    g.ellipse([x - 34, y - 34, x + 34, y + 34], fill=c)
img = Image.blend(img, glow.filter(ImageFilter.GaussianBlur(22)), 0.8)
img.paste(glow, (0, 0), glow.convert("L").point(lambda v: 255 if v > 40 else 0))
d = ImageDraw.Draw(img)
f1 = ImageFont.truetype("../assets/fonts/Anton-Regular.ttf", 150)
f2 = ImageFont.truetype("../assets/fonts/Anton-Regular.ttf", 54)
def ctext(txt, f, y, fill):
    w = d.textlength(txt, font=f)
    d.text(((W - w) / 2, y), txt, font=f, fill=fill, stroke_width=6, stroke_fill=(0, 0, 0))
ctext("BOUNCE ARENA", f1, 160, (255, 255, 255))
ctext("PICK A COLOR.  WATCH IT FIGHT.", f2, 360, (43, 231, 255))
ctext("NEW PHYSICS BATTLES DAILY", f2, 435, (255, 210, 63))
img.save("fb_cover.png")
