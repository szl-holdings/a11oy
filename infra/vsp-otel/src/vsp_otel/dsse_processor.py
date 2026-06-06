# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings — Yachay (CTO) + Perplexity Computer Agent
# Doctrine v11 LOCKED — 749/14/163 · Λ = Conjecture 1
"""DSSE-aware span processor that binds spans into the Khipu receipt chain.

For every span that ends, this processor:

  1. Computes a canonical *receipt* (subject digest) over the span's identity +
     attributes, and stamps ``szl.mesh.receipt_hash`` onto the span.
  2. Wraps that receipt in a **DSSE v1 envelope** (Dead Simple Signing Envelope)
     using the correct **PAE** (Pre-Authentication Encoding), signs the PAE with
     the configured signer, and appends the envelope to the **Khipu chain** —
     an append-only hash-linked ledger (each receipt commits to the previous,
     exactly like Khipu cords).
  3. Stamps the Khipu index/prev onto the span as attributes, and (when present)
     the ``szl.mesh.rekor_log_index`` returned by the transparency-log sink.

DSSE PAE (per the spec, https://github.com/secure-systems-lab/dsse):

    PAE(type, body) = "DSSEv1" SP LEN(type) SP type SP LEN(body) SP body

where SP is a single 0x20 space, LEN is the ASCII-decimal byte length, and
``type`` / ``body`` are UTF-8 / raw bytes. This is what the signature is computed
over — NOT the raw payload — which is what prevents envelope-confusion attacks.

Honest gaps
-----------
* Default signer is a **deterministic HMAC test signer** so the chain is fully
  testable offline. A real ECDSA-P256 / cosign signer is injected in production
  via ``signer=`` (the a11oy mesh already has ``szl_dsse`` for this). When no
  production key is present we keep an HONEST ``UNSIGNED``-grade HMAC marker —
  we never claim a cosign signature we did not make.
* Rekor inclusion is **optional**. If a ``rekor_submit`` callable is supplied we
  record the returned ``log_index``; otherwise the attribute is omitted (we do
  not fabricate a log index).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import threading
from dataclasses import dataclass, field
from typing import Callable, Optional

from . import (
    ATTR_DSSE_PAYLOAD_TYPE,
    ATTR_KHIPU_INDEX,
    ATTR_KHIPU_PREV,
    ATTR_LAMBDA_AXIS,
    ATTR_RECEIPT_HASH,
    ATTR_REKOR_LOG_INDEX,
)

PAYLOAD_TYPE = "application/vnd.szl.khipu-span+json"
GENESIS_PREV = "0" * 64  # genesis link for the Khipu chain


# ---------------------------------------------------------------------------
# DSSE v1 primitives
# ---------------------------------------------------------------------------
def dsse_pae(payload_type: str, payload: bytes) -> bytes:
    """Compute the DSSE v1 Pre-Authentication Encoding (PAE).

    PAE = "DSSEv1" SP LEN(type) SP type SP LEN(body) SP body
    """
    t = payload_type.encode("utf-8")
    return b"DSSEv1 %d %s %d %s" % (len(t), t, len(payload), payload)


def dsse_envelope(payload: bytes, payload_type: str,
                  sign: Callable[[bytes], bytes],
                  keyid: str = "") -> dict:
    """Build a well-formed DSSE v1 envelope.

    The signature is computed over ``PAE(payload_type, payload)``, and the
    payload itself is base64-encoded in the envelope, per the DSSE spec.
    """
    pae = dsse_pae(payload_type, payload)
    sig = sign(pae)
    return {
        "payload": base64.standard_b64encode(payload).decode("ascii"),
        "payloadType": payload_type,
        "signatures": [
            {
                "keyid": keyid,
                "sig": base64.standard_b64encode(sig).decode("ascii"),
            }
        ],
    }


def _default_hmac_signer() -> tuple[Callable[[bytes], bytes], str]:
    """Deterministic HMAC test signer.

    HONEST: this is NOT a cosign/ECDSA signature. It exists so the Khipu chain
    and DSSE envelope are testable offline. Production injects a real signer.
    """
    key = os.environ.get("VSP_OTEL_HMAC_KEY", "vsp-otel-dev-key").encode()
    keyid = "hmac-sha256:" + hashlib.sha256(key).hexdigest()[:16]

    def _sign(data: bytes) -> bytes:
        return hmac.new(key, data, hashlib.sha256).digest()

    return _sign, keyid


# ---------------------------------------------------------------------------
# Khipu receipt + append-only chain
# ---------------------------------------------------------------------------
@dataclass
class KhipuReceipt:
    index: int
    prev: str
    receipt_hash: str
    payload_type: str
    envelope: dict
    rekor_log_index: Optional[int] = None

    @property
    def link(self) -> str:
        """Chain link = sha256(prev || receipt_hash). Hash-links each cord."""
        h = hashlib.sha256()
        h.update(self.prev.encode())
        h.update(self.receipt_hash.encode())
        return h.hexdigest()


class KhipuChain:
    """Append-only, hash-linked ledger of DSSE-bound span receipts."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._receipts: list[KhipuReceipt] = []

    @property
    def head(self) -> str:
        with self._lock:
            return self._receipts[-1].link if self._receipts else GENESIS_PREV

    def __len__(self) -> int:
        return len(self._receipts)

    def append(self, receipt_hash: str, envelope: dict,
               payload_type: str = PAYLOAD_TYPE,
               rekor_log_index: Optional[int] = None) -> KhipuReceipt:
        with self._lock:
            prev = self._receipts[-1].link if self._receipts else GENESIS_PREV
            r = KhipuReceipt(
                index=len(self._receipts),
                prev=prev,
                receipt_hash=receipt_hash,
                payload_type=payload_type,
                envelope=envelope,
                rekor_log_index=rekor_log_index,
            )
            self._receipts.append(r)
            return r

    def receipts(self) -> list[KhipuReceipt]:
        with self._lock:
            return list(self._receipts)

    def verify(self) -> bool:
        """Re-walk the chain and confirm every link is consistent."""
        with self._lock:
            prev = GENESIS_PREV
            for r in self._receipts:
                if r.prev != prev:
                    return False
                prev = r.link
            return True


