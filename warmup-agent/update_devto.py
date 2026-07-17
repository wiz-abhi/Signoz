"""Update the published Dev.to article with the latest blog markdown."""
import os

import httpx

KEY = os.environ["DEVTO_KEY"]
ARTICLE_ID = 4127403  # the warm-up post; pinned so a future SigNoz article can't be clobbered

blog = open(os.path.join(os.path.dirname(__file__), "..", "signoz-warmup-blog.md"), encoding="utf-8").read()
lines = blog.splitlines()
title = lines[0].lstrip("# ").strip()
body = "\n".join(lines[1:]).strip()

art = httpx.get(f"https://dev.to/api/articles/{ARTICLE_ID}", timeout=60).json()
print("updating:", art["id"], art["url"])

r = httpx.put(
    f"https://dev.to/api/articles/{ARTICLE_ID}",
    headers={"api-key": KEY, "Content-Type": "application/json"},
    json={"article": {"title": title, "body_markdown": body}},
    timeout=60,
)
print(r.status_code, r.json().get("url", r.text[:300]))
