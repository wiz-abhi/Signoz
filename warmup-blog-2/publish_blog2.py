"""Publish warm-up blog #2 to Dev.to as a new article.

Usage:
    $env:DEVTO_KEY = "<your dev.to api key>"
    python warmup-blog-2/publish_blog2.py            # dry run: show what will be sent
    python warmup-blog-2/publish_blog2.py --publish  # actually create the article

After it prints the article URL, use Medium's "Import a story" tool
(https://medium.com/p/import) with that URL to mirror it there; Medium
re-hosts the images and sets the canonical link back to Dev.to.
"""
import os
import sys

import httpx

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "signoz-funnels-blog.md")
TAGS = ["signoz", "opentelemetry", "observability", "debugging"]

blog = open(SRC, encoding="utf-8").read()
lines = blog.splitlines()
title = lines[0].lstrip("# ").strip()
body = "\n".join(lines[1:]).strip()

print(f"title ({len(title)} chars): {title}")
print(f"tags: {', '.join(TAGS)}")
print(f"body: {len(body.split())} words, {body.count('![')} images, {body.count('```') // 2} code blocks")

if "--publish" not in sys.argv:
    print("\nDry run. Re-run with --publish to create the article on Dev.to.")
    sys.exit(0)

key = os.environ.get("DEVTO_KEY")
if not key:
    sys.exit("DEVTO_KEY is not set in this shell. Set it, then re-run.")

r = httpx.post(
    "https://dev.to/api/articles",
    headers={"api-key": key, "Content-Type": "application/json"},
    json={"article": {
        "title": title,
        "published": True,
        "body_markdown": body,
        "tags": TAGS,
    }},
    timeout=60,
)
print(r.status_code)
data = r.json()
url = data.get("url")
if url:
    print("published:", url)
    print("article id:", data.get("id"))
    print("\nNext: https://medium.com/p/import  ->  paste that URL.")
else:
    print(data)
