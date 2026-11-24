"""In-memory event bus for SSE progress streaming.

Events are keyed by invoice_id, with a bounded replay history so a late-joining
SSE client still receives the full processing picture from the start.
"""
import queue
import threading
from collections import defaultdict, deque
from typing import Any

_MAX_HISTORY = 200


class EventBus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._history: dict[str, deque[dict[str, Any]]] = defaultdict(
            lambda: deque(maxlen=_MAX_HISTORY)
        )
        self._subscribers: dict[str, list["queue.Queue[dict[str, Any]]"]] = defaultdict(list)

    def publish(self, invoice_id: str, event: dict[str, Any]) -> None:
        with self._lock:
            self._history[invoice_id].append(event)
            subs = list(self._subscribers[invoice_id])
        for q in subs:
            q.put(event)

    def subscribe(self, invoice_id: str) -> "queue.Queue[dict[str, Any]]":
        q: "queue.Queue[dict[str, Any]]" = queue.Queue()
        with self._lock:
            for ev in self._history[invoice_id]:
                q.put(ev)
            self._subscribers[invoice_id].append(q)
        return q

    def unsubscribe(self, invoice_id: str, q: "queue.Queue[dict[str, Any]]") -> None:
        with self._lock:
            subs = self._subscribers[invoice_id]
            if q in subs:
                subs.remove(q)

    def history(self, invoice_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._history[invoice_id])


bus = EventBus()
