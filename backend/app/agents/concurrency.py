"""Ordered bounded waves, with an allowance for every in-flight model request."""

import asyncio
import math
from collections.abc import Callable, Coroutine, Sequence
from typing import Any, Protocol


class CallSummary(Protocol):
    costEstimateUsd: float
    callCount: int


async def budgeted_map[T, S: CallSummary](
    items: Sequence[T],
    work: Callable[[T], Coroutine[Any, Any, S]],
    *,
    budget_usd: float,
    call_estimate: float,
    max_calls: int,
    concurrency: int = 3,
) -> tuple[list[S], Sequence[T]]:
    """Admit in input order; failed/cheap calls release room for the next wave.

    Work still owns its durable atomic call reservation and settlement. A wave
    reserves the full existing per-call estimate before any of its work starts.
    Results are returned in input order regardless of completion order.
    """
    results: list[S] = []
    index = 0
    while index < len(items):
        remaining = max(0.0, budget_usd - sum(result.costEstimateUsd for result in results))
        room = max_calls - sum(result.callCount for result in results)
        affordable = math.floor((remaining + 1e-9) / call_estimate) if call_estimate > 0 else room
        width = min(concurrency, room, affordable, len(items) - index)
        if width <= 0:
            break
        tasks = [asyncio.create_task(work(item)) for item in items[index : index + width]]
        try:
            results.extend(await asyncio.gather(*tasks))
        except BaseException:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise
        index += width
    return results, items[index:]
