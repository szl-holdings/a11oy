"""EventBus — a minimal in-process publish/subscribe event bus.

No external broker. Subscribers register a callback for a topic (or "*" for all). When the
pool commits a cell it publishes a ("write", cell) event; reads publish ("read", cid).
This is the pub/sub layer of the KIPU substrate — organs subscribe to react to each
other's receipts without polling.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Callable, Any


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[Callable[[str, Any], None]]] = defaultdict(list)
        self._lock = threading.RLock()

    def subscribe(self, topic: str, callback: Callable[[str, Any], None]) -> Callable[[], None]:
        """Register `callback(topic, payload)`. Returns an unsubscribe function."""
        with self._lock:
            self._subs[topic].append(callback)

        def _unsub() -> None:
            with self._lock:
                if callback in self._subs[topic]:
                    self._subs[topic].remove(callback)

        return _unsub

    def publish(self, topic: str, payload: Any) -> int:
        """Deliver to subscribers of `topic` and of "*". Returns count delivered."""
        with self._lock:
            targets = list(self._subs.get(topic, [])) + list(self._subs.get("*", []))
        n = 0
        for cb in targets:
            try:
                cb(topic, payload)
                n += 1
            except Exception:
                # A misbehaving subscriber must not break the bus.
                pass
        return n
