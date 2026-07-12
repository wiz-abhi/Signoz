# Warm Up Before You Build — SigNoz × WeMakeDevs

My submission for the **"Warm Up Before You Build"** pre-event challenge of the [Agents of SigNoz hackathon](https://www.wemakedevs.org/hackathons/signoz).

**📝 The blog post: [signoz-warmup-blog.md](signoz-warmup-blog.md)** — *My AI Agent Took 21 Seconds to Answer "What Is 2 + 2" — SigNoz Found Out Why in Two Clicks.*

## What's in here

| Path | What it is |
|---|---|
| [signoz-warmup-blog.md](signoz-warmup-blog.md) | The blog post |
| [warmup-agent/agent.py](warmup-agent/agent.py) | A tiny plan → tool → answer AI agent (Gemini `gemini-3.1-flash-lite`), manually instrumented with OpenTelemetry following the GenAI semantic conventions. Ships with a deliberate silent-retry-loop bug (`--fixed` turns it off). |
| [warmup-agent/casting.yaml](warmup-agent/casting.yaml) | Foundry casting file used to self-host SigNoz via Docker Compose |
| [warmup-agent/make_dashboard.py](warmup-agent/make_dashboard.py) | Creates the "Agent Health" dashboard via the SigNoz API |
| [warmup-agent/shots*.py](warmup-agent/shots.py) | Playwright scripts that captured the screenshots |
| [warmup-agent/screenshots/](warmup-agent/screenshots) | Real screenshots from my self-hosted SigNoz |

## Reproduce it

```bash
# 1. Self-host SigNoz (Docker required)
curl -fsSL https://signoz.io/foundry.sh | bash
foundryctl cast -f warmup-agent/casting.yaml
# UI: http://localhost:8080 — create your account first (the collector
# won't accept OTLP data until the first org exists!)

# 2. Run the agent
cd warmup-agent
python -m venv .venv && .venv/bin/pip install opentelemetry-sdk opentelemetry-exporter-otlp-proto-http openai
export GEMINI_API_KEY=...        # or CEREBRAS_API_KEY; falls back to a local stub
.venv/bin/python agent.py --runs 3          # the slow, buggy version (~21s)
.venv/bin/python agent.py --fixed --runs 5  # after the fix (~2.6s)

# 3. Open a slow trace in SigNoz and click the span's "Logs" tab. That's the post.
```
