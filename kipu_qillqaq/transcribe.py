"""QILLQAQ transcription engine — boot OrganAgents from declarative genome.toml files.

HONEST NAMING: "transcription" = read TOML config, import a handler module, instantiate an
agent. "boot from DNA" = config-driven module loading (like a plugin registry or a
Kubernetes operator reconciling a CRD). No biology.

An OrganAgent:
  * holds its Genome (the validated config),
  * is bound to a shared KipuPool,
  * exposes write()/read() that are GATED by the genome's allowed receipt kinds,
  * runs its handler (a module:callable) when stepped, if one resolves.

If a handler module cannot be imported (e.g. the organ's real code isn't present), the
agent still boots in "declared" mode: it can read/write receipts but has no step logic.
This keeps the engine usable as pure substrate wiring without every organ's code on path.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Callable, Optional

from .genome import Genome, load_genome, GenomeError
from .pool import KipuPool
from .cell import ReceiptCell


class OrganAgent:
    def __init__(self, genome: Genome, pool: KipuPool):
        self.genome = genome
        self.pool = pool
        self.handler: Optional[Callable] = None
        self.handler_status = "unbound"
        self._resolve_handler()

    def _resolve_handler(self) -> None:
        mod_name, _, attr = self.genome.handler.partition(":")
        try:
            mod = importlib.import_module(mod_name)
            self.handler = getattr(mod, attr)
            self.handler_status = "bound"
        except Exception as e:
            self.handler = None
            self.handler_status = f"declared (handler import failed: {type(e).__name__})"

    def write(self, kind: str, payload: dict, parents: tuple = ()) -> str:
        if not self.genome.may_write(kind):
            raise PermissionError(
                f"organ '{self.genome.name}' genome does not authorize writing kind '{kind}' "
                f"(allowed: {self.genome.writes})"
            )
        cell = ReceiptCell(organ=self.genome.name, kind=kind, payload=payload, parents=parents)
        return self.pool.write(cell)

    def read(self, cid: str) -> Optional[ReceiptCell]:
        cell = self.pool.read(cid, reader=self.genome.name)
        if cell is not None and not self.genome.may_read(cell.kind):
            raise PermissionError(
                f"organ '{self.genome.name}' genome does not authorize reading kind '{cell.kind}' "
                f"(allowed: {self.genome.reads})"
            )
        return cell

    def step(self, *args, **kwargs):
        """Invoke the bound handler if present. Handler signature: handler(agent, *a, **k)."""
        if self.handler is None:
            return None
        return self.handler(self, *args, **kwargs)

    def info(self) -> dict:
        return {
            "name": self.genome.name,
            "quechua": self.genome.quechua,
            "function": self.genome.function,
            "reads": self.genome.reads,
            "writes": self.genome.writes,
            "handler": self.genome.handler,
            "handler_status": self.handler_status,
            "enabled": self.genome.enabled,
        }


class QillqaqEngine:
    """Reads a directory of genome.toml files and boots an OrganAgent for each."""

    def __init__(self, pool: Optional[KipuPool] = None):
        self.pool = pool or KipuPool()
        self.agents: dict[str, OrganAgent] = {}
        self.errors: dict[str, str] = {}

    def boot_file(self, path: str | Path) -> Optional[OrganAgent]:
        try:
            genome = load_genome(path)
        except GenomeError as e:
            self.errors[str(path)] = str(e)
            return None
        if not genome.enabled:
            return None
        agent = OrganAgent(genome, self.pool)
        self.agents[genome.name] = agent
        return agent

    def boot_dir(self, directory: str | Path, pattern: str = "*.toml") -> dict[str, OrganAgent]:
        """Boot every genome file in a directory. Returns {organ_name: agent}."""
        d = Path(directory)
        for f in sorted(d.glob(pattern)):
            self.boot_file(f)
        return self.agents

    def boot_packaged(self) -> dict[str, OrganAgent]:
        """Boot the genome.toml files bundled inside the installed package."""
        here = Path(__file__).parent / "genomes"
        return self.boot_dir(here)

    def manifest(self) -> dict:
        return {
            "engine": "QILLQAQ",
            "pool": self.pool.stats(),
            "organs": {name: a.info() for name, a in self.agents.items()},
            "errors": self.errors,
            "count": len(self.agents),
        }
