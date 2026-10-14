# Generates Bounce Arena profile logo (1080x1080)
import math
from PIL import Image, ImageDraw, ImageFilter
S = 1080
img = Image.new("RGB", (S, S), (10, 10, 22))
glow = Image.new("RGB", (S, S), (0, 0, 0))
g = ImageDraw.Draw(glow)
c, r = S // 2, 380
g.ellipse([c - r, c - r, c + r, c + r], outline=(0, 230, 255), width=40)
balls = [((255, 60, 90), 200, -60), ((60, 140, 255), 150, 120), ((60, 255, 140), 110, 230), ((255, 210, 40), 220, 20)]
pos = []
for col, dist, ang in balls:
    x = c + dist * math.cos(math.radians(ang)); y = c + dist * math.sin(math.radians(ang))
    pos.append((col, x, y))
    g.ellipse([x - 95, y - 95, x + 95, y + 95], fill=col)
glow = glow.filter(ImageFilter.GaussianBlur(28))
img = Image.blend(img, glow, 0.9)
d = ImageDraw.Draw(img)
d.ellipse([c - r, c - r, c + r, c + r], outline=(180, 250, 255), width=18)
for col, x, y in pos:
    d.ellipse([x - 80, y - 80, x + 80, y + 80], fill=col)
    d.ellipse([x - 45, y - 55, x - 10, y - 20], fill=tuple(min(255, v + 120) for v in col))
img.save(__file__.replace("logo.py", "logo.png"))
