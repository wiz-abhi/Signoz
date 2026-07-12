# My AI Agent Took 21 Seconds to Answer "What Is 2 + 2" — SigNoz Found Out Why in Two Clicks

*Warming up for the [Agents of SigNoz hackathon](https://www.wemakedevs.org/hackathons/signoz), I self-hosted SigNoz, pointed a tiny AI agent at it, and fell hard for one feature: the one-click jump from a slow trace span into the exact logs that explain it.*

> **TL;DR** — My agent answered "what is 2 + 2" in **20.9 seconds**. Its own logs, read in isolation, looked perfectly healthy. In SigNoz, the trace flamegraph showed one span eating **18.31 s — 87.62% of the request** — and clicking that span's **Logs** tab revealed a silent retry loop I didn't know I'd shipped. Two clicks from symptom to root cause. That trace↔logs correlation is my favorite feature, and this post is the story of finding it. (Then I pointed SigNoz's **MCP server** at the same data and had an AI assistant re-run the whole investigation — down to the exact line number of the bug.)

---

## Why a warm-up post about an AI agent

The hackathon's pre-event challenge — *Warm Up Before You Build* — asks you to self-host SigNoz, send it real telemetry, explore the product, and write about your favorite feature.

I could have pointed it at a hello-world web app. But the main event is themed **agent observability**, and agents have a nasty property that makes them the perfect stress test for an observability tool: **they fail quietly**. No 500s, no stack traces. They loop, they retry, they burn tokens on tangents — and then return a perfectly plausible answer. The failure isn't a crash; it's *behavior*. So my warm-up plan was simple: build a deliberately imperfect agent, wire it to SigNoz, and see how fast I could catch it misbehaving.

Spoiler: faster than I expected.

## Self-hosting SigNoz (~15 minutes, one gotcha)

SigNoz's current install path is **Foundry**, its new installer CLI (the old `git clone && docker compose up` flow is deprecated as of v0.130). Three steps:

```bash
# 1. Install the foundryctl CLI
curl -fsSL https://signoz.io/foundry.sh | bash
```

```yaml
# 2. casting.yaml — tell Foundry to deploy via Docker Compose
apiVersion: v1alpha1
kind: Installation
metadata:
  name: signoz
spec:
  deployment:
    flavor: compose
    mode: docker
```

```bash
# 3. Cast it
foundryctl cast -f casting.yaml
```

