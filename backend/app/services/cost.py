"""LLM cost estimation and the project cost cap.

Pure arithmetic over the token usage the provider reports; the prices live in
`Settings` so a repricing never means editing call sites. Used both to fill
`costEstimateUsd` on analysis documents and to enforce `max_project_cost_usd`
before a new analysis run is accepted.
"""

from app.providers.base import LlmUsage


def estimate_cost_usd(
    usage: LlmUsage,
    *,
    input_price_per_mtok: float,
    output_price_per_mtok: float,
) -> float:
    """Estimated USD for one call. Rounded to six decimals to keep sums stable."""
    total = (
        usage.input_tokens * input_price_per_mtok
        + usage.output_tokens * output_price_per_mtok
    ) / 1_000_000
    return round(total, 6)


def remaining_budget_usd(spent_usd: float, *, max_project_cost_usd: float) -> float:
    """How much of the project budget is left. Never negative."""
    return round(max(0.0, max_project_cost_usd - spent_usd), 6)


def is_over_budget(spent_usd: float, *, max_project_cost_usd: float) -> bool:
    """True once the project has consumed its cost cap."""
    return spent_usd >= max_project_cost_usd


__all__ = ["estimate_cost_usd", "is_over_budget", "remaining_budget_usd"]
