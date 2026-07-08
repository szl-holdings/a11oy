#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""szl_brainqueryaudit.py — BRAIN QUERY AUDIT: an append-only, hash-linked ledger of
brain queries and the honest verdict each returned, so query accountability is itself
auditable.

WHY THIS EXISTS. The brain-honesty surfaces (grounding / provenance / contradiction /
uncertainty / health / watch) each answer ONE query and return an honest verdict. But
until now nothing kept an accountable record of WHICH queries were asked and WHAT
verdict each got. This surface is that record: a POST appends one
{query, timestamp_utc, returned_verdict, grounding_label} entry and mints an UNSIGNED
SHA-256 receipt that CHAINS to the prior entry's receipt (hash-linked, tamper-evident —
a mini transparency log). A GET returns the current ledger and RECOMPUTES the chain to
report, honestly, whether it is CHAIN-INTACT or CHAIN-BROKEN.

WHAT THIS IS — AND IS NOT (honest by construction, Doctrine v11):
  * It is OBSERVABILITY / ACCOUNTABILITY over the knowledge-graph brain: an audit log.
    It advances NO detection / fusion / effector / targeting / cueing capability.
  * Each receipt is an UNSIGNED-CONTENT-DIGEST: a plain SHA-256 over the entry's content
    plus the prior receipt. It is NOT a signature, NOT a cryptographic proof of anything
    beyond the content digest and its hash-link. Never claimed signed or proven.
  * The ledger is EPHEMERAL (in-memory). It DOES NOT persist across process restart; it
    is labelled accordingly and never presented as durable storage.
  * The surface's own top label is MODELED (a derived audit view, not a measurement).

CHAIN INTEGRITY. Each entry stores its content fields, the prior entry's receipt
(prev_receipt), and its own receipt. To verify, we recompute every receipt from the
stored fields and check (a) each recomputed digest equals the stored receipt and
(b) each entry's prev_receipt equals the prior entry's stored receipt (genesis links to
64 zeros). Any mismatch -> CHAIN-BROKEN, reported honestly with the first broken index.
A tampered field changes its recomputed digest, so tampering is detectable.

RECEIPTS — RECEIPT-ON-WRITE, NOT ON-READ. The GET info/audit reads mint NOTHING and
append NOTHING; they only recompute-and-verify (a pure read). Only the POST record
endpoint appends an entry and mints exactly ONE unsigned SHA-256 receipt.

DOCTRINE v11:
  * Adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22}; it only records/observes.
    Touches no locked formula and no kernel.
  * Λ stays Conjecture 1 (advisory); introduces no theorem, no green/1.0, no proof of Λ.
    Khipu BFT remains Conjecture 2. Trust ceiling 0.97, never 100%.
  * No label is ever upgraded; a CHAIN-BROKEN verdict can never be reported as
    CHAIN-INTACT. A truthful CHAIN-BROKEN beats a fake CHAIN-INTACT.
  * Pure stdlib (+numpy tolerated, not required). Additive routes, registered before the
    SPA catch-all; canonical domain a-11-oy.com; 0 runtime CDN.
