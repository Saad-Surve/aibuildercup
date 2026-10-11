"""Serialize duplicate deliveries in the current single-instance worker runtime."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from functools import wraps


@dataclass
class _JobLock:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    users: int = 0


_locks: dict[tuple[str, str, str], _JobLock] = {}


def serialize_job[**P, T](worker: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
    """Let a duplicate delivery observe the first invocation's terminal state.

    Worker entry points require keyword-only owner_uid/project_id/job_id. Their
    existing terminal-state checks run inside this guard, so a duplicate never
    starts model calls while the first delivery is still processing. Entries are
    removed after the last waiter exits. This is not a distributed job lease;
    scaling beyond the current single Cloud Run instance needs one in Firestore.
    """

    @wraps(worker)
    async def run(*args: P.args, **kwargs: P.kwargs) -> T:
        key = (str(kwargs["owner_uid"]), str(kwargs["project_id"]), str(kwargs["job_id"]))
        entry = _locks.get(key)
        if entry is None:
            entry = _JobLock()
            _locks[key] = entry
        entry.users += 1
        try:
            async with entry.lock:
                return await worker(*args, **kwargs)
        finally:
            entry.users -= 1
            if entry.users == 0:
                _locks.pop(key, None)

    return run
