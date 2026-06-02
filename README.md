# llm-trace-cost-attribution

cost waterfall over OpenTelemetry traces. answers, for one agent conversation:

> this conversation cost $X. if you had routed the cheap turns to a smaller model
> it would have cost $Y. when is the switch worth it?

it reads the OTLP/JSON any OpenTelemetry exporter emits, prices each GenAI span from
a table you own, attributes the spend turn by turn (including wasted retries), and
runs a counterfactual reroute with a switch-when breakeven.

## the pitch

per-call token usage is already on your spans if you instrument with the OTel GenAI
semantic conventions. what is missing is the layer that turns those tokens into a
dollar story a platform team can act on: which turn cost the most, how much went to
retries, and what a cheaper routing policy would have saved. this is that layer.

## no vendor lock-in

- input is the OTLP/JSON wire format, not any provider SDK or proprietary export.
- spans follow the published OTel GenAI semantic conventions (`gen_ai.system`,
  `gen_ai.request.model`, `gen_ai.usage.*`). any conformant instrumentation works.
- pricing is a plain editable table keyed by `(system, model)`. you own the numbers,
  you version them in your repo, the tool never calls a provider api.
- unknown models cost zero and are flagged rather than guessed.

## what it does

1. `load_otlp` parses an OTLP/JSON trace into normalized spans.
2. `llm_calls` filters to GenAI spans and prices each one.
3. `waterfall` aggregates cost by turn with per-turn share and cumulative total.
4. `retry_breakdown` isolates spend on retried attempts (`gen_ai.request.retry_count`).
5. `counterfactual` reprices the trace under a routing policy you supply.
6. `breakeven_retry_rate` gives the failure rate at which the reroute stops paying.

## quickstart

```bash
pip install -e .
jupyter notebook notebooks/cost_waterfall_demo.ipynb
```

the notebook runs end to end on `data/sample_trace.json` (a six-turn support-agent
conversation with two tool calls and one retried turn) and needs no api keys: the
attribution layer works on token counts already in the trace.

```python
from llm_trace_cost import load_otlp, llm_calls, waterfall, DEFAULT_PRICES

spans = load_otlp("data/sample_trace.json")
df = llm_calls(spans, DEFAULT_PRICES)
print(waterfall(df))
```

## status

early scaffold. working: OTLP load, pricing, waterfall, retry attribution,
counterfactual reroute, breakeven, executed demo notebook. not yet built: cli,
multi-trace aggregation, a real chart renderer, packaged tests. see the open issue
for scope and the retry-attribution convention question.

## license

MIT. see `LICENSE`.
