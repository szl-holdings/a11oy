"""ayllu.daemon — always-on-but-cheap listener, learned from the tribe soul-daemon.

The tribe's insight: a persona can be "always on & listening" without burning tokens,
because an idle tick does only a free file/inbox check and a model is invoked ONLY when
a real message arrives. a11oy keeps that insight and adds a hard bound: at most
`max_wakes` model-invoking wakes per run. The daemon itself never calls a model — it
tells the caller WHEN to (via ayllu.loop.run_turn), keeping cost and control explicit.
"""
from __future__ import annotations

from typing import Any


class Daemon:
    def __init__(self, persona, *, max_wakes: int = 8) -> None:
        self.persona = persona
        self.max_wakes = int(max_wakes)
        self.wakes = 0
        self.idle_ticks = 0

    def tick(self, inbox: list) -> dict[str, Any]:
        """One cheap tick. `inbox` is the already-read list of pending messages.

        Returns whether the persona should wake (and thus incur a model call). An
        empty inbox is FREE — no model, no cost.
        """
        if not inbox:
            self.idle_ticks += 1
            return {"woke": False, "cost": "free", "idle_ticks": self.idle_ticks}
        if self.wakes >= self.max_wakes:
            return {"woke": False, "reason": "max_wakes reached (bounded)",
                    "pending": len(inbox)}
        self.wakes += 1
        return {"woke": True, "message": inbox[0], "wakes": self.wakes,
                "pending_after": len(inbox) - 1}

    def stats(self) -> dict[str, Any]:
        return {"persona": getattr(self.persona, "name", None),
                "wakes": self.wakes, "idle_ticks": self.idle_ticks,
                "max_wakes": self.max_wakes}
