# Scope: cost waterfall over OTel traces, no vendor lock-in

## Goal

Turn an OpenTelemetry trace of an agent conversation into a dollar story a platform
team can act on: per-turn cost, retry waste, and a counterfactual reroute that answers
"this conversation cost $X, if the cheap turns went to a smaller model it would cost
$Y, switch when?"

## In scope

- Input is OTLP/JSON only (the format any OTel exporter emits). No provider SDK, no
  proprietary export format, no api calls.
- Spans follow the OTel GenAI semantic conventions: `gen_ai.system`,
  `gen_ai.request.model`, `gen_ai.operation.name`, `gen_ai.usage.input_tokens`,
  `gen_ai.usage.output_tokens`.
- Pricing is a user-owned table keyed by `(system, model)`, versioned in-repo and
  fully overridable. Unknown models are flagged, never guessed.
- Outputs: per-call cost table, waterfall by turn, retry-spend breakdown, counterfactual
  reroute under a user-supplied policy, and a switch-when breakeven.
- A Jupyter demo that runs on a checked-in sample trace with no api keys.

## Explicitly out of scope (for v0)

- No live model calls or token counting. The tool consumes token counts already on the
  spans; it does not re-tokenize or re-run prompts.
- No bundled per-provider price feed. Prices change and are contract-specific; shipping
  a "current" table would be both wrong and a soft lock-in. The table is yours.
- No dashboard or hosted service. Library plus notebook only.

## Open question: standardizing retry attribution

Retry spend is the most under-instrumented dimension and the main reason this is worth
building separately rather than as a query on existing tooling. There is no published
OTel GenAI attribute for retry count today. This repo reads `gen_ai.request.retry_count`
as a proposed attribute and degrades cleanly (treats calls as attempt 0) when it is
absent. Worth raising on the OTel / OpenLLMetry semantic-conventions track so the
dimension is portable rather than bespoke.

## Acceptance

- `load_otlp` + `llm_calls` produce a priced per-call table from the sample trace.
- `waterfall`, `retry_breakdown`, `counterfactual`, `breakeven_retry_rate` all return
  sensible numbers and are exercised by the demo notebook end to end.
- README documents the no-vendor-lock-in stance and the price-table contract.
