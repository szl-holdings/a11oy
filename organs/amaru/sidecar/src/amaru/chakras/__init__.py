"""
Amaru chakra kernels — one subpackage per chakra (root..crown).

The registry below is loaded once at module import. Each entry resolves a
chakra name to its kernel callable, LEADER.md text, and proof receipt.

If the upstream kernel for a chakra is not vendored locally, `kernel.evaluate`
raises `NotImplementedError("upstream kernel not vendored")`. The runtime
surfaces that loudly — it is never silently substituted with a fake result.
"""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from .. import CHAKRA_ORDER

_HERE = Path(__file__).resolve().parent


@dataclass(frozen=True)
class ChakraEntry:
    name: str
    evaluate: Callable[[Mapping[str, Any]], dict[str, Any]]
    leader_md: str
    proof: dict[str, Any]
    rejected_md: str
    stubbed: bool


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _build_registry() -> dict[str, ChakraEntry]:
    registry: dict[str, ChakraEntry] = {}
    for name in CHAKRA_ORDER:
        sub = _HERE / name
        module = importlib.import_module(f"amaru.chakras.{name}.kernel")
        evaluate = getattr(module, "evaluate")
        stubbed = bool(getattr(module, "STUBBED", False))
        registry[name] = ChakraEntry(
            name=name,
            evaluate=evaluate,
            leader_md=_load_text(sub / "LEADER.md"),
            proof=_load_json(sub / "proof.json"),
            rejected_md=_load_text(sub / "rejected.md"),
            stubbed=stubbed,
        )
    return registry


CHAKRA_REGISTRY: dict[str, ChakraEntry] = _build_registry()


def get_chakra(name: str) -> ChakraEntry:
    entry = CHAKRA_REGISTRY.get(name)
    if entry is None:
        raise KeyError(f"unknown chakra: {name!r}")
    return entry
