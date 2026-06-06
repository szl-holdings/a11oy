# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings — Yachay (CTO) + Perplexity Computer Agent
# Doctrine v11 LOCKED — 749/14/163 · Λ = Conjecture 1
"""DSSE binding tests: envelope is well-formed DSSEv1, PAE is spec-correct,
and the Khipu chain hash-links correctly."""

from __future__ import annotations

import base64
import hashlib
import hmac

from vsp_otel import ATTR_RECEIPT_HASH, ATTR_KHIPU_INDEX
from vsp_otel.dsse_processor import (
    DSSEKhipuSpanProcessor,
    KhipuChain,
    PAYLOAD_TYPE,
    dsse_envelope,
    dsse_pae,
)


# --- Lightweight span stub (duck-typed like an OTel ReadableSpan) ---------
class _Ctx:
    def __init__(self, trace_id, span_id):
        self.trace_id = trace_id
        self.span_id = span_id


class SpanStub:
    def __init__(self, name, trace_id, span_id, attributes=None):
        self.name = name
        self.context = _Ctx(trace_id, span_id)
        self.attributes = dict(attributes or {})

    def set_attribute(self, k, v):
        self.attributes[k] = v


def test_pae_matches_dsse_spec_examples():
    # From the DSSE spec test vectors: type="http://example.com/HelloWorld",
    # body="hello world". PAE = "DSSEv1 29 <type> 11 hello world".
    pae = dsse_pae("http://example.com/HelloWorld", b"hello world")
    assert pae == b"DSSEv1 29 http://example.com/HelloWorld 11 hello world"


def test_envelope_is_well_formed_dssev1():
    payload = b'{"hello":"world"}'
    key = b"k"
    env = dsse_envelope(payload, PAYLOAD_TYPE,
                        lambda d: hmac.new(key, d, hashlib.sha256).digest(),
                        keyid="kid-1")
    # Required DSSE v1 fields.
    assert set(env.keys()) == {"payload", "payloadType", "signatures"}
    assert env["payloadType"] == PAYLOAD_TYPE
    # payload is base64 of the raw payload.
    assert base64.standard_b64decode(env["payload"]) == payload
    # exactly one signature with keyid + base64 sig.
    assert len(env["signatures"]) == 1
    sig = env["signatures"][0]
    assert sig["keyid"] == "kid-1"
    raw_sig = base64.standard_b64decode(sig["sig"])
    # Signature is over the PAE — verify it.
    expected = hmac.new(key, dsse_pae(PAYLOAD_TYPE, payload),
                        hashlib.sha256).digest()
    assert raw_sig == expected


def test_signature_is_over_pae_not_raw_payload():
    payload = b"abc"
    key = b"k"
    env = dsse_envelope(payload, PAYLOAD_TYPE,
                        lambda d: hmac.new(key, d, hashlib.sha256).digest())
    raw_sig = base64.standard_b64decode(env["signatures"][0]["sig"])
    over_raw = hmac.new(key, payload, hashlib.sha256).digest()
    over_pae = hmac.new(key, dsse_pae(PAYLOAD_TYPE, payload),
                        hashlib.sha256).digest()
    assert raw_sig != over_raw          # NOT signed over the raw payload
    assert raw_sig == over_pae          # signed over the PAE (anti-confusion)


def test_processor_binds_span_and_stamps_receipt_hash():
    chain = KhipuChain()
    proc = DSSEKhipuSpanProcessor(chain=chain)
    span = SpanStub("GET /x", trace_id=0x1234, span_id=0xabcd,
                    attributes={"http.method": "GET"})
    proc.on_start(span)
    proc.on_end(span)

    assert len(chain) == 1
    # The span now carries the receipt hash + khipu index.
    assert ATTR_RECEIPT_HASH in span.attributes
    assert span.attributes[ATTR_KHIPU_INDEX] == 0
    r = chain.receipts()[0]
    assert r.receipt_hash == span.attributes[ATTR_RECEIPT_HASH]
    # Envelope on the chain is well-formed.
    assert r.envelope["payloadType"] == PAYLOAD_TYPE


def test_khipu_chain_hash_links_and_verifies():
    chain = KhipuChain()
    proc = DSSEKhipuSpanProcessor(chain=chain)
    for i in range(5):
        proc.on_end(SpanStub(f"op{i}", trace_id=i + 1, span_id=i + 100,
                             attributes={"i": i}))
    receipts = chain.receipts()
    assert len(receipts) == 5
    # Genesis link.
    assert receipts[0].prev == "0" * 64
    # Each receipt's prev == previous receipt's link.
    for a, b in zip(receipts, receipts[1:]):
        assert b.prev == a.link
    assert chain.verify() is True


def test_rekor_index_stamped_when_submit_supplied():
    chain = KhipuChain()
    proc = DSSEKhipuSpanProcessor(chain=chain,
                                  rekor_submit=lambda env: 424242)
    proc.on_end(SpanStub("op", 1, 2, {"a": 1}))
    r = chain.receipts()[0]
    assert r.rekor_log_index == 424242


def test_rekor_index_absent_when_no_submit():
    chain = KhipuChain()
    proc = DSSEKhipuSpanProcessor(chain=chain)  # no rekor_submit
    proc.on_end(SpanStub("op", 1, 2, {"a": 1}))
    assert chain.receipts()[0].rekor_log_index is None  # never fabricated
