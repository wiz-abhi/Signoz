"""Retake screenshot 1: services page, window covering only the Gemini runs."""
import os
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8080"
EMAIL = os.environ.get("SIGNOZ_EMAIL", "admin@example.com")
PASSWORD = os.environ.get("SIGNOZ_PASSWORD", "")
OUT = os.path.join(os.path.dirname(__file__), "screenshots")

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1600, "height": 900})
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.fill('input[type="email"]', EMAIL)
    page.click('button:has-text("Next")')
    page.wait_for_selector('input[type="password"]', timeout=15000)
    page.fill('input[type="password"]', PASSWORD)
    page.click('button:has-text("Sign in with Password")')
    page.wait_for_url("**/home**", timeout=30000)
    page.goto(f"{BASE}/services?relativeTime=15m", wait_until="networkidle")
    page.wait_for_selector("text=warmup-agent", timeout=30000)
    page.wait_for_timeout(2000)
    page.screenshot(path=os.path.join(OUT, "1-services.png"))
    print("saved shot 1")
    browser.close()