A couple of minutes later, `docker ps` showed the whole stack healthy — the SigNoz server, an OTel collector (the "ingester"), **ClickHouse** for storage, ClickHouse Keeper, and a Postgres metastore. UI on `http://localhost:8080`, OTLP ingestion on `4317` (gRPC) and `4318` (HTTP). No cloud account, no ingestion key; every byte of telemetry stays on my machine. (I'm on Windows 11 — Docker Desktop with the WSL2 backend, and the install script runs fine from Git Bash.)

**The gotcha worth knowing:** my first OTLP exports were rejected with connection resets, and the ingester logs showed the collector stuck in an OpAMP error/restart loop. The cause was hilariously mundane — I hadn't created the admin account yet. SigNoz's collector gets its config via OpAMP from the server, and until the first user/org exists it has nothing to serve. The moment I signed up at `localhost:8080`, the collector settled and ingestion turned green. If your self-hosted collector seems broken on first boot: **create your account first.**

![SigNoz Services page showing warmup-agent with P99 latency of 21,818 ms](https://raw.githubusercontent.com/wiz-abhi/Signoz/main/warmup-agent/screenshots/1-services.png)

The Services page a few minutes later: one application, `warmup-agent`, P99 latency **21,818 ms** — derived automatically from its spans, no metrics code written. For "2 + 2". We'll get to that.

## The agent, and how it's instrumented

My agent is a single Python file doing the classic loop real frameworks do — plan with an LLM (Gemini's `gemini-3.1-flash-lite`, via its OpenAI-compatible endpoint), call a tool, answer with an LLM:

```python
def answer(question: str) -> str:
    plan  = llm("plan", f"Plan how to answer: {question}")   # LLM call #1
    facts = search_tool(plan)                                # tool call
    return llm("answer", f"Answer {question} using: {facts}")# LLM call #2
```

For instrumentation I went OTel-native and hand-rolled spans following the **OpenTelemetry GenAI semantic conventions** — the emerging vendor-neutral standard (`gen_ai.*` attributes) for recording model names, token usage, agent steps, and tool calls. Every LLM call becomes a span carrying its contract with the outside world:

```python
with tracer.start_as_current_span(f"chat {MODEL}") as span:
    span.set_attribute("gen_ai.operation.name", "chat")
    span.set_attribute("gen_ai.request.model", MODEL)
    span.set_attribute("gen_ai.agent.name", "warmup-agent")
    # ... make the call ...
    span.set_attribute("gen_ai.usage.input_tokens", in_tok)
    span.set_attribute("gen_ai.usage.output_tokens", out_tok)
```

Two exporters point at my local SigNoz — `OTLPSpanExporter` for traces and `OTLPLogExporter` behind a stock `logging` handler for logs — both to `http://localhost:4318`. That logging handler is the quiet hero of this story: it stamps every log record emitted inside a span with that span's `trace_id` and `span_id`. Remember that detail.

(If you'd rather not write spans by hand: `opentelemetry-instrument` plus the GenAI instrumentation packages will auto-capture the same `gen_ai.*` attributes for OpenAI, LangChain, and friends with zero code changes. I wanted to feel the semantic conventions under my fingers at least once.)

## The mystery: 21 seconds for "2 + 2"

First real runs:

```text
run 1: arithmetic: 2 + 2 = 4 (source: math)  (21.9s)
run 2: Arithmetic: 2 + 2 = 4 (source: math)  (20.6s)
run 3: arithmetic: 2 + 2 = 4 (source: math)  (20.9s)
```

Correct answer. Absurd latency. And here's the thing — scrolling my terminal logs, nothing looked *wrong*. No errors, no exceptions, a clean INFO trail. This is the agent failure mode in miniature: everything "works," and something is deeply off.

Time to look at what SigNoz saw.

## Reading the flamegraph: where did 19.5 seconds go?

I opened the **Traces Explorer**, and rather than scrolling, made the query builder do the work — one filter, `durationNano >= 15s`, and only the pathological runs remained. Clicked one.

![Trace flamegraph: agent answer 20.89s with tool search_tool consuming 18.31s](https://raw.githubusercontent.com/wiz-abhi/Signoz/main/warmup-agent/screenshots/2-trace-flamegraph.png)

One glance told me *where*: the root `agent answer` span is 20.89 s, and sitting under it is a monstrous `tool search_tool` bar — **18.31 s, 87.62% of total execution time**. The two `chat gemini-3.1-flash-lite` spans flanking it are slivers (1.57 s for planning, a blink for the answer). So the LLM was never the problem; my *tool* was. The span's attributes (that's the GenAI conventions paying off) confirmed it: `gen_ai.tool.name: "search_tool"`, and — suspicious — `tool.attempts: 3`.

A trace tells you **where** the time went. It doesn't tell you **why**. Historically, "why" is where debugging gets miserable: copy the timestamp, switch to your logging tool, paste an approximate time window, squint at clock skew, guess which lines belong to this exact request.

## The feature that won me over: falling from a span into its logs

In SigNoz, the span details panel has a **Logs** tab. I clicked it with the slow span selected.

![The slow span selected with its correlated retry warning logs shown in the Logs tab](https://raw.githubusercontent.com/wiz-abhi/Signoz/main/warmup-agent/screenshots/3-span-related-logs.png)

The money shot. There they were. Not "logs from around that time" — *the logs of that exact span*, joined by the `trace_id` the instrumentation had been stamping all along, with the two WARN lines glowing amber in the panel:

```text
WARNING search_tool: upstream timeout, retrying (1/3)
WARNING search_tool: upstream timeout, retrying (2/3)
INFO    search_tool: succeeded on attempt 3
```

![Logs Explorer filtered by trace_id showing the full narrative of one agent run](https://raw.githubusercontent.com/wiz-abhi/Signoz/main/warmup-agent/screenshots/4-logs-explorer-trace-filter.png)

The same story in the Logs Explorer, filtered to `trace_id = '359c33c37996f84f6cf2fc02ffd5ab03'`: the full narrative of one agent run, from "received question" through the auto-captured `httpx` lines of the actual Gemini API calls, to the retry loop, to the answer — each LLM step even reporting its token usage (`llm plan completed (14 in / 196 out tokens)`).

And there was my bug, in three lines: my search tool had a **silent retry loop** — a 3 s timeout and an aggressive exponential backoff against a flaky upstream. It always recovered by attempt three, so no error ever surfaced. The agent "worked." The user just waited 21 seconds. Only the *combination* — trace for where, logs for why, welded by a shared ID — told the whole story, in roughly two clicks and zero timestamp archaeology.

The fix was two constants (cap the retries, fall back to cache fast). Next runs:

```text
run 1: arithmetic: 2 + 2 = 4 (cached)  (3.6s)
run 2: arithmetic: 2 + 2 = 4 (cached)  (2.6s)
run 3: arithmetic: 2 + 2 = 4 (cached)  (2.7s)
```

**~21 s → ~2.6 s.** But the fix isn't the point. The two clicks are the point.

## Why this works: one database, not three

This isn't UI sugar — it falls out of an architectural decision, and it's worth understanding:

1. **Context propagation.** OpenTelemetry stamps every log emitted inside a span with `trace_id`/`span_id`. The link lives in the data itself.
2. **One datastore.** SigNoz keeps traces, logs, *and* metrics in the same ClickHouse database. "Logs for this span" is a single indexed query — not a federated join across a trace store, a log store, and a metrics store with three query languages and three clocks.
3. **One query engine.** The same query builder speaks to all three signals, so correlation is a first-class action rather than a mental join you perform across browser tabs.

| | Stitched-together stack (Tempo + Loki + Prometheus) | SigNoz |
|---|---|---|
| Trace → logs | Copy timestamp, switch tool, guess the window | Click the span's **Logs** tab |
| Query languages | TraceQL + LogQL + PromQL | One query builder |
| Clock skew between signals | Your problem | Same store, same clock |
| Time to "why" | Minutes, if you're good | Seconds |

I've done the copy-the-timestamp dance for years. I didn't register how much of it was pure tax until SigNoz deleted it.

And the rest of the product hangs off the same spine, which is what makes the exploration feel coherent rather than like five bolted-together tools: the **Services** page derived RED metrics (P99, error rate, ops/sec) for my agent purely from its spans; the **Logs Explorer** runs fast structured queries over the same store (severity and trace filters, plus one-click **Create an Alert** / **Add to Dashboard** straight from any query); and because dashboards and alerts are built on the identical query builder, the p95-latency alert for this agent is the exact query I already wrote, reused.

To prove that to myself, I finished by building an **Agent Health** dashboard — four panels, each just a query-builder expression: agent runs over time (`count()` on the root span), p95 agent latency (`p95(duration_nano)`), LLM output tokens (`sum(gen_ai.usage.output_tokens)` — the GenAI conventions again), and tool retry warnings (`count()` on WARN logs). Four different questions, three different signals, one query language.

![Agent Health dashboard: runs, p95 latency, LLM output tokens, and retry warnings](https://raw.githubusercontent.com/wiz-abhi/Signoz/main/warmup-agent/screenshots/5-agent-health-dashboard.png)

Read the top-right and bottom-right panels together and the whole incident is visible at a glance: p95 latency pinned above 20 s exactly while the retry-warning counts spike, then both collapse after the fix. That's the correlation thesis of this post, drawn as two lines.

## One more thing: I let an AI agent read my telemetry

SigNoz recently shipped an official **MCP server** — a Model Context Protocol bridge that lets any MCP-compatible AI assistant (Claude Code, Cursor, Gemini CLI…) query your observability data with natural tool calls. Since this hackathon is literally called *Agents of SigNoz*, I couldn't resist closing the loop: an AI agent debugging my AI agent.

Setup was one Docker command plus a **read-only service account** (Settings → Service Accounts, `signoz-viewer` role — the MCP server only needs to read):

```bash
docker run -d -p 8000:8000 \
  -e TRANSPORT_MODE=http \
  -e SIGNOZ_URL=http://host.docker.internal:8080 \
  -e SIGNOZ_API_KEY=<service-account-key> \
  signoz/signoz-mcp-server:latest
```

That exposes **41 tools** — `signoz_list_services`, `signoz_search_traces`, `signoz_search_logs`, `signoz_query_metrics`, even `signoz_create_alert` and `signoz_create_dashboard`. I connected it to Claude Code and watched it re-run my entire investigation without touching the UI:

1. **"What services do I have?"** → `signoz_list_services`: one service, `warmup-agent`, 22 calls, **p99 21.7 s**, zero errors. (Zero errors! The agent is "healthy," remember?)
2. **"Show me the slowest agent runs"** → `signoz_search_traces` with `duration_nano > 15s`: trace `359c33c3…`, 20.89 s — the exact trace from the flamegraph above, returned with a clickable `webUrl`.
3. **"Any warnings?"** → `signoz_search_logs` with `severity_text = 'WARN'`: the retry-loop warnings — and because OTel logging captures code attributes, each log came back with `code.function.name: "search_tool"` and `code.line.number: 122`.

Read that last one again: the assistant didn't just find the warning — the telemetry told it **which function and which line of my source code produced it**. An AI agent read my observability data and pointed at line 122 of `agent.py`. That's the "agent-native observability" pitch, working end-to-end on my laptop, against a self-hosted instance, with a read-only key.

## Why this matters double for agents

Here's the thesis I'm carrying into the hackathon: **for AI agents, signal correlation isn't a nice-to-have — it's the whole game.**

An agent run *is* a trace: plan step, tool calls, reflection, answer — a tree of spans. The GenAI attributes annotate each step with model, tokens, and soon cost. The correlated logs record what each tool actually did. Put together, a single trace turns a non-deterministic black box into a *readable story of one decision*. My 18.3-second retry loop is the tame version; the same two-click move catches the expensive stuff — the agent that calls the same tool four times, the prompt that ballooned to 30k tokens, the tool that quietly falls back to stale cache.

Traditional services fail loudly. Agents fail politely. You need the trace to notice, and the logs to understand.

## What I'm building for the main event

This warm-up is becoming my Track 1 foundation: a multi-step, tool-calling agent with observability designed in from line one — per-step token and cost tracking via the GenAI conventions, alerts on runaway loops and token spikes, and a dashboard where every panel drills down to the exact trace (and therefore the exact logs) behind it. And now that I've seen the MCP server work, the loop I really want to build is *self-referential*: an agent that watches its own SigNoz telemetry and adjusts its behavior when it sees itself misbehaving. The warm-up was the rehearsal; now I know exactly which instrument carries the melody.

If you're on the fence about the hackathon: `foundryctl cast`, point anything you're building at `localhost:4318`, open your slowest trace, and click the span's **Logs** tab. That two-second fall from *where* to *why* is the moment "three pillars of observability" stops being a conference slide and becomes a debugging reflex.

---

*Everything here ran on my laptop: self-hosted SigNoz v0.132 via Foundry, OpenTelemetry Python SDK, Gemini (`gemini-3.1-flash-lite`) as the agent's brain, the SigNoz MCP server in Docker, and a ~140-line agent. Code, scripts, and all screenshots: [github.com/wiz-abhi/Signoz](https://github.com/wiz-abhi/Signoz). Written for the [Agents of SigNoz](https://www.wemakedevs.org/hackathons/signoz) warm-up challenge by [@wemakedevs](https://x.com/wemakedevs) and [SigNoz](https://signoz.io).*
