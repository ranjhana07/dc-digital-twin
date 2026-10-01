import threading
import time
from collections.abc import Callable
from typing import Generic, TypeVar

T = TypeVar("T")


class Batcher(Generic[T]):
    def __init__(
        self,
        sink: Callable[[list[T]], None],
        max_size: int = 2000,
        max_age_s: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
        max_backlog: int = 200_000,
    ) -> None:
        self.max_backlog = max_backlog
        self.requeued = 0
        self.sink = sink
        self.max_size = max_size
        self.max_age_s = max_age_s
        self.clock = clock
        self._items: list[T] = []
        self._opened_at = 0.0
        self._lock = threading.Lock()
        self.flushed_batches = 0
        self.flushed_items = 0

    def add(self, item: T) -> None:
        batch: list[T] | None = None
        with self._lock:
            if not self._items:
                self._opened_at = self.clock()
            self._items.append(item)
            if len(self._items) >= self.max_size:
                batch = self._take()
        if batch:
            self._write(batch)

    def flush_if_due(self) -> int:
        batch: list[T] | None = None
        with self._lock:
            if self._items and self.clock() - self._opened_at >= self.max_age_s:
                batch = self._take()
        return self._write(batch) if batch else 0

    def flush(self) -> int:
        with self._lock:
            batch = self._take()
        return self._write(batch) if batch else 0

    def pending(self) -> int:
        with self._lock:
            return len(self._items)

    def _requeue(self, batch: list[T]) -> None:
        with self._lock:
            self._items = batch + self._items
            if len(self._items) > self.max_backlog:
                del self._items[: len(self._items) - self.max_backlog]
            self._opened_at = self.clock()
            self.requeued += len(batch)

    def _take(self) -> list[T]:
        batch, self._items = self._items, []
        return batch

    def _write(self, batch: list[T]) -> int:
        try:
            self.sink(batch)
        except Exception:
            self._requeue(batch)
            raise
        self.flushed_batches += 1
        self.flushed_items += len(batch)
        return len(batch)
