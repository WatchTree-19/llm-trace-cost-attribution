"""llm-trace-cost-attribution: cost waterfall over OpenTelemetry GenAI spans.

Vendor neutral. Input is the OTLP/JSON any OpenTelemetry exporter produces;
pricing is a plain table you own. No SDK, no provider client, no lock-in.
"""
from llm_trace_cost.pricing import PriceTable, DEFAULT_PRICES
from llm_trace_cost.attribution import (
    load_otlp,
    llm_calls,
    cost_table,
    waterfall,
    retry_breakdown,
    counterfactual,
    breakeven_retry_rate,
)

__all__ = [
    "PriceTable",
    "DEFAULT_PRICES",
    "load_otlp",
    "llm_calls",
    "cost_table",
    "waterfall",
    "retry_breakdown",
    "counterfactual",
    "breakeven_retry_rate",
]
__version__ = "0.0.1"
