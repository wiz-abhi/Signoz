from playwright.sync_api import sync_playwright
import pathlib

base = pathlib.Path(r"C:/Users/abhis/Desktop/OSS/Signoz/warmup-blog-2/images")

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1000, "height": 420}, device_scale_factor=2)
    page.goto((base / "0-cover.html").as_uri())
    page.wait_for_timeout(300)
    page.screenshot(path=str(base / "0-cover.png"))
    print("rendered 0-cover")
    browser.close()
