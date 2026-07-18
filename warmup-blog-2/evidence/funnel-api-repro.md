# Trace Funnels API — verified repro (SigNoz v0.132.2, local Docker @ http://localhost:8080)

Captured 2026-07-18. Data under test: service `warmup-agent`, 22 traces, timestamps 2026-07-12 ~17:39–18:07 UTC.

**Funnel created for this evidence:**
- name: `agent-pipeline`
- **UUID: `019f75d5-f9ce-7685-8db1-097baa394562`**
- left in the WORKING state (step 3 = `chat gpt-4o-mini`) so it can be demoed live.

---

## Endpoint discovery

The funnel REST surface is under the prefix **`/api/v1/trace-funnels`** (found by grepping the
frontend bundle `assets/TracesFunnels-*.js`, base var ``Y=`/trace-funnels` ``). The UI route is
`/traces/funnels/<uuid>`. Full endpoint map (all POST take editor/admin Bearer):

| Purpose | Method | Path |
|---|---|---|
| List funnels | GET | `/api/v1/trace-funnels/list` |
| Get one funnel | GET | `/api/v1/trace-funnels/{funnel_id}` |
| Create funnel | POST | `/api/v1/trace-funnels/new` |
| Update whole funnel | PUT | `/api/v1/trace-funnels/{funnel_id}` |
| Update steps | PUT | `/api/v1/trace-funnels/steps/update` |
| Validate steps | POST | `/api/v1/trace-funnels/analytics/validate` |
| **Per-step counts** | POST | `/api/v1/trace-funnels/analytics/steps` |
| **Overview (conversion_rate)** | POST | `/api/v1/trace-funnels/analytics/overview` |
| **Step-range overview** | POST | `/api/v1/trace-funnels/analytics/steps/overview` |
| Slow traces | POST | `/api/v1/trace-funnels/analytics/slow-traces` |
| Error traces | POST | `/api/v1/trace-funnels/analytics/error-traces` |
| Delete funnel | DELETE | `/api/v1/trace-funnels/{funnel_id}` |

### Auth note (important)
The `token_dump.json` **access token was expired** (30-min TTL, `exp` 2026-07-16). Refresh with the
still-valid refresh token via:

```bash
# NOTE: the refresh token must be sent BOTH as the Bearer header AND in the body
curl -sS -X POST 'http://localhost:8080/api/v2/sessions/rotate' \
  -H 'Authorization: Bearer <REFRESH_AUTH_TOKEN>' \
  -H 'Content-Type: application/json' \
  -d '{"refreshToken":"<REFRESH_AUTH_TOKEN>"}'
# -> 200 {"status":"success","data":{"tokenType":"bearer","accessToken":"...","refreshToken":"..."}}
```

Use the returned `accessToken` as `Bearer <ADMIN_JWT>` below.

### Field/units gotchas (confirmed)
- Step objects: **omit `id`** on create/update (server auto-generates UUIDs; sending `"id":"1"` → invalid UUID).
- `POST .../new` and `PUT .../steps/update`: `timestamp` in **milliseconds**.
- All `analytics/*`: `start_time` / `end_time` in **nanoseconds**.
- `analytics/steps` requires the `steps` array in the body (sending only `funnel_id`+times → 500 ClickHouse syntax error, a *different* bug).
- `analytics/steps/overview` requires `step_start` + `step_end` (integers = step orders; must differ, else `"step start and end cannot be the same"`).

---

## 1. Create funnel + set 3 steps (working config)

```bash
# create
curl -sS -X POST 'http://localhost:8080/api/v1/trace-funnels/new' \
  -H 'Authorization: Bearer <ADMIN_JWT>' -H 'Content-Type: application/json' \
  -d '{"funnel_name":"agent-pipeline","timestamp":1784388384995}'
```
**200** →
```json
{"status":"success","data":{"funnel_id":"019f75d5-f9ce-7685-8db1-097baa394562","funnel_name":"agent-pipeline","created_at":1784388384995,"created_by":"019f5768-e00c-7dd6-a1aa-58889e772a90","updated_at":1784388385230,"org_id":"019f5768-e00c-7dc4-9376-b2b4a44c5e55"}}
```

```bash
# set steps (agent answer -> tool search_tool -> chat gpt-4o-mini)
curl -sS -X PUT 'http://localhost:8080/api/v1/trace-funnels/steps/update' \
  -H 'Authorization: Bearer <ADMIN_JWT>' -H 'Content-Type: application/json' \
  -d '{"funnel_id":"019f75d5-f9ce-7685-8db1-097baa394562","timestamp":1784388385290,"steps":[
        {"step_order":1,"service_name":"warmup-agent","span_name":"agent answer","filters":{"items":[],"op":"and"},"latency_pointer":"start","has_errors":false},
        {"step_order":2,"service_name":"warmup-agent","span_name":"tool search_tool","filters":{"items":[],"op":"and"},"latency_pointer":"start","has_errors":false},
        {"step_order":3,"service_name":"warmup-agent","span_name":"chat gpt-4o-mini","filters":{"items":[],"op":"and"},"latency_pointer":"end","has_errors":false}]}'
```
**200** → funnel object with the 3 steps and server-assigned step UUIDs.

---

## 2. Per-step analytics — HTTP 200 (window Jul 11–14 2026 in ns)

`start_time = 1783728000000000000` (2026-07-11 00:00 UTC), `end_time = 1783987200000000000` (2026-07-14 00:00 UTC).

