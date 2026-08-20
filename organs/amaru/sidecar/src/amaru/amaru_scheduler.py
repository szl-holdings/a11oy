"""
amaru_scheduler — one-step scheduler over the chakana wiring.

A tick walks the canonical root→crown ascent (then the ouroboros closure
back to root), evaluating each chakra against the rolling envelope. Stubbed
kernels are surfaced as `{stubbed: true, error: ...}` — never silently
substituted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import CHAKRA_ORDER
from .chakana_wiring import wiring_snapshot
from .chakras import get_chakra
from .receipts import ReceiptChain


@dataclass
class ChakraStep:
    chakra: str
    output: dict[str, Any] | None
    error: str | None
    stubbed: bool
    receipt_seq: int


@dataclass
class TickResult:
    tick_id: int
    steps: list[ChakraStep] = field(default_factory=list)
    closure: float | None = None
    handoff: dict[str, Any] | None = None


class AmaruScheduler:
    def __init__(self, chain: ReceiptChain) -> None:
        self._chain = chain
        self._tick_count = 0
        self._stub_surfaces: set[str] = set()

    @property
    def tick_count(self) -> int:
        return self._tick_count

    @property
    def stubbed_chakras(self) -> list[str]:
        return sorted(self._stub_surfaces)

    def tick(self, envelope: dict[str, Any] | None = None) -> TickResult:
        self._tick_count += 1
        env: dict[str, Any] = dict(envelope or {})
        env.setdefault("signals", {})
        upstream: dict[str, Any] = {}

        result = TickResult(tick_id=self._tick_count)

        for name in CHAKRA_ORDER:
            entry = get_chakra(name)
            if name == "crown":
                step_env = dict(env)
                step_env["upstream"] = upstream
            else:
                step_env = env
            try:
                output = entry.evaluate(step_env)
                error: str | None = None
            except NotImplementedError as exc:
                output = None
                error = str(exc)
                self._stub_surfaces.add(name)
            except Exception as exc:  # noqa: BLE001
                output = None
                error = f"{type(exc).__name__}: {exc}"

            receipt = self._chain.append(
                endpoint=f"/scheduler/tick/{name}",
                method="POST",
                params={"envelope": step_env},
                result={"output": output, "error": error},
                metadata={
                    "chakra": name,
                    "tick": self._tick_count,
                    "stubbed": entry.stubbed,
                    "proof_id": entry.proof.get("proof_id"),
                },
            )

            if output and isinstance(output, dict):
                for k, v in output.items():
                    if isinstance(v, (int, float)) and k not in {"chakra", "n_upstream_scalars"}:
                        upstream[k] = v

            result.steps.append(
                ChakraStep(
                    chakra=name,
                    output=output,
                    error=error,
                    stubbed=entry.stubbed,
                    receipt_seq=receipt.seq,
                )
            )

            if name == "crown" and output:
                closure = output.get("closure")
                handoff = output.get("handoff")
                if isinstance(closure, (int, float)):
                    result.closure = float(closure)
                if isinstance(handoff, dict):
                    result.handoff = handoff

        return result


def snapshot() -> dict[str, Any]:
    """Return the static wiring snapshot (for `/scheduler/wiring`)."""
    return wiring_snapshot()
