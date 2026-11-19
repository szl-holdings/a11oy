#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Pool-attester inference-receipt minter (compute-pool/v1).

Runs on the sovereign laptop next to the fabric it attests.  Each cycle:

  1. resolves the exact served model digest from the local Ollama /api/tags;
  2. performs one bounded chat completion through the SOVEREIGN SERVING PATH
     (the same fail-closed proxy + Bearer the production Space uses);
  3. hashes the exact request/response bytes (never embeds their content);
  4. builds the compute-pool/v1 inference-receipt payload;
  5. DSSE-signs it with the dedicated pool-attester P-256 key (the private key
     is generated on and NEVER leaves this machine; only the public PEM +
     SHA-256 pin are published to the Space);
  6. pushes the envelope to the Space's fail-closed ingestion route
     (POST /api/a11oy/v1/compute-pool/receipts), where it is re-verified
     against the pinned trust root before atomic bounded storage.

Loop cadence must stay <= half the Space freshness window (default 120 s for
a 300 s window).  The receipt binds hashes and identifiers only: no raw
prompt or completion content ever enters a receipt (the contract verifier
rejects content-bearing payloads outright).

Requires: cryptography (ECDSA P-256).  Stdlib only otherwise.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, Optional

RECEIPT_SCHEMA = "szl.compute-pool.inference-receipt/v1"
RECEIPT_PAYLOAD_TYPE = "application/vnd.szl.compute-pool.inference-receipt+json"
POOL_KEY_ID = "a11oy-pool-attester-v1"
POOL_ISSUER = "a11oy-pool-attester"
POOL_AUDIENCE = "a11oy-compute-pool"
POOL_PREDICATE = "szl.compute-pool.inference-qualification/v1"
POOL_MEASUREMENT_CONTRACT = "szl.compute-pool.measurement-contract/v1"

_PROBE_PROMPT = "Health probe. Reply with the single word: READY"
_USER_AGENT = "a11oy-pool-attester/1.0"


def canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def pae(payload_type: str, body: bytes) -> bytes:
    t = payload_type.encode("utf-8")
    return b"DSSEv1 " + str(len(t)).encode() + b" " + t + b" " + str(len(body)).encode() + b" " + body


def _read_secret(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read().strip()


def _http_json(url: str, *, method: str = "GET", body: Optional[bytes] = None, token: Optional[str] = None,
               timeout_s: float) -> tuple[int, Optional[bytes]]:
    request = urllib.request.Request(url, data=body, method=method)
    request.add_header("User-Agent", _USER_AGENT)
    if token:
        request.add_header("Authorization", "Bearer " + token)
    if body is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout_s, context=ssl.create_default_context()) as response:
            return int(response.status), response.read()
    except urllib.error.HTTPError as error:
        return int(error.code), error.read() if error.fp else None
    except (urllib.error.URLError, OSError, TimeoutError):
        return 0, None


def _model_digest(base_url: str, token: str, model: str, timeout_s: float) -> Optional[str]:
    status, raw = _http_json(base_url.rstrip("/") + "/api/tags", token=token, timeout_s=timeout_s)
    if status != 200 or not raw:
        return None
    try:
        tags = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    for entry in tags.get("models", []) or []:
        if entry.get("model") == model or entry.get("name") == model:
            digest = str(entry.get("digest") or "")
            if digest.startswith("sha256:"):
                digest = digest[len("sha256:"):]
            if len(digest) == 64 and all(c in "0123456789abcdef" for c in digest):
                return digest
    return None