```bash
curl -sS -X POST 'http://localhost:8080/api/v1/trace-funnels/analytics/steps' \
  -H 'Authorization: Bearer <ADMIN_JWT>' -H 'Content-Type: application/json' \
  -d '{"funnel_id":"019f75d5-f9ce-7685-8db1-097baa394562","start_time":1783728000000000000,"end_time":1783987200000000000,"steps":[
        {"step_order":1,"service_name":"warmup-agent","span_name":"agent answer","filters":{"items":[],"op":"and"},"latency_pointer":"start","has_errors":false},
        {"step_order":2,"service_name":"warmup-agent","span_name":"tool search_tool","filters":{"items":[],"op":"and"},"latency_pointer":"start","has_errors":false},
        {"step_order":3,"service_name":"warmup-agent","span_name":"chat gpt-4o-mini","filters":{"items":[],"op":"and"},"latency_pointer":"end","has_errors":false}]}'
```
**200** →
```json
{"status":"success","data":[{"timestamp":"0001-01-01T00:00:00Z","data":{
  "total_s1_errored_spans":0,"total_s1_spans":22,
  "total_s2_errored_spans":0,"total_s2_spans":22,
  "total_s3_errored_spans":0,"total_s3_spans":0}}]}
```

### Key finding — funnels enforce strict intra-trace temporal ordering
`chat gpt-4o-mini` **exists in 10 of the 22 traces** (single-step funnel `chat gpt-4o-mini` alone → `total_s1_spans:10`).
But as **step 3 after `tool search_tool`** it converts to **0**, because in these agent traces the LLM `chat`
span fires *before* the `tool search_tool` span, so no trace satisfies step2→step3 ordering. The funnel
API returns 200 with `total_s3_spans:0` — it cannot distinguish "model never ran" from "model ran but
not in this order". (Corresponds to screenshot **4-funnel-results.png**: bars 22, 22, 0 with a red ↓100% drop.)

A conversion-**positive** ordering `agent answer → chat gpt-4o-mini → tool search_tool` yields
`total_s1:22, total_s2:2, total_s3:2`, and `analytics/overview` returns **200 with `conversion_rate: 9.09`**
— proof the overview endpoint returns a real rate when every step converts.

---

## 3. The NaN 500 — which endpoint actually breaks

`analytics/steps` does **not** 500 on a zero-match step (it returns `total_sN_spans:0`).
The **overview** endpoints (`analytics/overview` and `analytics/steps/overview`) 500, because they compute
`conversion_rate = converted / previous`; when the last step matches 0 spans that is `0/0 = NaN`, and Go's
JSON encoder rejects NaN.

Repro with step 3 = `chat gemini-2.0-flash` (a model that emitted **zero spans anywhere**):

```bash
curl -sS -X POST 'http://localhost:8080/api/v1/trace-funnels/analytics/steps/overview' \
  -H 'Authorization: Bearer <ADMIN_JWT>' -H 'Content-Type: application/json' \
  -d '{"funnel_id":"019f75d5-f9ce-7685-8db1-097baa394562","start_time":1783728000000000000,"end_time":1783987200000000000,"step_start":1,"step_end":3,"steps":[
        {"step_order":1,"service_name":"warmup-agent","span_name":"agent answer","filters":{"items":[],"op":"and"},"latency_pointer":"start","has_errors":false},
        {"step_order":2,"service_name":"warmup-agent","span_name":"tool search_tool","filters":{"items":[],"op":"and"},"latency_pointer":"start","has_errors":false},
        {"step_order":3,"service_name":"warmup-agent","span_name":"chat gemini-2.0-flash","filters":{"items":[],"op":"and"},"latency_pointer":"end","has_errors":false}]}'
```
**500** (Content-Type text/plain), verbatim body:
```
app.ApiResponse.Data: []*v3.Row: v3.Row.Data: unsupported value: NaN
```

The **same 500/NaN** also occurs on `analytics/overview` for the *working* funnel (step 3 = `chat gpt-4o-mini`)
because its step-3 conversion is also 0 — i.e. the current demo funnel returns 200 on `analytics/steps`
(22,22,0) but 500 on the overview endpoints. In the UI this surfaces as **"No data" / "Conversion rate 0.00%"**
in the OVERALL FUNNEL METRICS panel (the UI swallows the raw 500). This is why screenshot 5 renders the
verbatim HTTP exchange rather than a UI panel.

(Corresponds to screenshot **5-funnel-500.png**.)

---

## Screenshots

| File | Shows |
|---|---|
| `images/3-funnel-ui.png` | `agent-pipeline` config, all 3 steps (warmup-agent: agent answer → tool search_tool → chat gpt-4o-mini). |
| `images/4-funnel-results.png` | Results view, Last-1-week range covering Jul 12: step spans 22 / 22 / 0, Step1→Step2 conversion 100.00%, overall "No data" (the NaN symptom). |
| `images/5-funnel-500.png` | Verbatim POST `analytics/steps/overview` with step 3 = `chat gemini-2.0-flash` → HTTP 500 `...v3.Row.Data: unsupported value: NaN`. |

---

## To reproduce the broken (zero-match) variant against the live funnel
The `agent-pipeline` funnel is **left in the working state** (step 3 = `chat gpt-4o-mini`). To reproduce the
NaN 500 as a *persisted* broken funnel:

1. `PUT /api/v1/trace-funnels/steps/update` with the body from §1 but step 3
   `"span_name":"chat gemini-2.0-flash"` (keep `funnel_id`, add `"timestamp":<now-ms>`).
2. `POST /api/v1/trace-funnels/analytics/steps/overview` with the §3 body → **500 NaN**.
3. Restore: repeat the §1 steps-update PUT (step 3 back to `chat gpt-4o-mini`).

Note: you do **not** need to persist the broken step to trigger the 500 — the analytics endpoints read the
`steps` array from the request body, so §3's single curl reproduces it without mutating the funnel.
