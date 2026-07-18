# I Built a Trace Funnel Over My AI Agent. The Conversion Rate Came Back NaN.

I asked SigNoz a simple question: of the runs where my agent planned an answer and called its search tool, how many reached the LLM step? The funnel said zero, for a model that had demonstrably run in ten traces. Chasing that zero took me somewhere better: an analytics endpoint that answers HTTP 500 where "0%" should be. A conversion funnel that cannot say "zero" has a sharp edge somewhere, and I went looking for it.

This is a warm-up post for the Agents of SigNoz hackathon. I self-hosted SigNoz v0.132.2 with Foundry ([the docs walk through it](https://signoz.io/docs/install/docker/)), pointed a small AI agent at it, and spent a few days on a feature I hadn't seen anywhere else. My first warm-up post covered trace-to-log correlation; this one is a different corner of the product.

## Why funnels, and why over agent traces

Conversion funnels are an old product-analytics idea: land, add to cart, check out, measure the drop-off at each step. SigNoz took that shape and pointed it at traces. You define an ordered list of span-name steps, and it tells you what fraction of traces made it through each one. I went hunting for this in the LLM-observability tools I already knew, and came up empty. Langfuse, LangSmith, Phoenix, Braintrust: plenty of tracing, but I didn't find a conversion funnel over trace steps in any of them.

For an agent, that shape is exactly right. An agent run is a small pipeline. Plan, call a tool, call the model, answer. If some fraction of runs never reach the model step, or the tool step silently drops out after a deploy, a funnel is the cleanest way to see it. So I opened Traces, found the Funnels section, and started building.

## The data I was working with

A single session of agent runs left 22 traces under one service, `warmup-agent`. Small n, but as it turns out, more than enough to hit the edge. Every trace has an `agent answer` span and a `tool search_tool` span. Then there's the LLM step, and this is where it gets interesting. I switched models a few times during that session, and my spans are named following the OpenTelemetry GenAI semantic conventions (still marked experimental), which [specify the span name as `{operation} {model}`](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-spans.md). One logical operation, but the name changes with the model.

I confirmed the shape straight from ClickHouse:

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

That's 44 chat spans across 22 traces, split three ways by model. The `agent answer` and `tool search_tool` spans match all 22 traces each; the LLM step matches at most 10 of them under any single name. This is correct instrumentation. The convention says the model belongs in the span name, my exporter obeys, and the result is that "the LLM call" has no single name to funnel on.

![Agent reasoning loop: one logical LLM step fragments into three span names](https://raw.githubusercontent.com/wiz-abhi/Signoz/main/warmup-blog-2/images/1-span-fragmentation.png)

Here's the naming, straight from my agent:

```python
with tracer.start_as_current_span(f"chat {MODEL}") as span:
    span.set_attribute("gen_ai.operation.name", "chat")
    span.set_attribute("gen_ai.request.model", MODEL)
```

## Building the funnel

My first funnel had three steps in the order I think of my agent: `agent answer`, then `tool search_tool`, then `chat gpt-4o-mini`.

![The agent-pipeline funnel configured in SigNoz: three steps on the warmup-agent service](https://raw.githubusercontent.com/wiz-abhi/Signoz/main/warmup-blog-2/images/3-funnel-ui.png)

Steps one and two matched 22 out of 22. Step three matched zero.

![Funnel results: 22 and 22 span bars, then 0 with a 100% drop, while the overview panel shows No data](https://raw.githubusercontent.com/wiz-abhi/Signoz/main/warmup-blog-2/images/4-funnel-results.png)

Zero. For a model that demonstrably ran in ten traces. At first I assumed I'd broken my own instrumentation. That's the honest reflex: when a tool shows zeros on your data, you suspect your data. I went back to my exporter config, re-checked the span names against ClickHouse, even built a one-step funnel containing only `chat gpt-4o-mini`. That one matched 10 traces. So the spans exist, the names are right, and the funnel still says zero when the step sits third.

The explanation took me longer than I'd like to admit: funnels enforce strict temporal ordering within each trace, and my agent calls the LLM to *plan* before it calls the tool. The first `chat` span in every trace fires before `tool search_tool`, so no trace satisfies "chat after tool," and step three legitimately converts to zero. Fair enough, that's what a funnel means. But notice what the number can't tell you: a step reading 0 looks identical whether the model never ran or ran a thousand times in a different order. Reordering the steps to `agent answer` → `chat gpt-4o-mini` → `tool search_tool` gave me a real conversion rate: 9.09%.

![Funnel steps join on literal span names; a zero-match step crashes the API](https://raw.githubusercontent.com/wiz-abhi/Signoz/main/warmup-blog-2/images/2-funnel-join.png)

And that's before the naming problem from the diagram above even enters. Under any single name, the LLM step can only ever match the traces of that one model, at most 10 of my 22. Now imagine the realistic production event: a fallback or a version bump quietly retires a model, its span name lingers in your funnel definition, and the step's match count goes to zero for a second reason. That's where it stopped being a quirk and became a crash.

## The crash

With the third step pointed at a model that had emitted no spans at all, the funnel page went to "No data" and the conversion rate read 0.00%. The API underneath was doing something worse. The per-step endpoint (`/api/v1/trace-funnels/analytics/steps`) still answered HTTP 200, honestly reporting `total_s3_spans: 0`. But both overview endpoints, the ones that compute the conversion rate, returned HTTP 500 with this body:

```
app.ApiResponse.Data: []*v3.Row: v3.Row.Data: unsupported value: NaN
```

![The verbatim request and 500 NaN response from the funnel overview endpoint](https://raw.githubusercontent.com/wiz-abhi/Signoz/main/warmup-blog-2/images/5-funnel-500.png)

A step that matches nothing should be a zero-percent conversion. Zero is a perfectly good answer to "how many made it this far." Instead a zero-converting final step produces a `NaN` the response can't carry, the request dies with a 500, and the UI papers over it as "No data." I re-verified all of this today against my live instance; the exact curl commands, request bodies, and responses are in [the repo](https://github.com/wiz-abhi/Signoz/blob/main/warmup-blog-2/evidence/funnel-api-repro.md) if you want to reproduce it end to end (creating funnels needs an editor or admin token; a read-only key gets a 403).

I've dug into where it happens and I'm filing an issue upstream with a repro, so I'll leave the internals for that. What matters for anyone using funnels today is that a zero-converting step is a live crash behind a quiet UI, and GenAI span naming plus ordering makes zero-converting steps very easy to create by accident.

## What actually works, and one thing that doesn't

The fix that held up: wrap the LLM call in a stable parent span. If every model call lives inside an outer `llm step` span with a constant name, you funnel on `llm step` and the model name stops mattering to the funnel. The GenAI-named child spans stay exactly as the convention wants them, so you lose nothing.

The tempting fix that doesn't work: the step filter clause. Funnel steps do accept an additional filter, and my first thought was to match on a stable attribute like `gen_ai.operation.name = "chat"` instead of the name. But the filter narrows *within* a span-name match rather than replacing it. A step still keys on one literal name, so no attribute filter can stitch `chat gpt-4o-mini` and `chat gemini-3.1-flash-lite` back into one step. Filters are still useful inside a step (scoping to one environment, say), just not for this. Knowing that saves you the hour I would have spent on it.

Two operational habits, both learned the slow way. Before trusting any multi-step funnel, sanity-check each step as a single-step funnel first; that's a fast, honest span count per name, and it's how I proved my zeros were an ordering problem rather than missing data. And order your steps by when the spans actually start inside a trace, not by your mental model of the pipeline. My mental model said the LLM answers last; my traces said the LLM plans first. The funnel believed the traces.

## What I took away

Trace Funnels are, for my money, one of the most underrated primitives in SigNoz for agent work. Measuring drop-off across the steps of a trace maps onto agent pipelines so naturally that I'm surprised I couldn't find it in the dedicated LLM tools. The sharp edges are specific and avoidable once you can name them: steps match literal span names, GenAI naming guarantees your most important step won't have one, ordering follows the trace rather than your intentions, and a step that converts to zero crashes the overview API instead of reporting 0%. Funnel on a wrapper span with a name you control, and check your ordering with single-step funnels first.

Rough corners are normal in a young feature. I want this one to win, so it's getting a proper bug report with a repro instead of a complaint.

## Resources

- OpenTelemetry GenAI span conventions: [gen-ai-spans.md](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-spans.md)
- [SigNoz docs](https://signoz.io/docs/)
- Install path: [SigNoz on Docker](https://signoz.io/docs/install/docker/)

---

*AI assistance disclosure. I used Claude as a research assistant and as an editor for structuring and tightening this post. The exploration, the self-hosted instance, the data, and the screenshots are mine. Every number was verified against my live ClickHouse and my own funnel analytics API on July 17–18, 2026; the full request/response log is [in the repo](https://github.com/wiz-abhi/Signoz/blob/main/warmup-blog-2/evidence/funnel-api-repro.md).*