"""

import datetime
import hashlib
import json

# Honesty-label vocabulary (doctrine v11). Re-stated here (not imported) so a broken
# import can never silently blank the vocabulary; tests grep these exact strings.
HONEST_LABELS = (
    "LIVE", "MEASURED", "MODELED", "SAMPLE", "SIMULATED", "CACHED", "PROVEN",
    "CONJECTURE", "ROADMAP", "DEGRADED", "REPLAY", "STRUCTURAL-ONLY", "HONEST-STUB",
    "UNSIGNED-LOCAL", "UNAVAILABLE",
)

# This surface's own top label — a derived append-only audit view, not a measurement.
LBL_MODELED = "MODELED"
LBL_UNAVAILABLE = "UNAVAILABLE"

# Chain-integrity verdicts.
CHAIN_INTACT = "CHAIN-INTACT"
CHAIN_BROKEN = "CHAIN-BROKEN"

# Genesis link — the first entry chains from 64 zero hex chars (no prior receipt).
GENESIS_PREV = "0" * 64

# Receipt mode — honest label for an unsigned content digest (never a signature).
RECEIPT_MODE = "UNSIGNED-CONTENT-DIGEST"

TRUST_CEILING = 0.97
LOCKED_SET = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
LOCKED_COUNT = 8
KERNEL_COMMIT = "c7c0ba17"

# This surface's own id (must match szl3d_holographic.SURFACES + holographic.html).
SURFACE_ID = "brainqueryaudit"

# The entry content fields the receipt digest commits to (order-independent — the
# canonical serialization sorts keys — but enumerated here as the audited contract).
_ENTRY_FIELDS = ("seq", "query", "timestamp_utc", "returned_verdict",
                 "grounding_label", "prev_receipt")


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _doctrine_block(note: str = "") -> dict:
    d = {
        "version": "v11",
        "label_top": LBL_MODELED,
        "locked_proven": LOCKED_COUNT,
        "locked_set": list(LOCKED_SET),
        "kernel_commit": KERNEL_COMMIT,
        "adds_to_locked_8": 0,
        "lambda": "Conjecture 1",
        "khipu_bft": "Conjecture 2",
        "trust_ceiling": TRUST_CEILING,
        "trust_100_percent": False,
        "runtime_cdn": 0,
    }
    if note:
        d["note"] = note
    return d


# --------------------------------------------------------------------------- #
# The ephemeral, in-memory, append-only ledger — one per namespace.
# NOT durable: cleared on process restart. Labelled accordingly everywhere.
# --------------------------------------------------------------------------- #
_LEDGERS: dict = {}


def _ledger(ns: str) -> list:
    return _LEDGERS.setdefault(ns, [])


def reset_ledger(ns: str = "a11oy") -> None:
    """Clear a namespace's ledger. Used by tests + honest re-init; the ledger is
    ephemeral by design, so this only makes the in-memory reset explicit."""
    _LEDGERS[ns] = []


# --------------------------------------------------------------------------- #
# Hash-linked receipt — an UNSIGNED SHA-256 content digest over the entry content
# plus the prior receipt. NOT a signature; NOT a proof beyond the content digest.
# --------------------------------------------------------------------------- #

def _entry_digest(*, seq: int, query: str, timestamp_utc: str,
                  returned_verdict: str, grounding_label: str,
                  prev_receipt: str) -> str:
    """Deterministic SHA-256 over the canonical entry content + the prior receipt.

    Committing prev_receipt into each digest is what CHAINS the entries (a tamper to
    any earlier entry changes its receipt, which every later entry commits to). This
    is an unsigned content digest — never a signature, never a proof of anything
    beyond the content and its hash-link."""
    core = {
        "seq": seq,
        "query": query,
        "timestamp_utc": timestamp_utc,
        "returned_verdict": returned_verdict,
        "grounding_label": grounding_label,
        "prev_receipt": prev_receipt,
    }
    canonical = json.dumps(core, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _receipt_block(entry: dict) -> dict:
    """The UNSIGNED SHA-256 receipt object for an appended entry (RECEIPT-ON-WRITE)."""
    return {
        "kind": "szl.brainqueryaudit.entry",
        "algorithm": "sha256",
        "content_sha256": entry["receipt"],
        "chained_from": entry["prev_receipt"],
        "seq": entry["seq"],
        "signed": False,
        "mode": RECEIPT_MODE,
        "receipt_on": "write (POST record)",
        "note": ("unsigned SHA-256 content digest of the audit entry, hash-linked to "
                 "the prior receipt (tamper-evident); RECEIPT-ON-WRITE, never on a GET "
                 "read. No signature fabricated, no proof claimed beyond the digest."),
        "computed_at": _now_iso(),
    }


def _coerce_str(value, default: str) -> str:
    """Store caller input VERBATIM as a string; a missing/blank value becomes an honest
    default (never fabricated — an absent verdict is recorded as UNAVAILABLE, an absent
    query as an empty string)."""
    if isinstance(value, str):
        return value
    if value is None:
        return default
    return str(value)


# --------------------------------------------------------------------------- #
# Append — the ONLY write path. Mints exactly one hash-linked receipt.
# --------------------------------------------------------------------------- #

def append_record(ns: str, *, query, returned_verdict, grounding_label) -> dict:
    """Append one audit entry to the ephemeral ledger and mint its hash-linked receipt.

    Fields are stored VERBATIM (never upgraded). Returns the stored entry dict (which
    includes its own receipt + the prev_receipt it chains from)."""
    ledger = _ledger(ns)
    seq = len(ledger)
    prev_receipt = ledger[-1]["receipt"] if ledger else GENESIS_PREV
    timestamp_utc = _now_iso()
    q = _coerce_str(query, "")
    rv = _coerce_str(returned_verdict, LBL_UNAVAILABLE)
    gl = _coerce_str(grounding_label, LBL_UNAVAILABLE)
    receipt = _entry_digest(
        seq=seq, query=q, timestamp_utc=timestamp_utc,
        returned_verdict=rv, grounding_label=gl, prev_receipt=prev_receipt)
    entry = {
        "seq": seq,
        "query": q,
        "timestamp_utc": timestamp_utc,
        "returned_verdict": rv,
        "grounding_label": gl,
        "prev_receipt": prev_receipt,
        "receipt": receipt,
    }
    ledger.append(entry)
    return entry


# --------------------------------------------------------------------------- #
# Verify — pure recomputation over the stored ledger (mints/appends nothing).
# --------------------------------------------------------------------------- #

def verify_chain(ledger: list) -> dict:
    """Recompute every receipt from the stored fields and check the hash-links.

    Reports CHAIN-INTACT only when EVERY entry's recomputed digest equals its stored
    receipt AND every prev_receipt equals the prior entry's stored receipt (genesis
    links to 64 zeros). Otherwise CHAIN-BROKEN, with the first broken index + reason.
    Pure: recomputes, never mutates the ledger, never mints a receipt."""
    broken: list = []
    expected_prev = GENESIS_PREV
    for i, e in enumerate(ledger):
        stored_prev = e.get("prev_receipt")
        stored_receipt = e.get("receipt")
        recomputed = _entry_digest(
            seq=e.get("seq"),
            query=e.get("query"),
            timestamp_utc=e.get("timestamp_utc"),
            returned_verdict=e.get("returned_verdict"),
            grounding_label=e.get("grounding_label"),
            prev_receipt=stored_prev,
        )
        if stored_prev != expected_prev:
            broken.append({
                "index": i, "seq": e.get("seq"),
                "reason": "prev_receipt does not match the prior entry's receipt "
                          "(hash-link broken)",
                "expected_prev": expected_prev, "stored_prev": stored_prev,
            })
        if recomputed != stored_receipt:
            broken.append({
                "index": i, "seq": e.get("seq"),
                "reason": "recomputed content digest does not match the stored receipt "
                          "(entry content was altered)",
                "recomputed": recomputed, "stored_receipt": stored_receipt,
            })
        # Chain continues from the STORED receipt so a single break is localized and
        # every subsequent link is still checked honestly against what is on record.
        expected_prev = stored_receipt

    verdict = CHAIN_INTACT if not broken else CHAIN_BROKEN
    if verdict == CHAIN_INTACT:
        reason = (f"all {len(ledger)} entry receipt(s) recomputed and hash-links "
                  f"verified" if ledger else "empty ledger — no entries to break")
    else:
        reason = (f"{len(broken)} integrity failure(s); first at index "
                  f"{broken[0]['index']} — reported CHAIN-BROKEN (never softened to "
                  f"CHAIN-INTACT).")
    return {
        "verdict": verdict,
        "verdict_reason": reason,
        "entry_count": len(ledger),
        "broken": broken,
        "first_broken_index": broken[0]["index"] if broken else None,
    }


# --------------------------------------------------------------------------- #
# Handlers.
# --------------------------------------------------------------------------- #

def handle_info(ns: str = "a11oy") -> dict:
    """GET /brain/audit/info — static self-describing manifest (no compute). PURE READ."""
    base = f"/api/{ns}/v1/brain/audit"
    return {
        "ok": True,
        "service": "a11oy.brain.audit",
        "endpoint": "brain/audit/info",
        "surface_id": SURFACE_ID,
        "label": LBL_MODELED,
        "title": "Brain Query Audit — append-only hash-linked ledger of brain queries",
        "what": ("an append-only, hash-linked audit log of brain queries and the honest "
                 "verdict each returned. POST appends {query, timestamp_utc, "
                 "returned_verdict, grounding_label} and mints an UNSIGNED SHA-256 "
                 "receipt chained to the prior entry (tamper-evident). GET returns the "
                 "ledger + a recomputed chain-integrity verdict. Pure accountability / "
                 "observability over the knowledge-graph brain; advances no "
                 "detection/fusion/effector/targeting/cueing capability."),
        "endpoints": {
            "info": f"GET  {base}/info",
            "audit": f"GET  {base}",
            "record": f"POST {base}/record",
        },
        "record_body": {
            "query": "str — the brain query that was asked (stored verbatim)",
            "returned_verdict": "str — the honest verdict the query returned (verbatim)",
            "grounding_label": "str — the honesty label of the grounding (verbatim)",
        },
        "verdicts": [CHAIN_INTACT, CHAIN_BROKEN],
        "verdict_legend": {
            CHAIN_INTACT: ("every entry's receipt recomputes and every hash-link "
                           "verifies"),
            CHAIN_BROKEN: ("at least one receipt failed to recompute or a hash-link "
                           "did not match (never reported as CHAIN-INTACT)"),
        },
        "receipt": {
            "algorithm": "sha256",
            "mode": RECEIPT_MODE,
            "signed": False,
            "note": ("each receipt is an UNSIGNED content digest hash-linked to the "
                     "prior receipt — a mini transparency log. It is NOT a signature "
                     "and NOT a proof of anything beyond the content digest."),
        },
        "persistence": {
            "durable": False,
            "storage": "in-memory (ephemeral)",
            "note": ("the ledger DOES NOT persist across process restart; it is honest "
                     "ephemeral state, never presented as durable storage."),
        },
        "receipt_policy": ("RECEIPT-ON-WRITE-NOT-ON-READ — only POST /record appends an "
                           "entry and mints one unsigned SHA-256 receipt; GET reads mint "
                           "nothing."),
        "honest_labels_vocabulary": list(HONEST_LABELS),
        "doctrine": _doctrine_block(
            "additive append-only audit surface over the knowledge-graph brain; touches "
            "no locked formula and no kernel; Λ = Conjecture 1, never a theorem."),
        "timestamp_utc": _now_iso(),
    }


def _ledger_view(ns: str) -> dict:
    """Build the current ledger + a recomputed chain-integrity verdict. PURE READ."""
    ledger = _ledger(ns)
    integrity = verify_chain(ledger)
    return {
        "ok": True,
        "endpoint": "brain/audit",
        "surface_id": SURFACE_ID,
        "label": LBL_MODELED,
        "ns": ns,
        "verdict": integrity["verdict"],
        "verdict_reason": integrity["verdict_reason"],
        "entry_count": integrity["entry_count"],
        "ledger": [dict(e) for e in ledger],
        "integrity": integrity,
        "persistence": {
            "durable": False,
            "storage": "in-memory (ephemeral)",
            "note": ("ephemeral ledger; does not persist across restart — the entry "
                     "count reflects only this process's lifetime."),
        },
        "receipt_policy": ("RECEIPT-ON-WRITE-NOT-ON-READ — this GET recomputes and "
                           "verifies but mints nothing and appends nothing."),
        "doctrine": _doctrine_block(
            "pure read; Λ = Conjecture 1; adds nothing to the locked-8. Chain integrity "
            "is recomputed, never trusted blindly."),
        "timestamp_utc": _now_iso(),
    }


def handle_audit(ns: str = "a11oy") -> dict:
    """GET /brain/audit — the current ledger + chain-integrity verdict. PURE READ
    (mints nothing, appends nothing). Never 500s: honest degraded response on error."""
    try:
        return _ledger_view(ns)
    except Exception as exc:  # never 500 — honest degraded response
        return {
            "ok": False, "endpoint": "brain/audit", "label": LBL_UNAVAILABLE,
            "surface_id": SURFACE_ID, "verdict": CHAIN_BROKEN, "error": str(exc)[:200],
            "doctrine": "v11: audit unavailable; no fabricated verdict emitted.",
            "timestamp_utc": _now_iso(),
        }


def handle_record(ns: str = "a11oy", body=None) -> dict:
    """POST /brain/audit/record — append one entry + mint its hash-linked UNSIGNED
    SHA-256 receipt (RECEIPT-ON-WRITE). A missing/empty/bogus body still records an
    honest entry (absent fields default to empty query / UNAVAILABLE verdict — never
    fabricated). Never 500s: honest degraded response on error."""
    try:
        b = body if isinstance(body, dict) else {}
        entry = append_record(
            ns,
            query=b.get("query"),
            returned_verdict=b.get("returned_verdict"),
            grounding_label=b.get("grounding_label"),
        )
        integrity = verify_chain(_ledger(ns))
        return {
            "ok": True,
            "endpoint": "brain/audit/record",
            "surface_id": SURFACE_ID,
            "label": LBL_MODELED,
            "ns": ns,
            "appended": dict(entry),
            "receipt": _receipt_block(entry),
            "verdict": integrity["verdict"],
            "verdict_reason": integrity["verdict_reason"],
            "entry_count": integrity["entry_count"],
            "persistence": {
                "durable": False,
                "storage": "in-memory (ephemeral)",
                "note": ("entry appended to the ephemeral in-memory ledger; it does not "
                         "persist across process restart."),
            },
            "receipt_policy": ("RECEIPT-ON-WRITE — this POST minted exactly ONE unsigned "
                               "SHA-256 receipt for the appended entry."),
            "doctrine": _doctrine_block(
                "append-only write; unsigned content digest hash-linked to the prior "
                "receipt; no signature, no proof claimed. Λ = Conjecture 1."),
            "timestamp_utc": _now_iso(),
        }
    except Exception as exc:
        return {
            "ok": False, "endpoint": "brain/audit/record", "label": LBL_UNAVAILABLE,
            "surface_id": SURFACE_ID, "verdict": CHAIN_BROKEN, "error": str(exc)[:200],
            "doctrine": "v11: record unavailable; no entry appended, no receipt minted.",
            "timestamp_utc": _now_iso(),
        }


# --------------------------------------------------------------------------- #
# FastAPI router registration.
#   GET  info/audit — normal FastAPI GET handlers (pure reads; mint nothing).
#   POST record     — raw-Request handler via app.router.add_route (Starlette passes
#                     the Request positionally, version-proof under fastapi==0.137.x),
#                     with app.add_api_route as the fallback. The handler is annotated
#                     request: fastapi.Request. Registered BEFORE the SPA catch-all.
# --------------------------------------------------------------------------- #

def register(app, ns: str = "a11oy") -> str:
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/brain/audit"

    @app.get(f"{base}/info")
    def _brainqueryaudit_info():
        """Self-describing brain-query-audit manifest (pure read; mints nothing)."""
        return JSONResponse(handle_info(ns))

    @app.get(base)
    def _brainqueryaudit_audit():
        """Current ledger + recomputed chain-integrity verdict (pure read; mints nothing)."""
        return JSONResponse(handle_audit(ns))

    async def _brainqueryaudit_record(request):
        """POST: append one query+verdict entry + mint its hash-linked UNSIGNED SHA-256
        receipt (RECEIPT-ON-WRITE). A missing/empty/bogus body records an honest entry
        with defaulted fields — never a fabricated verdict."""
        body = None
        try:
            raw = await request.body()
            if raw:
                body = json.loads(raw)
        except Exception:  # a malformed body still records honestly, never a 500
            body = None
        return JSONResponse(handle_record(ns, body))

    # Annotate the raw-Request handler as fastapi.Request so any FastAPI signature
    # analysis (in the add_api_route fallback path) treats the param as the request
    # object (0.137.x gotcha).
    try:
        import fastapi as _fastapi
        _brainqueryaudit_record.__annotations__["request"] = _fastapi.Request
    except Exception:  # noqa: BLE001 — annotation is best-effort only
        pass

    rec_path = f"{base}/record"
    add_route = getattr(getattr(app, "router", None), "add_route", None)
    add_api_route = getattr(app, "add_api_route", None)
    try:
        if callable(add_route):
            app.router.add_route(rec_path, _brainqueryaudit_record, methods=["POST"])
        elif callable(add_api_route):
            app.add_api_route(rec_path, _brainqueryaudit_record, methods=["POST"])
        else:  # pragma: no cover — last-resort Starlette Route append
            from starlette.routing import Route
            app.router.routes.append(Route(rec_path, _brainqueryaudit_record, methods=["POST"]))
    except Exception as exc:  # additive register must never break boot
        print(f"[{ns}] brainqueryaudit record POST route NOT wired (guarded): {exc!r}",
              file=__import__("sys").stderr)
        return "brainqueryaudit-wired:2(get-only)"

    return "brainqueryaudit-wired:3"


# --------------------------------------------------------------------------- #
# Self-test — honest chain, no fabricated verdict, receipt only on write.
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    import sys as _sys

    print("=" * 72)
    print("szl_brainqueryaudit — self-test (append-only hash-linked query audit)")
    print("=" * 72)

    reset_ledger("selftest")

    # 1) empty ledger is honestly CHAIN-INTACT (nothing to break), 0 entries.
    v0 = _ledger_view("selftest")
    assert v0["entry_count"] == 0 and v0["verdict"] == CHAIN_INTACT
    assert "receipt" not in v0, "GET audit must mint nothing (receipt-on-write)"
    print(f"[1] empty ledger: entry_count=0, verdict={v0['verdict']}, GET mints "
          f"nothing  OK")

    # 2) POST appends + mints exactly one unsigned SHA-256 receipt; chain stays INTACT.
    r1 = handle_record("selftest", {"query": "what proves the estate thesis",
                                    "returned_verdict": "GROUNDED",
                                    "grounding_label": "MODELED"})
    assert r1["ok"] and r1["entry_count"] == 1
    rec = r1["receipt"]
    assert rec["algorithm"] == "sha256" and len(rec["content_sha256"]) == 64
    assert rec["signed"] is False and rec["mode"] == RECEIPT_MODE
    assert r1["appended"]["prev_receipt"] == GENESIS_PREV, "genesis links to 64 zeros"
    r2 = handle_record("selftest", {"query": "list the locked-8 formulas",
                                    "returned_verdict": "TRACEABLE",
                                    "grounding_label": "HARVESTED"})
    assert r2["entry_count"] == 2
    assert r2["appended"]["prev_receipt"] == rec["content_sha256"], "chain links"
    view = _ledger_view("selftest")
    assert view["verdict"] == CHAIN_INTACT, view["verdict"]
    print(f"[2] two appends chain correctly; each mints one unsigned sha256; "
          f"verdict={view['verdict']}  OK")

    # 3) a TAMPERED entry yields CHAIN-BROKEN (never softened to CHAIN-INTACT).
    #    (Λ is Conjecture 1, never a theorem — the honesty posture is unchanged by a
    #    detected tamper; we only report the break truthfully.)
    tampered = [dict(e) for e in _ledger("selftest")]
    tampered[0]["returned_verdict"] = "INSUFFICIENT-GROUNDING"  # alter recorded content
    integ = verify_chain(tampered)
    assert integ["verdict"] == CHAIN_BROKEN, "a tampered entry must be CHAIN-BROKEN"
    assert integ["first_broken_index"] == 0
    print(f"[3] tampered entry => {integ['verdict']} at index "
          f"{integ['first_broken_index']} (never softened)  OK")

    # 4) GET audit is a PURE READ: it recomputes but mints/appends nothing; the real
    #    ledger is still INTACT after a verify over a tampered COPY.
    view2 = _ledger_view("selftest")
    assert view2["entry_count"] == 2, "verify over a copy must not touch the real ledger"
    assert view2["verdict"] == CHAIN_INTACT
    assert "receipt" not in view2, "GET audit must not mint a receipt"
    print(f"[4] GET audit pure-read: real ledger still INTACT, entry_count=2, mints "
          f"nothing  OK")

    # 5) ephemeral honesty + doctrine: locked-8 exact, +0, Λ Conjecture 1, trust 0.97.
    info = handle_info("selftest")
    assert info["persistence"]["durable"] is False
    assert info["receipt"]["signed"] is False and info["receipt"]["mode"] == RECEIPT_MODE
    d = info["doctrine"]
    assert d["locked_proven"] == 8 and d["locked_set"] == LOCKED_SET
    assert d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1" and d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0
    assert LBL_MODELED in HONEST_LABELS
    print("[5] ephemeral labelled honestly; doctrine: locked-8 exact, +0, "
          "Λ=Conjecture 1, trust 0.97 (not 100%)  OK")

    reset_ledger("selftest")
    print("\nok:true checks:5")
    _sys.exit(0)
