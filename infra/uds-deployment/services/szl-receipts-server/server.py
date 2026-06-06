#!/usr/bin/env python3
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# SZL Receipts server.
#
# Extracted from charts/szl-receipts/templates/configmap.yaml (inline source)
# and refactored for v0.3.1 per PhD Systems Scope 6 (durability) and PhD Crypto
# Finding A2 (signature scheme) + Finding A1 (canonical DSSE PAE).
#
# HTTP surface (unchanged from the ConfigMap build, with additions noted):
#   POST /receipt    — accept a receipt body, sign it, append it to the chain
#   GET  /receipts   — return all stored receipts as JSON
#   GET  /stream     — SSE stream of new receipts for the dashboard
#   GET  /health     — readiness/liveness probe (preserved)
#   GET  /healthz    — readiness/liveness probe (alias; matches Dockerfile HEALTHCHECK)
#   GET  /metrics    — Prometheus-compatible counters (preserved)
#
# Changes in v0.3.1:
#   1. Receipts are signed with Ed25519 (cryptography.hazmat) instead of
#      HMAC-SHA-256. The private key is loaded from a PEM file
#      (SZL_ED25519_KEY_PATH, default /run/secrets/szl-receipts/ed25519.pem).
#      The signature is a base64url-encoded 64-byte Ed25519 signature placed in
#      the DSSE envelope's signatures[].sig, with a stable keyid.
#   2. The signature is computed over the canonical DSSE PAE:
#         "DSSEv1" SP LEN(type) SP type SP LEN(body) SP body
#      where SP = 0x20 and LEN is ASCII decimal. (PhD_CRYPTO_VERDICT Finding A1.)
#   3. Each receipt carries a chain block {prev_hash, hash, chain_index} and a
#      created_at timestamp. On startup the server walks STORE_PATH, rehydrates
#      the in-memory _receipts list ordered by created_at, and reconstructs the
#      chain pointers by reading each JSON's chain.prev_hash. It logs the count.
#   4. A boot OTel span (szl_receipts.boot) is emitted on startup and a per-POST
#      span (szl_receipts.append) is emitted on each receipt, exported via OTLP
#      gRPC when OTEL_EXPORTER_OTLP_ENDPOINT is set (default unset = no export).
#
# Honest labeling: this is an Ed25519 software-key signer. The private key lives
# in a Kubernetes Secret mounted at SZL_ED25519_KEY_PATH. Production HSM/KMS key
# custody is roadmap, not implemented here (see PhD_CRYPTO_VERDICT section I and
# the HSM-in-prod note referenced at pqc.ts:327).

import os
import json
import time
import base64
import hashlib
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# ── Configuration ─────────────────────────────────────────────────────────────

PORT       = int(os.environ.get("SZL_PORT", 8080))
STORE_PATH = os.environ.get("SZL_RECEIPT_STORE", "/data/receipts")
LOG_LEVEL  = os.environ.get("SZL_LOG_LEVEL", "info")

# Ed25519 private key (PEM, PKCS#8 or OpenSSH-unencrypted) mounted from a Secret.
ED25519_KEY_PATH = os.environ.get(
    "SZL_ED25519_KEY_PATH", "/run/secrets/szl-receipts/ed25519.pem"
)
# Stable identifier for the signing key, surfaced in DSSE signatures[].keyid.
KEY_ID = os.environ.get("SZL_KEY_ID", "szl-receipts-ed25519-2026")

# DSSE payloadType for SZL governance receipts.
PAYLOAD_TYPE = "application/vnd.szl.receipt.v1+json"

# Genesis sentinel for the first receipt's prev_hash.
GENESIS = "GENESIS"

os.makedirs(STORE_PATH, exist_ok=True)

_receipts      = []
_receipt_lock  = threading.Lock()
_sse_clients   = []
_client_lock   = threading.Lock()
_counter_total = 0
_counter_valid = 0
_chain_head    = GENESIS   # hash of the most recent receipt, or GENESIS
_chain_index   = 0         # next chain index to assign

_private_key   = None      # Ed25519PrivateKey or None (unsigned/demo)
_public_key_b64 = None     # base64url raw public key, for diagnostics


