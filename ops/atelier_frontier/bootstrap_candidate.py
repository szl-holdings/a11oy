#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Materialize and integrate the bounded Atelier Frontier candidate."""
from __future__ import annotations

import base64
import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path

PAYLOAD_PARTS = 8
EXPECTED = {'.github/workflows/atelier-frontier.yml': '7f1ff44377a7e89f31e403a65a53dea4d02598c395ac55b61eef956e0e1dc478', 'docs/third-party/meta-success-intake-v1.md': 'f2854cd181aecb3a00cd3a086499a0936e7a9c07165fb467763578788a836cba', 'routers/atelier_frontier.py': '9ef4a66e725fa3854b0be5a1be85617df58eda9b9300ea596d2aa1ee8d28d7b7', 'routers/atelier_frontier_web/app.js': 'ab2050f533f63323acd9fb894fdc94a08288b030bd2a94857cefebf828ed02e6', 'routers/atelier_frontier_web/index.html': '8af3f9819dad4a0548fb45966f39388c3118671148059aec6bbc262ae4fee211', 'routers/atelier_frontier_web/styles.css': '4e5bca5fedca019bdb3efad8672d5014186612ee4f058eb1021631c04be55e5d', 'tests/test_atelier_frontier.py': '6c85e14ce49da880e063166bb4c5ebf6b67bc644c8633e4260597cba1935caf0'}


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one integration anchor, found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def materialize(root: Path) -> None:
    payload_dir = root / "ops" / "atelier_frontier" / "payload"
    encoded = "".join(
        (payload_dir / f"part-{index:02d}.txt").read_text(encoding="ascii")
        for index in range(PAYLOAD_PARTS)
    )
    archive = gzip.decompress(base64.b64decode(encoded, validate=True))
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as bundle:
        members = bundle.getmembers()
        for member in members:
            if not member.isfile():
                raise SystemExit(f"payload member is not a regular file: {member.name}")
            destination = (root / member.name).resolve()
            if root.resolve() not in destination.parents:
                raise SystemExit(f"payload path escapes repository: {member.name}")
        bundle.extractall(root, filter="data")

    actual = {
        rel: hashlib.sha256((root / rel).read_bytes()).hexdigest()
        for rel in EXPECTED
    }
    if actual != EXPECTED:
        raise SystemExit("materialized payload digest mismatch")


def integrate(root: Path) -> None:
    init = root / "routers" / "__init__.py"
    reads = root / "routers" / "frontier_reads.py"
    atelier = root / "pages" / "atelier.html"

    replace_once(
        init,
        "`frontier_now_control_plane` is an additive GET/HEAD-only projection over that\n"
        "existing Series-A seam. It intentionally owns no database, signer, credentials,\n"
        "scheduler, passport authority, or effectors.\n",
        "`frontier_now_control_plane` is an additive GET/HEAD-only projection over that\n"
        "existing Series-A seam. It intentionally owns no database, signer, credentials,\n"
        "scheduler, passport authority, or effectors.\n\n"
        "`atelier_frontier` is the GET/HEAD-only clean-room reference intake and MODELED\n"
        "candidate evaluator. It copies no third-party source or identity and binds no\n"
        "signer, credential, persistence layer, scheduler, or effector.\n",
    )
    replace_once(
        init,
        '    "frontier_now_control_plane",\n    "series_a_control_plane",',
        '    "frontier_now_control_plane",\n    "atelier_frontier",\n    "series_a_control_plane",',
    )

    replace_once(
        reads,
        "Now is a read-only projection over that controller: no second store, signer,\n"
        "credential, scheduler, passport authority, or effector.\n",
        "Now is a read-only projection over that controller: no second store, signer,\n"
        "credential, scheduler, passport authority, or effector. Atelier Frontier shares\n"
        "this pre-catch-all seam as a clean-room, GET/HEAD-only reference registry and\n"
        "MODELED evaluator; it has no provider write authority or effectors.\n",
    )
    anchor = """    try:
        from routers import frontier_now_control_plane as _frontier_now

        frontier_now = _frontier_now.register(app, ns="a11oy")
    except Exception as exc:  # one read projection must never take down A11oy
        frontier_now = {
            "ok": False,
            "state": "UNAVAILABLE",
            "reason": type(exc).__name__,
            "effectors": [],
        }

    return {
"""
    replacement = """    try:
        from routers import frontier_now_control_plane as _frontier_now

        frontier_now = _frontier_now.register(app, ns="a11oy")
    except Exception as exc:  # one read projection must never take down A11oy
        frontier_now = {
            "ok": False,
            "state": "UNAVAILABLE",
            "reason": type(exc).__name__,
            "effectors": [],
        }

    try:
        from routers import atelier_frontier as _atelier_frontier

        atelier_frontier = _atelier_frontier.register(app, ns="a11oy")
    except Exception as exc:  # reference intake must never take down A11oy
        atelier_frontier = {
            "ok": False,
            "state": "UNAVAILABLE",
            "reason": type(exc).__name__,
            "effectors": [],
        }

    return {
"""
    replace_once(reads, anchor, replacement)
    replace_once(
        reads,
        '        "frontier_now": frontier_now,\n        "routes": [',
        '        "frontier_now": frontier_now,\n        "atelier_frontier": atelier_frontier,\n        "routes": [',
    )
    replace_once(
        reads,
        '            "/api/a11oy/v1/frontier-now/inventory",\n        ],',
        '            "/api/a11oy/v1/frontier-now/inventory",\n'
        '            "/atelier/frontier",\n'
        '            "/api/a11oy/v1/atelier/frontier/registry",\n'
        '            "/api/a11oy/v1/atelier/frontier/evaluate",\n'
        '        ],',
    )

    replace_once(
        atelier,
        "nav { display: grid; grid-template-columns: repeat(5, 1fr); border-top: 1px solid var(--line); }",
        "nav { display: grid; grid-template-columns: repeat(6, 1fr); border-top: 1px solid var(--line); }",
    )
    replace_once(
        atelier,
        '        <a href="#/forge" data-nav="forge">Forge</a>\n',
        '        <a href="#/forge" data-nav="forge">Forge</a>\n'
        '        <a href="/atelier/frontier">Frontier</a>\n',
    )


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    materialize(root)
    integrate(root)
    report = {
        "schema": "szl.atelier-frontier-bootstrap/v1",
        "files": EXPECTED,
        "source_copy_used": False,
        "external_writes": "DISABLED_BY_RUNTIME_SURFACE",
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
