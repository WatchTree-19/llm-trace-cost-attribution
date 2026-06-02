"""Attribution: turn OTLP GenAI spans into a per-call cost table, a waterfall,
a retry breakdown, and a counterfactual reroute. All pandas, all pure functions.

Input contract: the OTLP/JSON structure an OpenTelemetry exporter emits
(resourceSpans -> scopeSpans -> spans). Span attributes follow the OTel GenAI
semantic conventions:
    gen_ai.system            e.g. "anthropic"
    gen_ai.request.model     e.g. "claude-opus-4"
    gen_ai.operation.name    e.g. "chat", "tool"
    gen_ai.usage.input_tokens
    gen_ai.usage.output_tokens
Retry is read from gen_ai.request.retry_count when present. That attribute is not
yet part of the published conventions (see the scope issue); when it is absent we
treat the call as attempt 0, so the tool degrades cleanly on any standard exporter.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from llm_trace_cost.pricing import PriceTable


def _attrs_to_dict(attr_list: list[dict]) -> dict:
    """Flatten OTLP key/value attribute list into a plain dict."""
    out: dict = {}
    for kv in attr_list or []:
        key = kv.get("key")
        val = kv.get("value", {})
        if "stringValue" in val:
            out[key] = val["stringValue"]
        elif "intValue" in val:
            out[key] = int(val["intValue"])
        elif "doubleValue" in val:
            out[key] = float(val["doubleValue"])
        elif "boolValue" in val:
            out[key] = bool(val["boolValue"])
    return out


def load_otlp(path: str | Path) -> list[dict]:
    """Parse an OTLP/JSON trace export into a flat list of normalized spans."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    spans: list[dict] = []
    for rs in raw.get("resourceSpans", []):
        for ss in rs.get("scopeSpans", []):
            for sp in ss.get("spans", []):
                attrs = _attrs_to_dict(sp.get("attributes", []))
                spans.append({
                    "span_id": sp.get("spanId"),
                    "parent_span_id": sp.get("parentSpanId") or None,
                    "name": sp.get("name"),
                    "start_ns": int(sp.get("startTimeUnixNano", 0)),
                    "end_ns": int(sp.get("endTimeUnixNano", 0)),
                    "attrs": attrs,
                })
    spans.sort(key=lambda s: s["start_ns"])
    return spans


def llm_calls(spans: list[dict], prices: PriceTable) -> pd.DataFrame:
    """Filter to GenAI calls and build the per-call cost table."""
    rows = []
    for s in spans:
        a = s["attrs"]
        system = a.get("gen_ai.system")
        model = a.get("gen_ai.request.model")
        if system is None or model is None:
            continue
        in_tok = int(a.get("gen_ai.usage.input_tokens", 0))
        out_tok = int(a.get("gen_ai.usage.output_tokens", 0))
        retry = int(a.get("gen_ai.request.retry_count", 0))
        rows.append({
            "span_id": s["span_id"],
            "turn": a.get("gen_ai.turn.index"),
            "operation": a.get("gen_ai.operation.name", "chat"),
            "system": system,
            "model": model,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "retry_count": retry,
            "is_retry": retry > 0,
            "priced": prices.known(system, model),
            "cost_usd": prices.cost(system, model, in_tok, out_tok),
        })
    return pd.DataFrame(rows)


def cost_table(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["cum_cost_usd"] = out["cost_usd"].cumsum()
    return out


def waterfall(df: pd.DataFrame, by: str = "turn") -> pd.DataFrame:
    g = df.groupby(by, dropna=False)["cost_usd"].sum().reset_index()
    total = g["cost_usd"].sum()
    g["pct_of_total"] = (g["cost_usd"] / total * 100.0) if total else 0.0
    g["cum_cost_usd"] = g["cost_usd"].cumsum()
    return g


def retry_breakdown(df: pd.DataFrame) -> dict:
    total = float(df["cost_usd"].sum())
    retry_spend = float(df.loc[df["is_retry"], "cost_usd"].sum())
    return {
        "total_usd": total,
        "retry_usd": retry_spend,
        "retry_pct": (retry_spend / total * 100.0) if total else 0.0,
        "n_retries": int(df["is_retry"].sum()),
    }


def counterfactual(df: pd.DataFrame, prices: PriceTable, policy) -> pd.DataFrame:
    out = df.copy()
    new_systems, new_models, new_costs = [], [], []
    for _, row in out.iterrows():
        route = policy(row)
        sys_, mdl_ = route if route else (row["system"], row["model"])
        new_systems.append(sys_)
        new_models.append(mdl_)
        new_costs.append(prices.cost(sys_, mdl_, row["input_tokens"], row["output_tokens"]))
    out["cf_system"] = new_systems
    out["cf_model"] = new_models
    out["cf_cost_usd"] = new_costs
    out["saving_usd"] = out["cost_usd"] - out["cf_cost_usd"]
    return out


def breakeven_retry_rate(saving_usd: float, redo_cost_usd: float) -> float:
    """Switch-when math.

    Routing cheap turns to a smaller model saves `saving_usd` per conversation, but
    a weaker model may fail and force a redo on the strong model. Per rerouted turn
    with strong-model cost o and cheap-model cost h, the expected saving vs. always
    using the strong model is (o - h) - p * o, where p is the failure rate. Setting
    that to zero gives the breakeven:

        p_breakeven = saving_usd / redo_cost_usd        (equivalently 1 - h/o)

    Route while expected failure rate sits below p_breakeven; above it, keep the
    stronger model. Returns p in [0, 1].
    """
    if redo_cost_usd <= 0:
        return float("inf")
    return saving_usd / redo_cost_usd
