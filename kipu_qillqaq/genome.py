"""QILLQAQ genome — declarative organ config parsed with stdlib `tomllib`.

HONEST NAMING: a "genome" here is a TOML config file describing an organ's identity, the
receipt KINDS it is allowed to read/write on the KIPU substrate, and which Python handler
(module:callable) implements its loop. "Boot from DNA" = parse TOML + import a module.
No biology, no magic. tomllib is the Python 3.11+ standard library TOML parser.

Schema (validated below):
  [organ]   name (str, required), quechua (str), function (str, required)
  [role]    loop (str, required)            -- human description of the organ's loop
  [reads]   kinds (list[str], required)     -- receipt KINDS this organ may read
  [writes]  kinds (list[str], required)     -- receipt KINDS this organ may write
  [boot]    handler (str "module:callable", required), enabled (bool, default true)
  [meta]    any free-form table (optional)
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class GenomeError(ValueError):
    """Raised when a genome.toml fails schema validation."""


@dataclass
class Genome:
    name: str
    quechua: str
    function: str
    loop: str
    reads: list[str]
    writes: list[str]
    handler: str  # "module:callable"
    enabled: bool = True
    meta: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)

    def may_write(self, kind: str) -> bool:
        return kind in self.writes

    def may_read(self, kind: str) -> bool:
        return kind in self.reads


def _require(table: dict, key: str, typ: type, where: str) -> Any:
    if key not in table:
        raise GenomeError(f"[{where}] missing required key '{key}'")
    val = table[key]
    if not isinstance(val, typ):
        raise GenomeError(f"[{where}] key '{key}' must be {typ.__name__}, got {type(val).__name__}")
    return val


def validate_genome(data: dict) -> Genome:
    """Validate a parsed TOML dict against the genome schema. Returns a Genome or raises."""
    if "organ" not in data:
        raise GenomeError("missing [organ] table")
    organ = data["organ"]
    name = _require(organ, "name", str, "organ")
    function = _require(organ, "function", str, "organ")
    quechua = organ.get("quechua", "")

    if "role" not in data:
        raise GenomeError("missing [role] table")
    loop = _require(data["role"], "loop", str, "role")

    if "reads" not in data:
        raise GenomeError("missing [reads] table")
    reads = _require(data["reads"], "kinds", list, "reads")
    if not all(isinstance(x, str) for x in reads):
        raise GenomeError("[reads] kinds must be a list of strings")

    if "writes" not in data:
        raise GenomeError("missing [writes] table")
    writes = _require(data["writes"], "kinds", list, "writes")
    if not all(isinstance(x, str) for x in writes):
        raise GenomeError("[writes] kinds must be a list of strings")

    if "boot" not in data:
        raise GenomeError("missing [boot] table")
    handler = _require(data["boot"], "handler", str, "boot")
    if ":" not in handler:
        raise GenomeError("[boot] handler must be 'module:callable'")
    enabled = bool(data["boot"].get("enabled", True))

    return Genome(
        name=name,
        quechua=quechua,
        function=function,
        loop=loop,
        reads=reads,
        writes=writes,
        handler=handler,
        enabled=enabled,
        meta=data.get("meta", {}),
        raw=data,
    )


def load_genome(path: str | Path) -> Genome:
    """Parse a genome.toml file with tomllib and validate it. Returns a Genome."""
    p = Path(path)
    with open(p, "rb") as f:
        data = tomllib.load(f)
    return validate_genome(data)
