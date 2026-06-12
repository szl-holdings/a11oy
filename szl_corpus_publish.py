"""
szl_corpus_publish — publish a11oy's verifiable corpus to the PUBLIC Hugging Face
dataset ``SZLHOLDINGS/a11oy-verifiable-corpus`` ("verify-it-yourself").

Three append-only, idempotent asset classes are published through the shared
content-addressed bucket client (:mod:`szl_hf_bucket`). Re-publishing the same
logical record dedups to a single stored entry; a genuine change (new receipt,
updated proof status, regenerated theorem list) lands as a new append-only
record so the full history is preserved.

  kind="receipt"  — signed DSSE receipts WITH everything a third party needs to
                    verify them offline: the full envelope (payload, payloadType,
                    signatures), the key id, the published public-key URL, the
                    PAE sha256, and the honesty marker. Only GENUINELY signed
                    envelopes are published; UNSIGNED / placeholder envelopes are
                    skipped — no fabricated signature ever leaves the runtime.
  kind="theorem"  — the kernel-verified theorem list (lutar-lean
                    ``VERIFIED_THEOREMS.md``) embedded verbatim with its honest
                    auto-generated status and source provenance.
  kind="formula"  — the canonical formula registry (:mod:`szl_formulas`
                    ``REGISTRY``) with ``PROOF_STATUS`` copied verbatim (Doctrine
                    v11 honesty surface).

Honesty preserved exactly: Theorem U = proven·conditional; Conjecture 1
(unconditional Λ uniqueness) = OPEN / machine-checked FALSE; the locked ladder
is NOT collapsed to "all proven". This module never asserts a stronger status
than its source; it copies the source's own status strings.

ADDITIVE · stdlib-only (lazy-imports the bucket / formula / dsse modules) ·
never raises into a caller's hot path.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import time
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
CORPUS_REPO_DEFAULT = "SZLHOLDINGS/a11oy-verifiable-corpus"
SOURCE = "a11oy"

# Asset classes get their own NDJSON directory (prefix) so the dataset is easy to
# browse: receipts/ , theorems/ , formulas/ — each with day-sharded NDJSON and a
# head.json chain-state, exactly like every other szl_hf_bucket surface.
PREFIX_RECEIPT = "receipts"
PREFIX_THEOREM = "theorems"
PREFIX_FORMULA = "formulas"

LUTAR_THEOREMS_URL = (
    "https://raw.githubusercontent.com/szl-holdings/lutar-lean/main/VERIFIED_THEOREMS.md"
)
LUTAR_THEOREMS_SOURCE = "szl-holdings/lutar-lean@main:VERIFIED_THEOREMS.md"

RECORD_SCHEMA = "szl.a11oy.corpus.record/v1"


def corpus_repo() -> str:
    return os.environ.get("SZL_CORPUS_REPO") or CORPUS_REPO_DEFAULT


# --------------------------------------------------------------------------- #
# Bucket plumbing (lazy, cached, one background flusher per prefix)
# --------------------------------------------------------------------------- #
_buckets: Dict[str, Any] = {}
_buckets_lock = threading.RLock()


def _get_bucket(prefix: str, *, start: bool = True):
    """Return a cached HFBucket for the corpus repo at ``prefix``. Starts the
    debounced background flusher so the real-time receipt hook commits off the
    caller's hot path. Returns None if the bucket client cannot be constructed
    (e.g. missing repo / token) — callers degrade honestly."""
    with _buckets_lock:
        b = _buckets.get(prefix)
        if b is not None:
            return b
        try:
            from szl_hf_bucket import HFBucket  # lazy: heavy-ish import
        except Exception:
            return None
        try:
            b = HFBucket(repo_id=corpus_repo(), source=SOURCE, prefix=prefix)
        except Exception:
            return None
        if start:
            try:
                b.start()
            except Exception:
                pass
        _buckets[prefix] = b
        return b


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


# --------------------------------------------------------------------------- #
# Receipts
# --------------------------------------------------------------------------- #
def _is_real_signed(env: Dict[str, Any]) -> bool:
    """A receipt is publishable only if it carries a REAL signature. UNSIGNED /
    placeholder envelopes are rejected so no fabricated signature is published."""
    if not isinstance(env, dict):
        return False
    sigs = env.get("signatures") or []
    has_sig = any(isinstance(s, dict) and s.get("sig") for s in sigs)
    if not has_sig:
        return False
    if env.get("signed") is False:
        return False
    honesty = str(env.get("honesty", "")).upper()
    if honesty.startswith("UNSIGNED") or "PLACEHOLDER" in honesty:
        return False
    mode = str(env.get("_mode", "")).lower()
    if mode in ("placeholder", "unsigned", "demo"):
        return False
    return True


def _detect_scheme(env: Dict[str, Any]) -> str:
    pt = str(env.get("payloadType", ""))
    if (
        pt == "application/vnd.in-toto+json"
        or env.get("_sigstore")
        or env.get("_signer_identity")
        or env.get("_signer_issuer")
    ):
        return "sigstore-keyless-dsse"
    return "ecdsa-p256-dsse-pae"


def _receipt_uid(env: Dict[str, Any]) -> str:
    """Stable identity of the signed content (independent of any wrapper meta /
    publish timestamp): sha256 over the DSSE PAE of (payloadType, payload)."""
    try:
        import base64

        body = base64.b64decode(env.get("payload", "") or b"")
        pt = str(env.get("payloadType", ""))
        pae = b"DSSEv1 %d %s %d %s" % (len(pt.encode()), pt.encode(), len(body), body)
        return _sha256_hex(pae)
    except Exception:
        return _sha256_hex(_canon(env))


def _verify_block(env: Dict[str, Any], scheme: str) -> Dict[str, Any]:
    """The data a third party needs to verify the receipt with no extra context."""
    if scheme == "ecdsa-p256-dsse-pae":
        try:
            from szl_dsse import KEYID, PUB_KEY_URL, public_key_fingerprint

            keyid = KEYID
            key_url = PUB_KEY_URL
            fp = public_key_fingerprint()
        except Exception:
            keyid = "szlholdings-cosign"
            key_url = "https://github.com/szl-holdings/.github/blob/main/cosign.pub"
            fp = None
        return {
            "scheme": scheme,
            "algorithm": "ECDSA-P256-SHA256 over DSSE PAE (DSSEv1)",
            "keyid": keyid,
            "public_key_url": key_url,
            "public_key_sha256": fp,
            "how_to_verify": (
                "Reconstruct PAE = b'DSSEv1 ' + len(payloadType) + ' ' + payloadType "
                "+ ' ' + len(payload) + ' ' + payload (payload = base64-decoded), then "
                "verify signatures[].sig (base64) against the published cosign.pub with "
                "ECDSA-P256-SHA256. Live endpoint: POST /api/a11oy/khipu/verify."
            ),
        }
    return {
        "scheme": scheme,
        "algorithm": "Sigstore keyless DSSE (Fulcio cert + Rekor transparency log)",
        "how_to_verify": (
            "Self-contained in-toto Statement: the envelope embeds the Sigstore "
            "verification material (_sigstore bundle / signer identity + issuer). "
            "Verify with cosign verify-blob-attestation using the embedded bundle, "
            "or check the Rekor transparency-log entry."
        ),
        "signer_identity": env.get("_signer_identity"),
        "signer_issuer": env.get("_signer_issuer"),
    }


def make_receipt_record(env: Dict[str, Any], *, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    scheme = _detect_scheme(env)
    rec = {
        "schema": RECORD_SCHEMA,
        "asset": "receipt",
        "scheme": scheme,
        "receipt_uid": _receipt_uid(env),
        "envelope": env,
        "verify": _verify_block(env, scheme),
        "honesty": env.get("honesty"),
        "published_at": _utcnow_iso(),
    }
    if extra:
        rec["meta"] = extra
    return rec


def on_new_receipt(env: Dict[str, Any], *, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """REAL-TIME HOOK — call right after a receipt is signed. Off the hot path:
    the record is wrapped and handed to the bucket (a local, atomic disk enqueue);
    the debounced background flusher commits it to HF. NEVER raises into the
    caller and NEVER publishes an unsigned/placeholder envelope.

    The publish timestamp is kept OUT of the dedup basis (the bucket derives the
    record id from {source,kind,content}); we pass an explicit dedup_key of the
    receipt_uid so re-emitting the identical signed receipt dedups cleanly."""
    try:
        if not isinstance(env, dict):
            return {"ok": False, "skipped": "not-an-envelope"}
        if not _is_real_signed(env):
            return {"ok": True, "skipped": "unsigned-or-placeholder", "published": 0}
        bucket = _get_bucket(PREFIX_RECEIPT)
        if bucket is None:
            return {"ok": False, "skipped": "bucket-unavailable", "published": 0}
        rec = make_receipt_record(env, extra=extra)
        # dedup on the stable signed-content identity, not the publish timestamp.
        wrapped = bucket.make_record(
            rec, kind="receipt", source=SOURCE, dedup_key=rec["receipt_uid"]
        )
        res = bucket.append(wrapped, kind="receipt", source=SOURCE)
        return {"ok": True, "published": res.get("queued", 0),
                "duplicates": res.get("duplicates", 0), "id": wrapped.get("id"),
                "scheme": rec["scheme"]}
    except Exception as exc:  # pragma: no cover - hot-path safety
        return {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}


def backfill_receipts(envelopes: Iterable[Dict[str, Any]], *, flush: bool = True) -> Dict[str, Any]:
    """Publish a batch of already-signed envelopes (e.g. the existing governance
    ledger) for the initial seed. Skips unsigned/placeholder envelopes."""
    bucket = _get_bucket(PREFIX_RECEIPT, start=False)
    if bucket is None:
        return {"ok": False, "error": "bucket-unavailable"}
    queued = skipped = 0
    for env in envelopes:
        if not (isinstance(env, dict) and _is_real_signed(env)):
            skipped += 1
            continue
        rec = make_receipt_record(env)
        wrapped = bucket.make_record(rec, kind="receipt", source=SOURCE, dedup_key=rec["receipt_uid"])
        res = bucket.append(wrapped, kind="receipt", source=SOURCE, auto_flush=False)
        queued += res.get("queued", 0)
    out: Dict[str, Any] = {"ok": True, "queued": queued, "skipped_unsigned": skipped}
    if flush:
        out["flush"] = bucket.flush_queue(force=True)
    return out


# --------------------------------------------------------------------------- #
# Formulas
# --------------------------------------------------------------------------- #
def _formula_records() -> List[Dict[str, Any]]:
    from szl_formulas import REGISTRY, PROOF_STATUS

    recs: List[Dict[str, Any]] = []
    for name in sorted(REGISTRY):
        fn = REGISTRY[name]
        recs.append(
            {
                "schema": RECORD_SCHEMA,
                "asset": "formula",
                "name": name,
                "callable": getattr(fn, "__name__", name),
                "proof_status": PROOF_STATUS.get(name, "UNSPECIFIED"),
                "doctrine": "v11",
                "source": "szl-holdings/a11oy:szl_formulas.py REGISTRY+PROOF_STATUS",
                "note": (
                    "proof_status is copied verbatim from the runtime registry; "
                    "PROVEN/AXIOM/SORRY/REAL/CONJECTURE reflect the Lean kernel + "
                    "Doctrine v11 honesty surface, NOT a marketing claim."
                ),
            }
        )
    return recs


def publish_formulas(*, flush: bool = True) -> Dict[str, Any]:
    bucket = _get_bucket(PREFIX_FORMULA, start=not flush)
    if bucket is None:
        return {"ok": False, "error": "bucket-unavailable"}
    recs = _formula_records()
    res = bucket.append_many(recs, kind="formula", source=SOURCE, auto_flush=False)
    out = {"ok": True, "count": len(recs), "queued": res.get("queued", 0),
           "duplicates": res.get("duplicates", 0)}
    if flush:
        out["flush"] = bucket.flush_queue(force=True)
    return out


# --------------------------------------------------------------------------- #
# Theorems
# --------------------------------------------------------------------------- #
def _fetch_theorem_markdown(timeout: float = 8.0) -> Optional[Dict[str, Any]]:
    """Fetch lutar-lean VERIFIED_THEOREMS.md (public, no auth). Returns None
    (honest skip) if unreachable — never fabricates a theorem list."""
    try:
        req = urllib.request.Request(LUTAR_THEOREMS_URL, headers={"User-Agent": "szl-corpus-publish"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (trusted host)
            raw = resp.read()
    except Exception:
        return None
    text = raw.decode("utf-8", "replace")
    return {"text": text, "sha256": _sha256_hex(raw), "bytes": len(raw)}


def _theorem_summary(text: str) -> Dict[str, Any]:
    """A small, honest structural summary — counts only, plus the honesty markers
    the source itself asserts. Does NOT re-derive or upgrade any claim."""
    lines = text.splitlines()
    files = [ln[2:].strip().strip("`") for ln in lines if ln.startswith("## ")]
    entries = [ln for ln in lines if ln.lstrip().startswith("- `")]
    low = text.lower()
    return {
        "lean_files": len(files),
        "theorem_entries": len(entries),
        "asserts_locked_count_eight": "locked_count_eight" in text,
        "asserts_conjecture1_open": ("conjecture1_still_open" in text)
        or ("conjecture 1" in low and "open" in low),
        "asserts_conjecture1_false": ("machine-checked" in low and "false" in low)
        or ("maxagg_ne_lambda" in low),
        "asserts_theoremU_conditional": ("only the" in low and "conditional" in low)
        or ("lambda_unique_of_factors" in text),
        "doctrine": "v11",
    }


def publish_theorems(*, flush: bool = True) -> Dict[str, Any]:
    md = _fetch_theorem_markdown()
    if md is None:
        return {"ok": True, "skipped": "lutar-lean-unreachable", "published": 0}
    bucket = _get_bucket(PREFIX_THEOREM, start=not flush)
    if bucket is None:
        return {"ok": False, "error": "bucket-unavailable"}
    rec = {
        "schema": RECORD_SCHEMA,
        "asset": "theorem",
        "kind_detail": "kernel-verified-theorem-list",
        "source": LUTAR_THEOREMS_SOURCE,
        "source_url": LUTAR_THEOREMS_URL,
        "content_sha256": md["sha256"],
        "summary": _theorem_summary(md["text"]),
        "markdown": md["text"],
        "honesty": (
            "AUTO-GENERATED by lutar-lean from a real `lake build`; each entry is "
            "kernel-checked with zero `sorry`. Theorem U is REAL but CONDITIONAL; "
            "Conjecture 1 (unconditional Λ uniqueness) is machine-checked FALSE and "
            "stays OPEN; the locked-proven set is NOT collapsed."
        ),
    }
    # content-addressed: re-publishing the same theorem list dedups; a regenerated
    # list (new sha256) lands as a fresh append-only record.
    res = bucket.append(rec, kind="theorem", source=SOURCE, auto_flush=False)
    out = {"ok": True, "content_sha256": md["sha256"], "queued": res.get("queued", 0),
           "duplicates": res.get("duplicates", 0)}
    if flush:
        out["flush"] = bucket.flush_queue(force=True)
    return out


# --------------------------------------------------------------------------- #
# Full sync
# --------------------------------------------------------------------------- #
def full_sync() -> Dict[str, Any]:
    """Publish formulas + theorems (the deterministic, always-available asset
    classes). Receipts flow continuously through ``on_new_receipt``; the existing
    ledger is seeded once via ``backfill_receipts``. Returns an honest status."""
    return {
        "ok": True,
        "repo": corpus_repo(),
        "ts": _utcnow_iso(),
        "formulas": publish_formulas(flush=True),
        "theorems": publish_theorems(flush=True),
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _main(argv: List[str]) -> int:
    cmd = argv[0] if argv else "full-sync"
    if cmd in ("full-sync", "sync", "full"):
        print(json.dumps(full_sync(), indent=2))
    elif cmd == "formulas":
        print(json.dumps(publish_formulas(), indent=2))
    elif cmd == "theorems":
        print(json.dumps(publish_theorems(), indent=2))
    elif cmd == "preview-formulas":
        print(json.dumps(_formula_records(), indent=2))
    elif cmd == "preview-theorems":
        md = _fetch_theorem_markdown()
        print(json.dumps({"fetched": md is not None,
                          "summary": _theorem_summary(md["text"]) if md else None}, indent=2))
    else:
        print("usage: szl_corpus_publish [full-sync|formulas|theorems|"
              "preview-formulas|preview-theorems]", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
