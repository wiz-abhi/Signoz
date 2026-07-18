from playwright.sync_api import sync_playwright
import pathlib

base = pathlib.Path(r"C:/Users/abhis/Desktop/OSS/Signoz/warmup-blog-2/images")
targets = ["6-trace-timeline", "7-zero-flowchart"]

with sync_playwright() as p:
    browser = p.chromium.launch()
    for name in targets:
        page = browser.new_page(viewport={"width": 1400, "height": 900}, device_scale_factor=2)
        page.goto((base / f"{name}.html").as_uri())
        page.wait_for_timeout(300)
        el = page.query_selector(".canvas")
        el.screenshot(path=str(base / f"{name}.png"))
        print("rendered", name)
        page.close()
    browser.close()
