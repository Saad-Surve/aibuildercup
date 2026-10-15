"""Small process-local caches. Values are copied so callers cannot mutate shared results."""

from collections import OrderedDict
from collections.abc import Callable, Hashable
from copy import deepcopy
from threading import Lock
from time import monotonic


class ProcessCache[T]:
    def __init__(self, capacity: int, ttl: float = 1800) -> None:
        self.capacity = capacity
        self.ttl = ttl
        self._entries: OrderedDict[Hashable, tuple[float, T]] = OrderedDict()
        self._lock = Lock()
        self._stripes = [Lock() for _ in range(32)]

    def get_or_load(self, key: Hashable, load: Callable[[], T]) -> T:
        with self._stripes[hash(key) % len(self._stripes)]:
            with self._lock:
                cached = self._entries.get(key)
                if cached and cached[0] > monotonic():
                    self._entries.move_to_end(key)
                    return deepcopy(cached[1])
            value = load()
            with self._lock:
                self._entries[key] = (monotonic() + self.ttl, deepcopy(value))
                self._entries.move_to_end(key)
                while len(self._entries) > self.capacity:
                    self._entries.popitem(last=False)
            return value