def mint_once(args: Any, private_key: Any) -> bool:
    token = _read_secret(args.token_file)
    digest = _model_digest(args.base_url, token, args.model, args.timeout_ms / 1000.0)
    if digest is None:
        print("mint: model digest unavailable (fabric unreachable or model missing)", file=sys.stderr)
        return False
    request_body = canonical_json({
        "model": args.model,
        "messages": [{"role": "user", "content": _PROBE_PROMPT}],
        "max_tokens": args.max_output_tokens,
        "temperature": 0,
        "stream": False,
    })
    started = time.monotonic()
    status, response_body = _http_json(
        args.base_url.rstrip("/") + "/v1/chat/completions",
        method="POST",
        body=request_body,
        token=token,
        timeout_s=args.timeout_ms / 1000.0,
    )
    duration_ms = (time.monotonic() - started) * 1000.0
    success = status == 200 and bool(response_body)
    if not success:
        print(f"mint: inference failed (status={status})", file=sys.stderr)
        return False
    try:
        completion = json.loads(response_body or b"")
        choices = completion.get("choices") or []
        serving = bool(choices) and completion.get("model") == args.model
    except (UnicodeDecodeError, json.JSONDecodeError):
        serving = False
    observed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    payload = {
        "schema_version": RECEIPT_SCHEMA,
        "node_id": args.node_id,
        "model_id": args.model,
        "model_digest_sha256": digest,
        "observed_at": observed_at,
        "request_sha256": hashlib.sha256(request_body).hexdigest(),
        "response_sha256": hashlib.sha256(response_body).hexdigest(),
        "duration_ms": round(duration_ms, 3),
        "success": True,
        "serving": serving,
        "bounds": {
            "timeout_ms": args.timeout_ms,
            "max_input_tokens": args.max_input_tokens,
            "max_output_tokens": args.max_output_tokens,
        },
        "issuer": POOL_ISSUER,
        "audience": POOL_AUDIENCE,
        "predicate_type": POOL_PREDICATE,
        "measurement_contract": POOL_MEASUREMENT_CONTRACT,
    }
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec

    body = canonical_json(payload)
    signature = private_key.sign(pae(RECEIPT_PAYLOAD_TYPE, body), ec.ECDSA(hashes.SHA256()))
    envelope = canonical_json({
        "payloadType": RECEIPT_PAYLOAD_TYPE,
        "payload": base64.b64encode(body).decode("ascii"),
        "signatures": [{"keyid": POOL_KEY_ID, "sig": base64.b64encode(signature).decode("ascii")}],
    })
    ingest_token = _read_secret(args.ingest_token_file)
    status, raw = _http_json(
        args.ingest_url,
        method="POST",
        body=envelope,
        token=ingest_token,
        timeout_s=args.ingest_timeout_s,
    )
    if status != 202:
        print(f"mint: ingestion refused (status={status})", file=sys.stderr)
        return False
    print("mint: accepted " + hashlib.sha256(envelope).hexdigest()[:16])
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--key", required=True, help="pool-attester P-256 private key (PEM, stays on this machine)")
    parser.add_argument("--token-file", required=True, help="sovereign gateway bearer token file (serving path auth)")
    parser.add_argument("--ingest-token-file", required=True, help="Space ingestion bearer token file")
    parser.add_argument("--node-id", default="omen-betterwithage")
    parser.add_argument("--model", default="llama3.1:8b")
    parser.add_argument("--base-url", default="http://127.0.0.1:11436", help="sovereign serving-path base URL")
    parser.add_argument("--ingest-url", default="https://a-11-oy.com/api/a11oy/v1/compute-pool/receipts")
    parser.add_argument("--interval", type=int, default=120, help="seconds between receipts (<= half freshness window)")
    parser.add_argument("--timeout-ms", type=int, default=10000)
    parser.add_argument("--max-input-tokens", type=int, default=256)
    parser.add_argument("--max-output-tokens", type=int, default=32)
    parser.add_argument("--ingest-timeout-s", type=float, default=20.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    from cryptography.hazmat.primitives import serialization
    with open(args.key, "rb") as handle:
        private_key = serialization.load_pem_private_key(handle.read(), password=None)
    if not hasattr(private_key, "curve") or getattr(private_key, "curve").name != "secp256r1":
        print("mint: key must be an ECDSA P-256 private key", file=sys.stderr)
        return 2

    while True:
        mint_once(args, private_key)
        if args.once:
            return 0
        time.sleep(max(10, args.interval))


if __name__ == "__main__":
    sys.exit(main())