def log(level, msg):
    if LOG_LEVEL == "debug" or level in ("info", "warn", "error"):
        print(f"[{level.upper()}] {time.strftime('%Y-%m-%dT%H:%M:%SZ')} {msg}", flush=True)


# ── base64url helpers (no padding, per JOSE/DSSE convention) ───────────────────

def b64u_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def b64u_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


# ── Ed25519 key loading + signing ──────────────────────────────────────────────

def _load_private_key():
    """Load the Ed25519 private key from PEM. Returns the key or None.

    If the key file is absent, the server runs in unsigned mode: it still
    accepts and chains receipts but cannot produce Ed25519 signatures. This is
    a degraded mode (honest), not a fake signature."""
    global _public_key_b64
    try:
        from cryptography.hazmat.primitives.serialization import (
            load_pem_private_key,
        )
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
        )
    except Exception as e:  # cryptography missing
        log("warn", f"cryptography unavailable, running unsigned: {e}")
        return None

    if not os.path.exists(ED25519_KEY_PATH):
        log("warn",
            f"Ed25519 key not found at {ED25519_KEY_PATH}; running unsigned "
            f"(operator must provision the szl-receipts-ed25519 secret)")
        return None

    try:
        with open(ED25519_KEY_PATH, "rb") as f:
            pem = f.read()
        key = load_pem_private_key(pem, password=None)
        if not isinstance(key, Ed25519PrivateKey):
            log("error", "loaded key is not Ed25519; running unsigned")
            return None
        from cryptography.hazmat.primitives.serialization import (
            Encoding, PublicFormat,
        )
        raw_pub = key.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw
        )
        _public_key_b64 = b64u_encode(raw_pub)
        log("info", f"Ed25519 signing key loaded; keyid={KEY_ID} pub={_public_key_b64}")
        return key
    except Exception as e:
        log("error", f"failed to load Ed25519 key, running unsigned: {e}")
        return None


def dsse_pae(payload_type: str, body: bytes) -> bytes:
    """Canonical DSSE Pre-Authentication Encoding (DSSEv1).

    PAE = "DSSEv1" SP LEN(type) SP type SP LEN(body) SP body
    where SP = 0x20 (single space) and LEN is the ASCII-decimal byte length.
    Ref: github.com/secure-systems-lab/dsse/protocol.md
         PhD_CRYPTO_VERDICT.md Finding A1."""
    type_bytes = payload_type.encode("utf-8")
    return b" ".join([
        b"DSSEv1",
        str(len(type_bytes)).encode("ascii"),
        type_bytes,
        str(len(body)).encode("ascii"),
        body,
    ])


def sign_dsse(payload_bytes: bytes):
    """Return a DSSE envelope dict signing payload_bytes with Ed25519.

    The signature is over PAE(PAYLOAD_TYPE, payload_bytes). The 64-byte
    Ed25519 signature is base64url-encoded into signatures[].sig. If no private
    key is loaded, sig is an explicit unsigned sentinel (honest, not a forgery)."""
    payload_b64 = base64.b64encode(payload_bytes).decode("ascii")
    pae = dsse_pae(PAYLOAD_TYPE, payload_bytes)
    if _private_key is not None:
        raw_sig = _private_key.sign(pae)  # 64 bytes for Ed25519
        sig_b64u = b64u_encode(raw_sig)
        keyid = KEY_ID
    else:
        sig_b64u = "UNSIGNED-NO-ED25519-KEY"
        keyid = f"{KEY_ID}#unsigned"
    return {
        "payload": payload_b64,
        "payloadType": PAYLOAD_TYPE,
        "signatures": [{"keyid": keyid, "sig": sig_b64u}],
    }


def verify_dsse(envelope: dict) -> bool:
    """Verify the Ed25519 signature on a DSSE envelope against the loaded key.

    Returns False in unsigned mode or if verification fails. Verification is
    over the canonical PAE, matching sign_dsse."""
    if _private_key is None:
        return False
    try:
        payload_b64 = envelope.get("payload", "")
        sigs = envelope.get("signatures", [])
        payload_type = envelope.get("payloadType", PAYLOAD_TYPE)
        if not sigs:
            return False
        sig_b64u = sigs[0].get("sig", "")
        if not sig_b64u or sig_b64u.startswith("UNSIGNED"):
            return False
        body = base64.b64decode(payload_b64)
        pae = dsse_pae(payload_type, body)
        raw_sig = b64u_decode(sig_b64u)
        _private_key.public_key().verify(raw_sig, pae)
        return True
    except Exception as e:
        log("debug", f"DSSE verify failed: {e}")
        return False


