"""Pricing model. Prices are USD per 1,000,000 tokens, keyed by (system, model).

This table is illustrative and editable. It is deliberately not fetched from any
provider API: you own the numbers, you version them with your repo, and the tool
never phones home. Override DEFAULT_PRICES or pass your own PriceTable.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Price:
    input_per_mtok: float   # USD per 1e6 input tokens
    output_per_mtok: float  # USD per 1e6 output tokens


class PriceTable:
    """Maps (gen_ai.system, model) -> Price. Unknown models cost 0 and are flagged."""

    def __init__(self, prices: dict[tuple[str, str], Price] | None = None):
        self._prices: dict[tuple[str, str], Price] = dict(prices or {})

    def get(self, system: str, model: str) -> Price | None:
        return self._prices.get((system, model))

    def cost(self, system: str, model: str, input_tokens: int, output_tokens: int) -> float:
        p = self.get(system, model)
        if p is None:
            return 0.0
        return (input_tokens / 1e6) * p.input_per_mtok + (output_tokens / 1e6) * p.output_per_mtok

    def known(self, system: str, model: str) -> bool:
        return (system, model) in self._prices

    def with_overrides(self, extra: dict[tuple[str, str], Price]) -> "PriceTable":
        merged = dict(self._prices)
        merged.update(extra)
        return PriceTable(merged)


# Illustrative list prices (USD / 1e6 tokens). Edit to match your contract.
DEFAULT_PRICES = PriceTable({
    ("anthropic", "claude-opus-4"):        Price(15.00, 75.00),
    ("anthropic", "claude-sonnet-4"):      Price(3.00, 15.00),
    ("anthropic", "claude-haiku-3-5"):     Price(0.80, 4.00),
    ("openai", "gpt-4o"):                  Price(2.50, 10.00),
    ("openai", "gpt-4o-mini"):             Price(0.15, 0.60),
})
