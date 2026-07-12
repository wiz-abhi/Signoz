"""Talk to the SigNoz MCP server over streamable HTTP (raw JSON-RPC)."""
import json
import sys

import httpx

URL = "http://localhost:8000/mcp"
HDRS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


def parse(resp):
    ct = resp.headers.get("content-type", "")
    if "event-stream" in ct:
        for line in resp.text.splitlines():
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
        return None
    return resp.json() if resp.text else None


def rpc(client, method, params=None, id_=None, session=None):
    h = dict(HDRS)
    if session:
        h["Mcp-Session-Id"] = session
    body = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        body["params"] = params
    if id_ is not None:
        body["id"] = id_
    r = client.post(URL, headers=h, json=body, timeout=120)
    return r, parse(r)


with httpx.Client() as c:
    r, out = rpc(c, "initialize", {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "claude-code-demo", "version": "1.0"},
    }, id_=1)
    session = r.headers.get("Mcp-Session-Id")
    print("server:", json.dumps(out["result"]["serverInfo"]))
    rpc(c, "notifications/initialized", {}, session=session)

    _, tools = rpc(c, "tools/list", {}, id_=2, session=session)
    names = [t["name"] for t in tools["result"]["tools"]]
    print(f"tools ({len(names)}):", ", ".join(names))

    if len(sys.argv) > 2:
        tool = sys.argv[1]
        args = json.loads(sys.argv[2])
        _, res = rpc(c, "tools/call", {"name": tool, "arguments": args}, id_=3, session=session)
        for item in res["result"]["content"]:
            print(item.get("text", "")[:3000])
