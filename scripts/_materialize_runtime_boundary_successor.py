#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Materialize the clean current-main successor to the reviewed #1994 fixes."""
from __future__ import annotations

import hashlib
import json
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor, observed {count}")
    return text.replace(old, new, 1)


def patch_immune() -> None:
    path = ROOT / "szl_immune.py"
    text = path.read_text(encoding="utf-8")
    start = text.index("def _field(")
    end = text.index("\n\n# ---------------------------------------------------------------------------\n# Registration", start)
    block = text[start:end]

    if "    primary_status = status\n" not in block:
        block = replace_once(
            block,
            (
                "    status, data, err = probe(field_url)\n"
                "    body = data if isinstance(data, dict) else {}\n"
                "    reachable = status == 200 and isinstance(data, dict)\n"
                "    fallback_state = False\n"
            ),
            (
                "    status, data, err = probe(field_url)\n"
                "    primary_status = status\n"
                "    primary_error = err\n"
                "    body = data if isinstance(data, dict) else {}\n"
                "    reachable = status == 200 and isinstance(data, dict)\n"
                "    fallback_state = False\n"
            ),
            "field primary-probe attribution",
        )

    if '        "fallback_from": (' not in block:
        block = replace_once(
            block,
            (
                '        "upstream_http": status,\n'
                '        "error": None if reachable else (err or "field unobserved"),\n'
                '        "channel": "B",\n'
                '        "space": "SZLHOLDINGS/immune-lattice",\n'
                '        "contract": "/api/immune/state" if fallback_state else "/api/field",\n'
            ),
            (
                '        "upstream_http": status,\n'
                '        "error": None if reachable else (err or "field unobserved"),\n'
                '        "fallback_from": (\n'
                '            {\n'
                '                "channel": "B",\n'
                '                "space": "SZLHOLDINGS/immune-lattice",\n'
                '                "contract": "/api/field",\n'
                '                "url": field_url,\n'
                '                "upstream_http": primary_status,\n'
                '                "error": primary_error or "field unobserved",\n'
                '            }\n'
                '            if fallback_state\n'
                '            else None\n'
                '        ),\n'
                '        "channel": "A" if fallback_state else "B",\n'
                '        "space": "SZLHOLDINGS/immune" if fallback_state else "SZLHOLDINGS/immune-lattice",\n'
                '        "contract": "/api/immune/state" if fallback_state else "/api/field",\n'
            ),
            "field fallback-source attribution",
        )

    path.write_text(text[:start] + block + text[end:], encoding="utf-8")


def write_fallback_tests() -> None:
    content = textwrap.dedent(
        '''\
        # SPDX-License-Identifier: Apache-2.0
        """Regression coverage for IMMUNE Field fallback source attribution."""
        from __future__ import annotations

        import szl_immune as immune


        def _clear_cache() -> None:
            immune._FIELD_CACHE.clear()


        def test_primary_field_response_stays_channel_b() -> None:
            _clear_cache()

            def probe(url: str):
                assert url.endswith("/api/field")
                return 200, {
                    "lambda_status": "Conjecture 1 (NOT a theorem)",
                    "actuation": "SIMULATED",
                    "rule": "observe only",
                    "cells": [],
                    "hunts": [],
                }, None

            result = immune._field(now=10_000.0, probe=probe)
            assert result["channel"] == "B"
            assert result["space"] == "SZLHOLDINGS/immune-lattice"
            assert result["contract"] == "/api/field"
            assert result["fallback_from"] is None
            _clear_cache()


        def test_fallback_reports_channel_a_and_preserves_primary_failure() -> None:
            _clear_cache()
            calls: list[str] = []

            def probe(url: str):
                calls.append(url)
                if url.endswith("/api/field"):
                    return 503, None, "field overlay unavailable"
                assert url.endswith("/api/immune/state")
                return 200, {
                    "estate": [
                        {"id": "cell-1", "title": "Observed cell", "role": "sensor"}
                    ],
                    "ledger": {"count": 7},
                    "readiness": "OBSERVED",
                    "mesh": "DEGRADED",
                }, None

            result = immune._field(now=20_000.0, probe=probe)
            assert len(calls) == 2
            assert result["ok"] is True
            assert result["channel"] == "A"
            assert result["space"] == "SZLHOLDINGS/immune"
            assert result["contract"] == "/api/immune/state"
            assert result["url"].endswith("/api/immune/state")
            assert result["cell_count"] == 1
            assert result["ledger"] == {"count": 7}
            assert result["fallback_from"] == {
                "channel": "B",
                "space": "SZLHOLDINGS/immune-lattice",
                "contract": "/api/field",
                "url": calls[0],
                "upstream_http": 503,
                "error": "field overlay unavailable",
            }
            _clear_cache()
        '''
    )
    (ROOT / "tests/test_runtime_boundary_fallback_attribution.py").write_text(
        content,
        encoding="utf-8",
    )


def write_manifest() -> str:
    files = {
        relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        for relative in ("szl_agentic_loop.py", "szl_immune.py")
    }
    manifest = {
        "files": dict(sorted(files.items())),
        "payload_id": "runtime-boundary-1994-v2",
        "schema": "szl-shared-source-payload/v1",
    }
    raw = (json.dumps(manifest, separators=(",", ":"), ensure_ascii=True) + "\n").encode()
    path = ROOT / ".github/shared-source-payload-manifest.json"
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def update_audit(manifest_sha256: str) -> None:
    path = ROOT / "audit/POST_MERGE_1986_REVIEW_REPAIR_2026-09-05.md"
    text = path.read_text(encoding="utf-8")
    marker = "## Current-main successor reconciliation\n"
    if marker not in text:
        text += textwrap.dedent(
            f'''\

            ## Current-main successor reconciliation

            The reviewed functional changes were rematerialized onto current protected
            `main` without the temporary repair workflows or the `sitecustomize.py`
            collection shim from superseded PR #1994. The IMMUNE Field compatibility
            fallback now reports the actual Channel A source while retaining the failed
            Channel B probe as bounded evidence. The coordinated shared-source manifest
            is `sha256:{manifest_sha256}` and is verified reciprocally with Killinchu.
            '''
        )
        path.write_text(text, encoding="utf-8")


def main() -> int:
    required = [
        ROOT / "src/pages/Ouroboros.tsx",
        ROOT / "szl_agentic_loop.py",
        ROOT / "szl_immune.py",
        ROOT / "tests/test_post_merge_1986_review_repairs.py",
        ROOT / "audit/POST_MERGE_1986_REVIEW_REPAIR_2026-09-05.md",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        raise SystemExit(f"missing reviewed source files: {missing}")
    patch_immune()
    write_fallback_tests()
    manifest_sha256 = write_manifest()
    update_audit(manifest_sha256)
    print(f"shared_manifest_sha256={manifest_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
