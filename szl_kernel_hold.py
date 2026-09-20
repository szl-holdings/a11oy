# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED. Λ = Conjecture 1. Trust ceiling 0.97 is policy.
"""szl_kernel_hold.py — measured compiled-kernel inventory. Refuse empty v1.

Cutoff 2026-09-13 is overdue. A Git ref named v1 with no native load + ABI
is a false close. This module records what is missing. It does not mint
the missing thing.

Stdlib only. Additive register(); never replace existing routes.
"""
from __future__ import annotations

from typing import Any, Mapping

TRUST_CEILING = 0.97
KERNEL_CUTOFF = "2026-09-13"
SCHEMA = "szl.kernel_hold/v1"
CONJECTURE_1 = "Λ uniqueness remains Conjecture 1 — advisory, never a theorem."

# Observed 2026-09-19 by listing branches on each repo. Not LIVE.
KERNELS: tuple[dict[str, Any], ...] = (
    {
        "repo": "szl-holdings/szl-maskmod",
        "main_sha": "06723e5894ad34fa4de9a63188a643808cce8ecc",
        "v1": "missing",
        "present": ("main", "kernel/v0-original"),
    },
    {
        "repo": "szl-holdings/szl-block-kv",
        "main_sha": "7aa9c2483d9f5fb157ec3205985e5a0c0d3dd6e8",
        "v1": "missing",
        "present": ("main", "kernel/v0-original", "kernel-ops-unavailable"),
    },
    {
        "repo": "szl-holdings/szl-receipt-attn",
        "main_sha": "dd0b8c8f08b236cae323a41028e159e63e6b3d3a",
        "v1": "missing",
        "present": ("main", "kernel/v0-original"),
    },
    {
        "repo": "szl-holdings/YARQA-ATTN",
        "main_sha": "bb15b7da92ada2541e5deff0a276a2e51c17f1e2",
        "v1": "missing",
        "present": ("main", "kernel-gpu-unavailable", "kernel-status-import-live"),
    },
)


def refuse_mint_v1(repo: str, *, native_load: bool = False, abi_verified: bool = False) -> dict[str, Any]:
    """Empty v1 is a false close. Native load + ABI are both required."""
    return {
        "repo": repo,
        "mint": False,
        "v1": "missing",
        "honesty": "UNAVAILABLE",
        "reason": (
            "native load + ABI both required"
            if not (native_load and abi_verified)
            else "even a passing load does not auto-mint a Git ref from this module"
        ),
        "native_load": bool(native_load),
        "abi_verified": bool(abi_verified),
    }


def inventory(observed: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """Merge live observations onto the frozen 2026-09-19 snapshot."""
    extra = dict(observed or {})
    rows = []
    missing = []
    for row in KERNELS:
        live = extra.get(row["repo"], {})
        v1 = str(live.get("v1") or row["v1"])
        item = {
            **row,
            "v1": v1,
            "honesty": "UNAVAILABLE" if v1 == "missing" else "SOFTWARE",
        }
        rows.append(item)
        if v1 == "missing":
            missing.append(row["repo"])
    return {
        "schema": SCHEMA,
        "cutoff": KERNEL_CUTOFF,
        "overdue": True,
        "count": len(rows),
        "missing_v1": missing,
        "zero_stays_zero": len(missing) == 0,
        "kernels": rows,
        "all_done": False,
        "agi_claim": False,
        "trust_ceiling": TRUST_CEILING,
        "trust_ceiling_kind": "policy",
        "lambda": "Conjecture 1",
        "note": "Inventory is SOFTWARE. Listing a SHA is not a compiled-kernel load.",
    }


def kernel_status() -> dict[str, Any]:
    inv = inventory()
    return {
        "schema": SCHEMA,
        "honesty": "UNAVAILABLE",
        "v1": "missing",
        "cutoff": KERNEL_CUTOFF,
        "overdue": True,
        "missing_v1_count": len(inv["missing_v1"]),
        "estate_gate": "HOLD",
        "all_done": False,
        "agi_claim": False,
        "conjecture": CONJECTURE_1,
        "inventory": inv,
    }


def register(app: Any, ns: str = "a11oy") -> dict[str, Any]:
    report = {"ok": False, "registered": []}
    try:
        from fastapi.responses import JSONResponse
    except Exception:
        return report

    base = f"/api/{ns}/v1/kernel"

    @app.get(f"{base}/status")
    async def _status():
        return JSONResponse(kernel_status())

    @app.post(f"{base}/refuse-mint")
    async def _refuse(payload: dict[str, Any] | None = None):
        data = payload or {}
        return JSONResponse(
            refuse_mint_v1(
                str(data.get("repo") or ""),
                native_load=bool(data.get("native_load")),
                abi_verified=bool(data.get("abi_verified")),
            )
        )

    report["ok"] = True
    report["registered"] = [f"{base}/status", f"{base}/refuse-mint"]
    return report


if __name__ == "__main__":
    checks = []

    def check(name: str, ok: bool) -> None:
        checks.append((name, ok))
        print(("PASS" if ok else "FAIL"), name)

    inv = inventory()
    check("four_kernels", inv["count"] == 4)
    check("all_missing_v1", len(inv["missing_v1"]) == 4)
    check("not_all_done", inv["all_done"] is False)
    check("not_agi", inv["agi_claim"] is False)
    r = refuse_mint_v1("szl-holdings/szl-maskmod")
    check("refuse_empty_v1", r["mint"] is False and r["v1"] == "missing")
    r2 = refuse_mint_v1("szl-holdings/szl-maskmod", native_load=True, abi_verified=True)
    check("even_load_does_not_mint_ref", r2["mint"] is False)
    s = kernel_status()
    check("status_hold", s["estate_gate"] == "HOLD" and s["overdue"] is True)
    failed = [n for n, ok in checks if not ok]
    print({"ok": not failed, "checks": len(checks), "failed": failed})
    raise SystemExit(1 if failed else 0)
