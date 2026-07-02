"""ayllu.lounge — the collaboration surface, learned from the tribe lounge/bus.

The tribe let souls talk in a shared room. a11oy keeps that, in-memory and honest: each
posted message carries a source label ("brain" when a real model answered, else
"persona-fallback"), so a reader always knows whether they are seeing a grounded reply
or an honest placeholder. `deliberate()` runs a BOUNDED council round — one honest turn
per persona — and never fabricates when no backend is injected.
"""
from __future__ import annotations

import time
from typing import Any


class Lounge:
    def __init__(self, capacity: int = 200) -> None:
        self.capacity = int(capacity)
        self.feed: list[dict[str, Any]] = []

    def post(self, persona: str, text: str, *, source: str = "persona") -> dict[str, Any]:
        entry = {"ts": time.time(), "persona": persona, "text": text, "source": source}
        self.feed.append(entry)
        if len(self.feed) > self.capacity:
            self.feed = self.feed[-self.capacity:]
        return entry

    def recent(self, n: int = 50) -> list[dict[str, Any]]:
        return self.feed[-int(n):]

    async def deliberate(
        self,
        prompt: str,
        personas: list,
        *,
        model_complete=None,
        difficulty: float = 0.6,
        two_person_attested: bool = False,
    ) -> dict[str, Any]:
        from .loop import run_turn

        rounds = []
        for p in personas:
            turn = await run_turn(
                p, prompt,
                model_complete=model_complete,
                difficulty=difficulty,
                two_person_attested=two_person_attested,
            )
            src = "brain" if turn.get("answer") is not None else "persona-fallback"
            self.post(p.name, turn.get("answer") or turn.get("honesty"), source=src)
            rounds.append(turn)
        return {
            "prompt": prompt,
            "participants": [p.name for p in personas],
            "rounds": rounds,
            "note": "bounded council round; each turn honest (no fabrication when "
                    "a model backend is absent)",
        }
