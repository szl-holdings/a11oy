#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

ANCHOR = "# Waqay Security Loop (wave 15): expose only the deterministic, read-only\n"
MARKER = '@app.get("/api/build-info", include_in_schema=False)'

BLOCK = r'''
# Immutable deployment identity. This endpoint is deliberately read-only and
# receipt-free: it exposes only source/build metadata already supplied by the
# canonical deployment workflow. A missing or malformed source revision fails
# closed as UNAVAILABLE rather than inventing provenance.
def _a11oy_build_info_payload() -> tuple[dict[str, object], int]:
    revision = (os.environ.get("SZL_GIT_SHA") or os.environ.get("A11OY_GIT_SHA") or "").strip().lower()
    valid_revision = len(revision) == 40 and all(ch in "0123456789abcdef" for ch in revision)
    payload: dict[str, object] = {
        "build": {
            "state": "OBSERVED" if valid_revision else "UNAVAILABLE",
            "revision": revision if valid_revision else None,
            "version": (os.environ.get("A11OY_VERSION") or "").strip() or None,
            "built_at": (os.environ.get("A11OY_BUILD_DATE") or "").strip() or None,
        },
        "receipt_minted": False,
    }
    return payload, 200 if valid_revision else 503


@app.get("/api/build-info", include_in_schema=False)
async def a11oy_build_info() -> JSONResponse:
    payload, status_code = _a11oy_build_info_payload()
    return JSONResponse(
        payload,
        status_code=status_code,
        headers={
            "Cache-Control": "no-store, max-age=0",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )


'''


def apply(text: str) -> tuple[str, str]:
    if MARKER in text:
        if text.count(MARKER) != 1:
            raise RuntimeError("build-info route marker is duplicated")
        return text, "ALREADY_APPLIED"
    if text.count(ANCHOR) != 1:
        raise RuntimeError(f"expected exactly one insertion anchor; found {text.count(ANCHOR)}")
    return text.replace(ANCHOR, BLOCK + ANCHOR, 1), "APPLIED"


def validate(text: str) -> None:
    required = [
        MARKER,
        'os.environ.get("SZL_GIT_SHA")',
        'os.environ.get("A11OY_GIT_SHA")',
        '"state": "OBSERVED" if valid_revision else "UNAVAILABLE"',
        '"receipt_minted": False',
        '"Cache-Control": "no-store, max-age=0"',
        '200 if valid_revision else 503',
    ]
    missing = [token for token in required if token not in text]
    if missing:
        raise RuntimeError("build-info contract missing: " + ", ".join(missing))
    if text.count(MARKER) != 1:
        raise RuntimeError("build-info route must exist exactly once")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    original = args.path.read_text(encoding="utf-8")
    patched, state = apply(original)
    validate(patched)
    if args.check and state == "APPLIED":
        print(f"build-info route FAIL_UNAPPLIED: {args.path}")
        return 1
    if not args.check:
        args.path.write_text(patched, encoding="utf-8")
    print(f"build-info route {state}: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
