"""
warmup-agent: a tiny plan -> tool -> answer agent instrumented with OpenTelemetry.

Sends traces + logs to a self-hosted SigNoz at localhost:4318 (OTLP/HTTP).
LLM calls use OpenAI if OPENAI_API_KEY is set, otherwise a local stub with
realistic latency/token numbers. Spans carry OTel GenAI semantic-convention
attributes (gen_ai.*) either way.

Usage:
  python agent.py            # buggy tool: silent retry loop, ~19s answers
  python agent.py --fixed    # capped retries/backoff, ~2s answers
  python agent.py --runs 8   # generate traffic
"""
import argparse
import logging
import os
import random
import sys
import time

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter

OTLP = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
resource = Resource.create({"service.name": "warmup-agent", "deployment.environment": "local"})

tp = TracerProvider(resource=resource)
tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{OTLP}/v1/traces")))
trace.set_tracer_provider(tp)
tracer = trace.get_tracer("warmup-agent")

lp = LoggerProvider(resource=resource)
lp.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter(endpoint=f"{OTLP}/v1/logs")))
handler = LoggingHandler(level=logging.INFO, logger_provider=lp)
logging.basicConfig(level=logging.INFO, handlers=[handler, logging.StreamHandler(sys.stderr)])
log = logging.getLogger("warmup-agent")

if os.environ.get("GEMINI_API_KEY"):
    from openai import OpenAI
    PROVIDER = "gemini"
    MODEL = "gemini-3.1-flash-lite"
    oai = OpenAI(
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key=os.environ["GEMINI_API_KEY"],
    )
elif os.environ.get("CEREBRAS_API_KEY"):
    from openai import OpenAI
    PROVIDER = "cerebras"
    MODEL = "gpt-oss-120b"
    oai = OpenAI(base_url="https://api.cerebras.ai/v1", api_key=os.environ["CEREBRAS_API_KEY"])
else:
    PROVIDER = None
    MODEL = "stub-model"
    oai = None
USE_OPENAI = oai is not None


def llm(operation: str, prompt: str) -> str:
    """One LLM call, recorded per OTel GenAI semantic conventions."""
    with tracer.start_as_current_span(f"chat {MODEL}") as span:
        span.set_attribute("gen_ai.operation.name", "chat")
        span.set_attribute("gen_ai.system", PROVIDER or "stub")
        span.set_attribute("gen_ai.request.model", MODEL)
        span.set_attribute("gen_ai.agent.name", "warmup-agent")
        span.set_attribute("gen_ai.prompt", prompt)
        if USE_OPENAI:
            resp = oai.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_completion_tokens=200,
            )
            text = resp.choices[0].message.content
            in_tok = resp.usage.prompt_tokens
            out_tok = resp.usage.completion_tokens
        else:
            time.sleep(random.uniform(0.4, 0.9))  # realistic model latency
            in_tok = max(8, len(prompt.split()) + random.randint(2, 6))
            out_tok = random.randint(18, 60)
            text = {
                "plan": "1. Parse the arithmetic question. 2. Call search_tool. 3. Summarize.",
                "answer": "2 + 2 = 4. Verified via search_tool result.",
            }[operation]
        span.set_attribute("gen_ai.usage.input_tokens", in_tok)
        span.set_attribute("gen_ai.usage.output_tokens", out_tok)
        span.set_attribute("gen_ai.response.model", MODEL)
        log.info("llm %s completed (%d in / %d out tokens)", operation, in_tok, out_tok)
        return text


def flaky_upstream() -> bool:
    """Simulated flaky search backend: times out twice, succeeds third."""
    flaky_upstream.calls += 1
    return flaky_upstream.calls % 3 == 0


flaky_upstream.calls = 0


def search_tool(query: str, fixed: bool) -> str:
    max_retries = 1 if fixed else 3
    base_backoff = 0.2 if fixed else 4.0
    timeout = 0.5 if fixed else 3.0
    with tracer.start_as_current_span("tool search_tool") as span:
        span.set_attribute("gen_ai.tool.name", "search_tool")
        span.set_attribute("tool.query", query)
        attempt = 0
        while True:
            attempt += 1
            time.sleep(timeout if not flaky_upstream() else 0.3)
            if flaky_upstream.calls % 3 == 0:
                span.set_attribute("tool.attempts", attempt)
                log.info("search_tool: succeeded on attempt %d", attempt)
                return "arithmetic: 2 + 2 = 4 (source: math)"
            if attempt >= max_retries:
                span.set_attribute("tool.attempts", attempt)
                log.warning("search_tool: giving up after %d attempts, using cache", attempt)
                return "arithmetic: 2 + 2 = 4 (cached)"
            log.warning("search_tool: upstream timeout, retrying (%d/%d)", attempt, max_retries)
            time.sleep(base_backoff * attempt)


def answer(question: str, fixed: bool) -> str:
    with tracer.start_as_current_span("agent answer") as span:
        span.set_attribute("gen_ai.operation.name", "invoke_agent")
        span.set_attribute("gen_ai.agent.name", "warmup-agent")
        span.set_attribute("agent.question", question)
        log.info("agent received question: %s", question)
        plan = llm("plan", f"Plan how to answer: {question}")
        facts = search_tool(plan, fixed=fixed)
        result = llm("answer", f"Answer '{question}' using: {facts}")
        log.info("agent answered: %s", result)
        return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixed", action="store_true")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--question", default="what is 2 + 2?")
    args = ap.parse_args()

    for i in range(args.runs):
        flaky_upstream.calls = 0
        t0 = time.time()
        out = answer(args.question, fixed=args.fixed)
        print(f"run {i+1}: {out}  ({time.time()-t0:.1f}s)")
        if USE_OPENAI and i + 1 < args.runs:
            time.sleep(6)  # stay under free-tier rate limits

    tp.shutdown()
    lp.shutdown()
