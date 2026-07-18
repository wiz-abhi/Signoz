"""Simulate Dev.to's CDN: downscale to width=800 and re-encode as lossy WebP."""
import os
import sys

from PIL import Image

SRC = os.path.join(os.path.dirname(__file__), "screenshots")
OUT = os.path.join(os.path.dirname(__file__), "devto_preview")
os.makedirs(OUT, exist_ok=True)

for name in sorted(os.listdir(SRC)):
    if not name.endswith(".png"):
        continue
    im = Image.open(os.path.join(SRC, name))
    w, h = im.size
    if w > 800:
        im = im.resize((800, round(h * 800 / w)), Image.LANCZOS)
    tmp = os.path.join(OUT, name.replace(".png", ".webp"))
    im.convert("RGB").save(tmp, "WEBP", quality=80)
    back = Image.open(tmp).convert("RGB")
    png = os.path.join(OUT, name)
    back.save(png)
    print(f"{name:38s} {w}x{h} -> {im.size[0]}x{im.size[1]}  webp={os.path.getsize(tmp)//1024}KB")
