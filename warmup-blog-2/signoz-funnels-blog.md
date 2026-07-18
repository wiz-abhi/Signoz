# I Built a Trace Funnel Over My AI Agent. A Retired Model Name Crashed the API.

I asked SigNoz a simple question: of the runs where my agent planned an answer and called its search tool, how many reached the LLM step? For a model I was still using, the funnel behaved. Then I pointed the third step at a model I'd stopped using, expecting to see 0%. Instead the analytics API handed me back an HTTP 500 and a message about `NaN`. A conversion funnel that cannot say "zero" has a sharp edge somewhere, and I went looking for it.

This is a warm-up post for the Agents of SigNoz hackathon. I self-hosted SigNoz v0.132.2 with Foundry ([the docs walk through it](https://signoz.io/docs/install/docker/)) and pointed a small AI agent at it, then spent a few days poking at a feature I hadn't seen anywhere else. My first warm-up post was about trace-to-log correlation; this one is a different corner of the product entirely.

## Why funnels, and why over agent traces

Conversion funnels are an old product-analytics idea: users land, they add to cart, they check out, and you measure the drop-off at each step. SigNoz took that shape and pointed it at traces. You define an ordered list of span-name steps, and it tells you what fraction of traces made it through each one. I went hunting for something like this in the LLM-observability tools I already knew, and I couldn't find a funnel primitive in any of them. Langfuse, LangSmith, Phoenix, Braintrust: plenty of tracing, but I didn't find a conversion funnel over trace steps in any of them.

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

![Agent reasoning loop: one logical LLM step fragments into three span names](IMG:1-span-fragmentation.png)

Here's the naming, straight from my agent:

```python
with tracer.start_as_current_span(f"chat {MODEL}") as span:
    span.set_attribute("gen_ai.operation.name", "chat")
    span.set_attribute("gen_ai.request.model", MODEL)
```

## Building the funnel

My first funnel had three steps: `agent answer`, then `tool search_tool`, then `chat gpt-4o-mini`. Steps one and two matched 22 out of 22. Step three could only ever match the ten traces where I'd used that model. The funnel was telling the truth, even if the truth was skewed by my naming.

![Funnel steps join on literal span names; a zero-match step crashes the API](IMG:2-funnel-join.png)

![SCREENSHOT-PLACEHOLDER: funnel configured in SigNoz UI]

Then I did the obvious thing. I named a model that I'd stopped using. Imagine a fallback or a version bump that quietly retires a model; the span name it produced is still in your funnel definition, but nothing matches it anymore. That's the realistic failure, and it's the one that broke.

## The crash

The moment the third step matched zero spans, the funnel stopped returning a number. It returned a server error.

At first I assumed I'd broken my own instrumentation. That's the honest reflex: when a tool errors on your data, you suspect your data. I went back to my exporter config, re-checked the span names against the ones in ClickHouse, and confirmed the counts were exactly what I expected. Twenty spans for one model, sixteen for another, eight for the third, and zero for the retired one. My data was fine, so the error was coming from the other side.

![SCREENSHOT-PLACEHOLDER: the HTTP 500 NaN response]

I probed the analytics API directly on July 16 to pin it down (the per-step numbers come from the funnel's `/analytics/steps` endpoint; note that creating funnels needs an editor or admin token, a read-only key gets a 403). With a step matching five spans, the call returned HTTP 200 and a sensible number:

<!-- TODO before publish: replace this note with the exact request (method, full endpoint path, JSON body) captured during the fresh-token re-probe, so the 500 is reproducible from the post alone. -->

```json
{ "conversion_rate": 22.73 }
```

With the same funnel pointed at a step where `total_s3_spans: 0`, the call returned HTTP 500:

```json
{ "error": "v3.Row.Data: unsupported value: NaN" }
```

There it is. A step that matches nothing should be a zero-percent conversion. Zero is a perfectly good answer to "how many made it this far." Instead, somewhere behind that endpoint, a zero-match step produces a `NaN` the response can't carry, and the whole request fails with a 500.

![SCREENSHOT-PLACEHOLDER: funnel results with conversion rate]

At the behavior level the cause is simple to state. Funnel steps join on the exact literal span name, so a retired model name matches an empty set, and the request fails instead of reporting zero. I've dug into where it happens and I'm filing an issue upstream with a repro, so I'll leave the internals for that. What matters for anyone using funnels today is that a zero-match step is a live crash, and GenAI span naming makes zero-match steps easy to create by accident.

## What actually works, and one thing that doesn't

The fix that held up: wrap the LLM call in a stable parent span. If every model call lives inside an outer `llm step` span with a constant name, you funnel on `llm step` and the model name stops mattering to the funnel. The GenAI-named child spans stay exactly as the convention wants them, so you lose nothing.

The tempting fix that doesn't work: the step filter clause. Funnel steps do accept an additional filter, and my first thought was to match on a stable attribute like `gen_ai.operation.name = "chat"` instead of the name. But the filter narrows *within* a span-name match rather than replacing it. A step still keys on one literal name, so no attribute filter can stitch `chat gpt-4o-mini` and `chat gemini-3.1-flash-lite` back into one step. Filters are still useful inside a step (scoping to one environment, say), just not for this. Knowing that saves you the hour I would have spent on it.

And the operational one: if a funnel suddenly reads 0% or throws a 500 right after a deploy, check whether a model swap changed your span names before you go tearing through your pipeline. The error message points at `NaN`, which sounds like a math bug deep in the stack. The real trigger might just be that yesterday's model name retired overnight.

## What I took away

Trace Funnels are, for my money, one of the most underrated primitives in SigNoz for agent work. Measuring drop-off across the steps of a trace maps onto agent pipelines so naturally that I'm surprised I couldn't find it in the dedicated LLM tools. The sharp edge is narrow and specific: step matching keys on literal span names, and GenAI naming guarantees your most important step won't have a single literal name. Until the matching understands that, funnel on a wrapper span with a name you control.

Rough corners are normal in a young feature. I want this one to win, so it's getting a proper bug report with a repro instead of a complaint.

## Resources

- OpenTelemetry GenAI span conventions: [gen-ai-spans.md](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-spans.md)
- [SigNoz docs](https://signoz.io/docs/)
- Install path: [SigNoz on Docker](https://signoz.io/docs/install/docker/)

---

*AI assistance disclosure. I used Claude as a research assistant and as an editor for structuring and tightening this post. The exploration, the self-hosted instance, the data, and the screenshots are mine. Every number here was verified against my live ClickHouse on July 17, 2026, and the HTTP 500 and 200 responses came from probing my own analytics API on July 16.*