# ---------------------------------------------------------------------------
# The SpanProcessor
# ---------------------------------------------------------------------------
def _canonical_receipt(span_dict: dict) -> tuple[str, bytes]:
    """Canonical JSON receipt + its sha256 hex digest (the subject digest)."""
    body = json.dumps(span_dict, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(body).hexdigest()
    return digest, body


@dataclass
class DSSEKhipuSpanProcessor:
    """OpenTelemetry ``SpanProcessor`` that DSSE-binds + Khipu-chains spans.

    Implements ``on_start``, ``on_end``, ``shutdown``, ``force_flush``.

    Parameters
    ----------
    chain : KhipuChain
        The receipt chain to append to (shared across the process).
    signer : callable, optional
        ``bytes -> bytes`` signature function over the DSSE PAE. Defaults to a
        deterministic HMAC test signer (HONEST: not a cosign sig).
    keyid : str, optional
        Key identifier recorded in the DSSE envelope.
    rekor_submit : callable, optional
        ``dict(envelope) -> int(log_index)``. If supplied, the returned index is
        stamped as ``szl.mesh.rekor_log_index``. Omitted entirely if absent —
        we never fabricate a transparency-log index.
    """

    chain: KhipuChain
    signer: Optional[Callable[[bytes], bytes]] = None
    keyid: str = ""
    rekor_submit: Optional[Callable[[dict], int]] = None
    _bound: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if self.signer is None:
            self.signer, default_keyid = _default_hmac_signer()
            self.keyid = self.keyid or default_keyid

    # -- OTel SpanProcessor protocol ------------------------------------
    def on_start(self, span, parent_context=None) -> None:  # noqa: D401
        # Stamp the Λ-axis up front so it is present even on dropped spans.
        try:
            span.set_attribute(ATTR_LAMBDA_AXIS, "Conjecture 1")
        except Exception:
            pass

    def _on_ending(self, span) -> None:
        # Newer OTel SDKs invoke _on_ending() while the span is STILL WRITABLE,
        # just before end(). This is the correct place to stamp provenance
        # attributes (a ReadableSpan is immutable by the time on_end() runs).
        # We pre-compute the receipt hash + next khipu index here and stamp them;
        # the actual chain append happens in on_end() so the digest covers the
        # final application attributes.
        try:
            digest, _ = _canonical_receipt(self._span_to_dict(span))
            next_index = len(self.chain)
            span.set_attribute(ATTR_RECEIPT_HASH, digest)
            span.set_attribute(ATTR_KHIPU_INDEX, next_index)
            span.set_attribute(ATTR_KHIPU_PREV, self.chain.head)
            span.set_attribute(ATTR_DSSE_PAYLOAD_TYPE, PAYLOAD_TYPE)
        except Exception:
            pass

    def on_end(self, span) -> None:
        receipt = self.bind(span)
        # Best-effort stamp for SDKs/stubs whose span is still writable here
        # (e.g. the test SpanStub, which has no separate _on_ending phase).
        setter = getattr(span, "set_attribute", None)
        if callable(setter):
            try:
                setter(ATTR_RECEIPT_HASH, receipt.receipt_hash)
                setter(ATTR_KHIPU_INDEX, receipt.index)
                setter(ATTR_KHIPU_PREV, receipt.prev)
                setter(ATTR_DSSE_PAYLOAD_TYPE, receipt.payload_type)
                if receipt.rekor_log_index is not None:
                    setter(ATTR_REKOR_LOG_INDEX, receipt.rekor_log_index)
            except Exception:
                pass

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return True

    # -- core binding logic (also directly unit-testable) ----------------
    def bind(self, span) -> KhipuReceipt:
        """Bind one span into a DSSE envelope + append to the Khipu chain."""
        span_dict = self._span_to_dict(span)
        receipt_hash, body = _canonical_receipt(span_dict)
        env = dsse_envelope(body, PAYLOAD_TYPE, self.signer, self.keyid)

        rekor_idx = None
        if self.rekor_submit is not None:
            try:
                rekor_idx = int(self.rekor_submit(env))
            except Exception:
                rekor_idx = None  # HONEST: no index rather than a fake one

        receipt = self.chain.append(receipt_hash, env,
                                    rekor_log_index=rekor_idx)
        self._bound += 1
        return receipt

    @staticmethod
    def _span_to_dict(span) -> dict:
        """Extract a stable identity+attributes dict from a span.

        Works with both real OpenTelemetry ReadableSpans and the lightweight
        test SpanStub (duck-typed).
        """
        ctx = getattr(span, "context", None) or getattr(
            span, "get_span_context", lambda: None)()
        trace_id = getattr(ctx, "trace_id", None)
        span_id = getattr(ctx, "span_id", None)
        attrs = dict(getattr(span, "attributes", {}) or {})
        # Drop our own provenance attributes to keep the receipt over the
        # *application* span only (avoid self-reference in the digest).
        for k in (ATTR_RECEIPT_HASH, ATTR_KHIPU_INDEX, ATTR_KHIPU_PREV,
                  ATTR_DSSE_PAYLOAD_TYPE, ATTR_REKOR_LOG_INDEX):
            attrs.pop(k, None)
        return {
            "name": getattr(span, "name", None),
            "trace_id": format(trace_id, "032x") if isinstance(trace_id, int) else trace_id,
            "span_id": format(span_id, "016x") if isinstance(span_id, int) else span_id,
            "attributes": attrs,
        }