# ── OpenTelemetry (optional; exported only when endpoint is set) ───────────────

_tracer = None


def _init_tracer():
    """Initialize an OTLP/gRPC tracer if OTEL_EXPORTER_OTLP_ENDPOINT is set.

    Returns a tracer or None. No-op (returns None) when the endpoint env var is
    unset, so the default posture is no export."""
    global _tracer
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        log("info", "OTEL_EXPORTER_OTLP_ENDPOINT unset; OTel export disabled")
        return None
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        service_name = os.environ.get("OTEL_SERVICE_NAME", "szl-receipts-server")
        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer("szl.receipts")
        log("info", f"OTel tracer initialized; endpoint={endpoint} service={service_name}")
        return _tracer
    except Exception as e:
        log("warn", f"OTel init failed, continuing without export: {e}")
        return None


def _span(name, attributes=None):
    """Context manager helper that emits an OTel span if a tracer exists, else
    a no-op context."""
    if _tracer is None:
        from contextlib import nullcontext
        return nullcontext()
    cm = _tracer.start_as_current_span(name)
    return _SpanWrapper(cm, attributes or {})


class _SpanWrapper:
    def __init__(self, cm, attributes):
        self._cm = cm
        self._attributes = attributes
        self._span = None

    def __enter__(self):
        self._span = self._cm.__enter__()
        try:
            for k, v in self._attributes.items():
                if v is not None:
                    self._span.set_attribute(k, v)
        except Exception:
            pass
        return self._span

    def __exit__(self, *args):
        return self._cm.__exit__(*args)


# ── Chain helpers ──────────────────────────────────────────────────────────────

