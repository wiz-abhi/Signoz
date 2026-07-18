# ClickHouse Evidence — SigNoz warmup-agent traces

Source: self-hosted SigNoz v0.132.2, ClickHouse container `signoz-telemetrystore-clickhouse-0-0`.
Table: `signoz_traces.distributed_signoz_index_v3`.
Collected: 2026-07-18. All numbers below are verbatim query output — nothing rounded or invented.

## SUMMARY (key finding)

The single logical step "the LLM call" is fragmented across **3 distinct span
names** in this dataset: `chat gpt-4o-mini`, `chat gemini-3.1-flash-lite`, and
`chat gpt-oss-120b`. These follow the OpenTelemetry GenAI semconv pattern
`{operation} {model}`, so every time the agent switches model the span name
changes — one logical operation, N names. All three come from a single service,
**warmup-agent**. In total the chat spans span **44 spans across 22 traces**
(20/10, 16/8, 8/4). The full instance holds **92 spans across 26 traces** from
**2 services** (warmup-agent: 88 spans / 22 traces; replay-probe: 4 spans / 4
traces). The chat-span data was recorded on 2026-07-12, between 17:39:36 and
18:07:11 UTC. Takeaway for the blog: model-name-in-span-name means you cannot
group "the LLM call" by span name — it splinters per model.

---

## Schema note

The service name lives in a column named `resource_string_service$$name`
(a materialized default over `resources_string['service.name']`), with the
convenience ALIAS `serviceName`. The `$$` must be escaped in a bash-quoted
`-q` string as `\$\$`. Span name is the `name` column (LowCardinality(String)).
Trace id is `trace_id` (FixedString(32)). Timestamp is `timestamp`
(DateTime64(9)). Confirmed via `DESCRIBE TABLE`.

---

## Q1 — Span-name distribution for LLM chat spans (the money query)

```
docker exec signoz-telemetrystore-clickhouse-0-0 clickhouse-client -q "SELECT name, count() AS spans, count(DISTINCT trace_id) AS traces FROM signoz_traces.distributed_signoz_index_v3 WHERE name LIKE 'chat %' GROUP BY name ORDER BY spans DESC FORMAT PrettyCompactMonoBlock"
```

```
   ┌─name───────────────────────┬─spans─┬─traces─┐
1. │ chat gpt-4o-mini           │    20 │     10 │
2. │ chat gemini-3.1-flash-lite │    16 │      8 │
3. │ chat gpt-oss-120b          │     8 │      4 │
   └────────────────────────────┴───────┴────────┘
```

One logical step ("the LLM call") fragmented across 3 span names.

---

## Q2 — Same, scoped per service

Uses the `resource_string_service$$name` column (`$$` escaped as `\$\$`).

```
docker exec signoz-telemetrystore-clickhouse-0-0 clickhouse-client -q "SELECT \`resource_string_service\$\$name\` AS service, name, count() AS spans, count(DISTINCT trace_id) AS traces FROM signoz_traces.distributed_signoz_index_v3 WHERE name LIKE 'chat %' GROUP BY service, name ORDER BY service, spans DESC FORMAT PrettyCompactMonoBlock"
```

```
   ┌─service──────┬─name───────────────────────┬─spans─┬─traces─┐
1. │ warmup-agent │ chat gpt-4o-mini           │    20 │     10 │
2. │ warmup-agent │ chat gemini-3.1-flash-lite │    16 │      8 │
3. │ warmup-agent │ chat gpt-oss-120b          │     8 │      4 │
   └──────────────┴────────────────────────────┴───────┴────────┘
```

All chat spans belong to the single service `warmup-agent`.

---

## Q3a — Total span and trace count (whole instance)

```
docker exec signoz-telemetrystore-clickhouse-0-0 clickhouse-client -q "SELECT count() AS total_spans, count(DISTINCT trace_id) AS total_traces FROM signoz_traces.distributed_signoz_index_v3 FORMAT PrettyCompactMonoBlock"
```

```
   ┌─total_spans─┬─total_traces─┐
1. │          92 │           26 │
   └─────────────┴──────────────┘
```

---

## Q3b — Totals for the multi-model service specifically (and full span breakdown)

Per-service totals (also serves as Q4, distinct services):

```
docker exec signoz-telemetrystore-clickhouse-0-0 clickhouse-client -q "SELECT \`resource_string_service\$\$name\` AS service, count() AS spans, count(DISTINCT trace_id) AS traces FROM signoz_traces.distributed_signoz_index_v3 GROUP BY service ORDER BY spans DESC FORMAT PrettyCompactMonoBlock"
```

```
   ┌─service──────┬─spans─┬─traces─┐
1. │ warmup-agent │    88 │     22 │
2. │ replay-probe │     4 │      4 │
   └──────────────┴───────┴────────┘
```

Full span-name breakdown for the multi-model service `warmup-agent`:

```
docker exec signoz-telemetrystore-clickhouse-0-0 clickhouse-client -q "SELECT name, count() AS spans, count(DISTINCT trace_id) AS traces FROM signoz_traces.distributed_signoz_index_v3 WHERE \`resource_string_service\$\$name\` = 'warmup-agent' GROUP BY name ORDER BY spans DESC FORMAT PrettyCompactMonoBlock"
```

```
   ┌─name───────────────────────┬─spans─┬─traces─┐
1. │ agent answer               │    22 │     22 │
2. │ tool search_tool           │    22 │     22 │
3. │ chat gpt-4o-mini           │    20 │     10 │
4. │ chat gemini-3.1-flash-lite │    16 │      8 │
5. │ chat gpt-oss-120b          │     8 │      4 │
   └────────────────────────────┴───────┴────────┘
```

---

## Q4 — Distinct services present

(Same query as Q3b per-service totals above; services are `warmup-agent` and
`replay-probe`.) Minimal form:

```
docker exec signoz-telemetrystore-clickhouse-0-0 clickhouse-client -q "SELECT DISTINCT \`resource_string_service\$\$name\` AS service FROM signoz_traces.distributed_signoz_index_v3 ORDER BY service FORMAT PrettyCompactMonoBlock"
```

Services: `replay-probe`, `warmup-agent`.

---

## Q5 — Min/max timestamp of the chat spans

```
docker exec signoz-telemetrystore-clickhouse-0-0 clickhouse-client -q "SELECT min(timestamp) AS earliest, max(timestamp) AS latest FROM signoz_traces.distributed_signoz_index_v3 WHERE name LIKE 'chat %' FORMAT PrettyCompactMonoBlock"
```

```
   ┌──────────────────────earliest─┬────────────────────────latest─┐
1. │ 2026-07-12 17:39:36.660447700 │ 2026-07-12 18:07:11.650970700 │
   └───────────────────────────────┴───────────────────────────────┘
```

The chat-span data is from 2026-07-12, 17:39:36 to 18:07:11 (a ~27.5 min window).
