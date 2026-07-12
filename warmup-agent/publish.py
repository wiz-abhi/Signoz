import json
import os
import sys

import httpx

blog = open(os.path.join(os.path.dirname(__file__), "..", "signoz-warmup-blog.md"), encoding="utf-8").read()
lines = blog.splitlines()
title = lines[0].lstrip("# ").strip()
body = "\n".join(lines[1:]).strip()

target = sys.argv[1]

if target == "devto":
    r = httpx.post(
        "https://dev.to/api/articles",
        headers={"api-key": os.environ["DEVTO_KEY"], "Content-Type": "application/json"},
        json={"article": {
            "title": title,
            "published": True,
            "body_markdown": body,
            "tags": ["signoz", "opentelemetry", "observability", "ai"],
        }},
        timeout=60,
    )
    print(r.status_code)
    d = r.json()
    print(d.get("url") or d)

elif target == "hashnode-pubs":
    q = "query { me { publications(first: 10) { edges { node { id url } } } } }"
    r = httpx.post("https://gql.hashnode.com/", headers={"Authorization": os.environ["HASHNODE_KEY"]},
                   json={"query": q}, timeout=60)
    print(r.status_code, r.text[:800])

elif target == "hashnode-publish":
    pub_id = sys.argv[2]
    q = """
    mutation PublishPost($input: PublishPostInput!) {
      publishPost(input: $input) { post { url } }
    }"""
    variables = {"input": {
        "title": title,
        "contentMarkdown": body,
        "publicationId": pub_id,
        "tags": [
            {"slug": "signoz", "name": "SigNoz"},
            {"slug": "opentelemetry", "name": "OpenTelemetry"},
            {"slug": "observability", "name": "Observability"},
            {"slug": "ai", "name": "AI"},
        ],
    }}
    r = httpx.post("https://gql.hashnode.com/", headers={"Authorization": os.environ["HASHNODE_KEY"]},
                   json={"query": q, "variables": variables}, timeout=60)
    print(r.status_code, r.text[:800])
