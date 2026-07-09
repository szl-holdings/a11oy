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
        debate: bool = False,
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
            turn["round"] = 1
            src = "brain" if turn.get("answer") is not None else "persona-fallback"
            self.post(p.name, turn.get("answer") or turn.get("honesty"), source=src)
            rounds.append(turn)

        mode = "single-round"
        # Debate-then-converge (after arXiv:2305.14325, Multiagent Debate): one
        # bounded extra round where each persona reads its peers' round-1 positions,
        # states dissent or agreement explicitly, and revises. EXACTLY two rounds —
        # never an open-ended loop. Runs only when a real/stub backend is injected
        # and at least two personas answered (an honest debate needs peers).
        if debate and model_complete is not None:
            positions = [
                (r.get("persona"), r.get("answer"))
                for r in rounds if r.get("answer")
            ]
            if len(positions) >= 2:
                mode = "debate"
                for p in personas:
                    peers = "\n\n".join(
                        f"[{name}] {ans[:1200]}" for name, ans in positions
                        if name != p.name
                    )
                    debate_prompt = (
                        "COUNCIL DEBATE ROUND (bounded: this is the final round).\n"
                        f"Original question:\n{prompt}\n\n"
                        f"Your peers' opening positions:\n{peers}\n\n"
                        "State explicitly where you agree or dissent, then give "
                        "your revised answer. Honest dissent beats false consensus."
                    )
                    turn = await run_turn(
                        p, debate_prompt,
                        model_complete=model_complete,
                        difficulty=difficulty,
                        two_person_attested=two_person_attested,
                    )
                    turn["round"] = 2
                    src = ("brain" if turn.get("answer") is not None
                           else "persona-fallback")
                    self.post(p.name, turn.get("answer") or turn.get("honesty"),
                              source=src)
                    rounds.append(turn)
            else:
                mode = "single-round"

        return {
            "prompt": prompt,
            "participants": [p.name for p in personas],
            "rounds": rounds,
            "mode": mode,
            "note": "bounded council; each turn honest (no fabrication when a model "
                    "backend is absent); debate mode = exactly two rounds, "
                    "after arXiv:2305.14325",
        }
