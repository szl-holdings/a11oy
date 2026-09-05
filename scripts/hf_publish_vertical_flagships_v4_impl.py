#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Policy overlay for the immutable Domain Experience v4 renderer.

The generated renderer stays byte-identical in the adjacent base module. This
module applies the reviewed Sentra receipt-verifier semantics while preserving
Terra forge 0.2.2, the current Lyte source pin, every non-Sentra vertical, and
the canonical single-writer publisher contract.

Importing this module performs no network or provider mutation.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

BASE_IMPLEMENTATION_PATH = Path(__file__).with_name(
    "_hf_publish_vertical_flagships_v4_impl_base.py"
)
SENTRA_OVERLAY_VERSION = "receipt-verifier/v1"


def _load_base() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "szl_hf_vertical_flagships_v4_base", BASE_IMPLEMENTATION_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load immutable flagship base: {BASE_IMPLEMENTATION_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_BASE = _load_base()
if getattr(_BASE, "TERRA_FORGE_MARKER", None) != 'data-szl-vertical-forge="0.2.2"':
    raise RuntimeError("immutable flagship base is not Terra forge 0.2.2")
if getattr(_BASE, "TERRA_FORGE_GENERATOR", None) != "szl-vertical-forge/0.2.2":
    raise RuntimeError("immutable flagship base has an unexpected Terra generator")

_sentra = {
    "slug": "sentra",
    "title": "Sentra",
    "vertical": "ASSURANCE COMMAND",
    "short": "Public receipt verification and assurance evidence",
    "source": (
        "https://github.com/szl-holdings/a11oy/blob/main/"
        "scripts/hf_publish_vertical_flagships_v4_impl.py"
    ),
    "upstream": (
        "https://szlholdings-a11oy.hf.space/api/a11oy/v1/verify/receipt"
    ),
    "workflow": ("RECEIPT", "SIGNATURE", "DIGEST", "CHAIN", "VERDICT"),
    "lens": "receipt",
    "labels": ("Verifier contract", "Integrity checks", "Evidence verdict"),
}

_rows = tuple(getattr(_BASE, "FLAGSHIPS", ()))
if sum(1 for row in _rows if row.get("slug") == "sentra") != 1:
    raise RuntimeError("immutable flagship base must contain exactly one Sentra row")
_BASE.FLAGSHIPS = tuple(
    _sentra if row.get("slug") == "sentra" else row for row in _rows
)

_BASE.DOMAIN_CSS = dict(getattr(_BASE, "DOMAIN_CSS", {}))
_BASE.DOMAIN_CSS["sentra"] = r''':root{--bg:#030506;--panel:rgba(7,12,15,.92);--muted:#8ca1a8;--accent:#54f0d1;--accent2:#ff5d73}.domain{margin-top:48px;display:grid;grid-template-columns:minmax(0,1fr) minmax(300px,.8fr);gap:14px}.verification{min-height:410px;position:relative;overflow:hidden;background:radial-gradient(circle at 30% 30%,rgba(84,240,209,.08),transparent 35%),linear-gradient(rgba(84,240,209,.045) 1px,transparent 1px),linear-gradient(90deg,rgba(84,240,209,.045) 1px,transparent 1px);background-size:auto,28px 28px,28px 28px}.node{position:absolute;inline-size:74px;block-size:74px;border:1px solid var(--accent);border-radius:50%;display:grid;place-items:center;background:#061014;font:800 9px ui-monospace,monospace;text-align:center}.n1{left:8%;top:18%}.n2{left:42%;top:10%}.n3{right:8%;top:38%;border-color:var(--accent2)}.n4{left:34%;bottom:9%}.path{position:absolute;block-size:1px;background:linear-gradient(90deg,var(--accent),var(--accent2));transform-origin:left center}.x1{left:16%;top:27%;inline-size:31%;transform:rotate(-8deg)}.x2{left:49%;top:20%;inline-size:37%;transform:rotate(25deg)}.x3{left:42%;top:65%;inline-size:42%;transform:rotate(-22deg)}.queue{display:grid;gap:8px}.incident{padding:12px;border:1px solid var(--line);display:grid;grid-template-columns:64px 1fr;gap:10px}.sev{font:900 10px ui-monospace,monospace;color:var(--accent2)}@media(max-width:850px){.domain{grid-template-columns:1fr}}'''

_BASE.DOMAIN_HTML = dict(getattr(_BASE, "DOMAIN_HTML", {}))
_BASE.DOMAIN_HTML["sentra"] = '''<div class="domain"><section class="panel verification" aria-label="Illustrative receipt verification graph"><span class="illus">Illustrative — schematic, not live data</span><span class="path x1"></span><span class="path x2"></span><span class="path x3"></span><div class="node n1">RECEIPT</div><div class="node n2">SIGNATURE</div><div class="node n3">DIGEST</div><div class="node n4">CHAIN</div></section><aside class="panel queue"><span class="illus">Illustrative — schematic, not live data</span><div class="mono">VERIFICATION EVIDENCE QUEUE</div><div class="incident"><span class="sev">CONTRACT</span><span>The live upstream describes the public verifier and its supported checks; it does not claim a receipt verdict.</span></div><div class="incident"><span class="sev">VERDICT</span><span>PASS requires an actual caller-supplied receipt and successful signature, payload-digest, and hash-chain checks.</span></div><div class="incident"><span class="sev">SCOPE</span><span>This read-only surface performs no admission or approval. Immune engine migration remains UNVERIFIED until its contracts and runtime parity are proven.</span></div></aside></div>'''

# Export the complete base API after applying the overlay. Function objects keep
# the base module globals, which are synchronized again before public calls that
# depend on mutable module contracts.
for _name in dir(_BASE):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_BASE, _name)


def _sync_contract() -> None:
    _BASE.FLAGSHIPS = tuple(FLAGSHIPS)
    _BASE.DOMAIN_CSS = dict(DOMAIN_CSS)
    _BASE.DOMAIN_HTML = dict(DOMAIN_HTML)
    _BASE.TERRA_FORGE_BUNDLE = TERRA_FORGE_BUNDLE
    _BASE.TERRA_FORGE_MARKER = TERRA_FORGE_MARKER
    _BASE.TERRA_FORGE_GENERATOR = TERRA_FORGE_GENERATOR
    _BASE.TERRA_FORGE_SOURCE_REPOSITORY = TERRA_FORGE_SOURCE_REPOSITORY


def load_terra_forge_bundle() -> tuple[str, dict[str, Any]]:
    _sync_contract()
    return _BASE.load_terra_forge_bundle()


def html(item: dict[str, Any]) -> str:
    _sync_contract()
    return _BASE.html(item)


def readme(item: dict[str, Any]) -> str:
    _sync_contract()
    return _BASE.readme(item)


def main() -> int:
    _sync_contract()
    return int(_BASE.main())


__all__ = tuple(
    sorted(
        name
        for name in globals()
        if not name.startswith("_")
        and name not in {"Any", "ModuleType", "Path", "importlib"}
    )
)


if __name__ == "__main__":
    raise SystemExit(main())