def _receipt_hash(record: dict) -> str:
    """Stable SHA-256 over the receipt's signed envelope. Used as the chain link
    value (the next receipt's prev_hash)."""
    canonical = json.dumps(record["envelope"], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _rehydrate():
    """Walk STORE_PATH, load every *.json receipt, order by created_at, and
    rebuild the in-memory list and chain head/index. Logs the count.

    Chain pointers are reconstructed by reading each receipt's chain.prev_hash;
    the chain head is set to the hash of the last (most recent) receipt."""
    global _receipts, _chain_head, _chain_index
    loaded = []
    try:
        names = [n for n in os.listdir(STORE_PATH) if n.endswith(".json")]
    except FileNotFoundError:
        names = []
    for name in names:
        path = os.path.join(STORE_PATH, name)
        try:
            with open(path, "r") as f:
                rec = json.load(f)
            loaded.append(rec)
        except Exception as e:
            log("warn", f"skipping unreadable receipt {name}: {e}")

    # Order by created_at (ISO-8601 sorts lexicographically), then chain_index
    # as a tie-breaker for receipts created within the same second.
    def _key(r):
        return (
            r.get("created_at", ""),
            r.get("chain", {}).get("chain_index", 0),
        )
    loaded.sort(key=_key)

    with _receipt_lock:
        _receipts = loaded
        if loaded:
            last = loaded[-1]
            _chain_head = last.get("chain", {}).get("hash") or _receipt_hash(last)
            _chain_index = last.get("chain", {}).get("chain_index", len(loaded) - 1) + 1
        else:
            _chain_head = GENESIS
            _chain_index = 0
    log("info", f"Rehydrated {len(loaded)} receipt(s) from {STORE_PATH}; "
                 f"chain_index={_chain_index} head={_chain_head[:12]}…")
    return len(loaded)


def _broadcast_sse(data: str):
    dead = []
    with _client_lock:
        for wfile in list(_sse_clients):
            try:
                wfile.write(f"data: {data}\n\n".encode())
                wfile.flush()
            except Exception:
                dead.append(wfile)
        for d in dead:
            _sse_clients.remove(d)


# ── HTTP handler ───────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        log("debug", fmt % args)

    def _send(self, code, content_type, body):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/health", "/healthz"):
            self._send(200, "application/json", json.dumps({"status": "ok"}))
        elif path == "/receipts":
            with _receipt_lock:
                body = json.dumps(_receipts)
            self._send(200, "application/json", body)
        elif path == "/metrics":
            body = (
                f"# HELP szl_receipts_total Total receipts received\n"
                f"# TYPE szl_receipts_total counter\n"
                f"szl_receipts_total {_counter_total}\n"
                f"# HELP szl_receipts_valid_total Valid (verified) receipts\n"
                f"# TYPE szl_receipts_valid_total counter\n"
                f"szl_receipts_valid_total {_counter_valid}\n"
            )
            self._send(200, "text/plain; version=0.0.4", body)
        elif path == "/stream":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            with _receipt_lock:
                for r in _receipts[-20:]:
                    self.wfile.write(f"data: {json.dumps(r)}\n\n".encode())
            self.wfile.flush()
            with _client_lock:
                _sse_clients.append(self.wfile)
            try:
                while True:
                    time.sleep(1)
            except Exception:
                pass
        else:
            self._send(404, "text/plain", "not found")

    def do_POST(self):
        global _counter_total, _counter_valid, _chain_head, _chain_index
        path = urlparse(self.path).path
        if path != "/receipt":
            self._send(404, "text/plain", "not found")
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            incoming = json.loads(body)
        except json.JSONDecodeError:
            self._send(400, "text/plain", "invalid JSON")
            return

        _counter_total += 1

        # The server is the signer: it (re)signs the receipt payload with
        # Ed25519. If the POST body is already a DSSE envelope we re-sign its
        # payload; otherwise we treat the whole body as the payload object.
        if isinstance(incoming, dict) and "payload" in incoming and "signatures" in incoming:
            try:
                payload_bytes = base64.b64decode(incoming["payload"])
            except Exception:
                payload_bytes = json.dumps(incoming, sort_keys=True).encode()
        else:
            payload_bytes = json.dumps(incoming, sort_keys=True).encode()

        envelope = sign_dsse(payload_bytes)
        valid = verify_dsse(envelope)
        if valid:
            _counter_valid += 1

        with _receipt_lock:
            prev_hash = _chain_head
            chain_index = _chain_index
            created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ")
            # receipt_id is the SHA-256 of the signed envelope (stable).
            receipt_id = hashlib.sha256(
                json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            record = {
                "id":         receipt_id,
                "created_at": created_at,
                "timestamp":  created_at,   # preserved field name for the dashboard
                "valid":      valid,
                "envelope":   envelope,
                "chain": {
                    "prev_hash":   prev_hash,
                    "chain_index": chain_index,
                },
            }
            record["chain"]["hash"] = _receipt_hash(record)
            _receipts.append(record)
            _chain_head = record["chain"]["hash"]
            _chain_index = chain_index + 1
            try:
                with open(f"{STORE_PATH}/{receipt_id}.json", "w") as f:
                    json.dump(record, f)
            except Exception as e:
                log("warn", f"Could not persist receipt: {e}")

        with _span("szl_receipts.append", {
            "receipt_id": receipt_id,
            "prev_hash": record["chain"]["prev_hash"],
            "chain_index": record["chain"]["chain_index"],
        }):
            _broadcast_sse(json.dumps(record))

        log("info",
            f"Receipt {receipt_id[:12]}… valid={valid} "
            f"chain_index={chain_index} prev={prev_hash[:12]}…")
        resp = {
            "id": receipt_id,
            "valid": valid,
            "chain": record["chain"],
        }
        self._send(200, "application/json", json.dumps(resp))


def boot():
    """Startup hook: load key, init tracer, rehydrate chain, emit boot span."""
    global _private_key
    _private_key = _load_private_key()
    _init_tracer()
    count = _rehydrate()
    with _span("szl_receipts.boot", {
        "store_path": STORE_PATH,
        "rehydrated": count,
        "signed": _private_key is not None,
        "keyid": KEY_ID,
    }):
        log("info", f"SZL Receipts boot complete; rehydrated={count} "
                    f"signed={_private_key is not None}")


if __name__ == "__main__":
    boot()
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    log("info", f"SZL Receipts server listening on :{PORT}")
    server.serve_forever()
