"""Helper to declare a chakra whose upstream kernel is not vendored locally."""

from __future__ import annotations

from typing import Any, Mapping


def make_stub(name: str):
    STUBBED = True

    def evaluate(envelope: Mapping[str, Any]) -> dict[str, Any]:
        raise NotImplementedError(
            f"upstream kernel not vendored (chakra={name!r}). "
            "Vendor the upstream Amaru bundle to enable real evaluation."
        )

    return STUBBED, evaluate
