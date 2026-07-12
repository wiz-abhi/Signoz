import json
import uuid

import httpx

TOKEN = json.load(open("token_dump.json"))["AUTH_TOKEN"]
BASE = "http://localhost:8080"
H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


def trace_query(expression, filter_expr, legend, aggregation_expr):
    return {
        "dataSource": "traces",
        "queryName": expression,
        "aggregations": [{"expression": aggregation_expr}],
        "filter": {"expression": filter_expr},
        "filters": {"items": [], "op": "AND"},
        "expression": expression,
        "disabled": False,
        "stepInterval": 60,
        "having": [],
        "limit": None,
        "orderBy": [],
        "groupBy": [],
        "legend": legend,
        "reduceTo": "avg",
        "functions": [],
    }


def log_query(expression, filter_expr, legend, aggregation_expr):
    q = trace_query(expression, filter_expr, legend, aggregation_expr)
    q["dataSource"] = "logs"
    return q


def widget(title, description, query_data, y, x, unit=""):
    wid = str(uuid.uuid4())
    return wid, {
        "id": wid,
        "title": title,
        "description": description,
        "panelTypes": "graph",
        "isStacked": False,
        "nullZeroValues": "zero",
        "opacity": "1",
        "fillSpans": False,
        "yAxisUnit": unit,
        "softMax": None,
        "softMin": None,
        "selectedLogFields": [],
        "selectedTracesFields": [],
        "query": {
            "queryType": "builder",
            "builder": {"queryData": query_data, "queryFormulas": []},
            "promql": [{"name": "A", "query": "", "legend": "", "disabled": False}],
            "clickhouse_sql": [{"name": "A", "legend": "", "disabled": False, "query": ""}],
            "id": str(uuid.uuid4()),
        },
        "timePreferance": "GLOBAL_TIME",
    }


widgets, layout = [], []
panels = [
    ("Agent runs", "Count of agent answer invocations", "",
     [trace_query("A", "name = 'agent answer'", "runs", "count()")]),
    ("p95 agent latency", "p95 end-to-end latency of one agent run", "ns",
     [trace_query("A", "name = 'agent answer'", "p95 latency", "p95(duration_nano)")]),
    ("LLM output tokens", "Output tokens across chat spans (GenAI semconv)", "",
     [trace_query("A", "gen_ai.usage.output_tokens EXISTS", "output tokens", "sum(gen_ai.usage.output_tokens)")]),
    ("Tool retry warnings", "WARN logs from the agent (search_tool retries)", "",
     [log_query("A", "severity_text = 'WARN'", "warnings", "count()")]),
]
for i, (title, desc, unit, qd) in enumerate(panels):
    wid, w = widget(title, desc, qd, y=(i // 2) * 9, x=(i % 2) * 6, unit=unit)
    widgets.append(w)
    layout.append({"i": wid, "x": (i % 2) * 6, "y": (i // 2) * 9, "w": 6, "h": 9, "moved": False, "static": False})

body = {
    "title": "Agent Health - warmup-agent",
    "description": "RED metrics + GenAI token usage for the warmup agent",
    "tags": ["agents", "genai", "warmup"],
    "layout": layout,
    "widgets": widgets,
    "variables": {},
}

old = "019f5790-9827-7079-8926-7c09381a4f0a"
print("delete old:", httpx.delete(f"{BASE}/api/v1/dashboards/{old}", headers=H, timeout=30).status_code)
r = httpx.post(f"{BASE}/api/v1/dashboards", headers=H, json=body, timeout=30)
print(r.status_code)
print("new id:", r.json()["data"]["id"])
