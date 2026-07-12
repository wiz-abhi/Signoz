import json
import os
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    api_calls = []
    pg.on("request", lambda r: api_calls.append((r.method, r.url)) if "/api/" in r.url else None)
    pg.goto("http://localhost:8080/login", wait_until="networkidle")
    pg.fill('input[type="email"]', os.environ.get("SIGNOZ_EMAIL", "admin@example.com"))
    pg.click('button:has-text("Next")')
    pg.wait_for_selector('input[type="password"]')
    pg.fill('input[type="password"]', os.environ.get("SIGNOZ_PASSWORD", ""))
    pg.click('button:has-text("Sign in with Password")')
    pg.wait_for_url("**/home**", timeout=30000)
    ls = json.loads(pg.evaluate("() => JSON.stringify(Object.fromEntries(Object.entries(localStorage)))"))
    with open("token_dump.json", "w") as f:
        json.dump(ls, f, indent=1)
    for k, v in ls.items():
        print(k, "=", str(v)[:60])
    print("AUTH-ish calls:")
    for m, u in api_calls:
        if any(s in u for s in ("login", "session", "auth", "token")):
            print(" ", m, u)
    b.close()
