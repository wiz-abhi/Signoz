import os
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "screenshots")
os.makedirs(OUT, exist_ok=True)

pairs = [
    ("meme_fire.html", "6-meme-fire-logs.png"),
    ("meme_expectation.html", "7-meme-expectation-reality.png"),
]

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1200, "height": 628}, device_scale_factor=2)
    for src, dst in pairs:
        pg.goto("file:///" + os.path.join(HERE, src).replace("\\", "/"))
        pg.wait_for_timeout(300)
        pg.screenshot(path=os.path.join(OUT, dst))
        print("saved", dst)
    b.close()
