"""The three MCP calls an AI assistant would make to debug the slow agent."""
import json

from mcp_demo import rpc, HDRS  # reuse the raw JSON-RPC helpers
import httpx

URL = "http://localhost:8000/mcp"

with httpx.Client() as c:
    r, out = rpc(c, "initialize", {
        "protocolVersion": "2025-03-26", "capabilities": {},
        "clientInfo": {"name": "claude-code", "version": "1.0"},
    }, id_=1)
    session = r.headers.get("Mcp-Session-Id")
    rpc(c, "notifications/initialized", {}, session=session)

    def call(tool, args, id_):
        _, res = rpc(c, "tools/call", {"name": tool, "arguments": args}, id_=id_, session=session)
        if "error" in (res or {}):
            return f"ERROR: {res['error']}"
        texts = [i.get("text", "") for i in res["result"]["content"]]
        return "\n".join(texts)

    print("=== 1. which services exist? ===")
    print(call("signoz_list_services", {"timeRange": "48h"}, 2)[:400])

    print("\n=== 2. slowest traces for warmup-agent ===")
    print(call("signoz_search_traces", {
        "timeRange": "48h",
        "filter": "service.name = 'warmup-agent' AND name = 'agent answer' AND duration_nano > 15000000000",
        "limit": 3,
    }, 3)[:1500])

    print("\n=== 3. WARN logs from the agent ===")
    print(call("signoz_search_logs", {
        "timeRange": "48h",
        "filter": "severity_text = 'WARN'",
        "limit": 5,
    }, 4)[:1500])
