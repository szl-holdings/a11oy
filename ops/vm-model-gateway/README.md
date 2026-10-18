<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Local VM model gateway

This is an isolated A11oy **proposal** adapter for the already running Massed Compute
`llama-server`. It binds `127.0.0.1:4000` and reaches only the verified SSH
loopback tunnel at `127.0.0.1:19483`. It is not a production route, an A11oy
execution authority, a held-out evaluation, or a claim of model quality.

## Contract

- `GET /health` is a minimal public local process readback with a random,
  per-process `instance_id`. The ID can be compared between local and edge
  routes before credentials are sent; it is not cryptographic identity proof.
  This GET does not probe the model or mint a receipt.
- `GET /v1/models` requires `Authorization: Bearer <SZL_LITELLM_KEY>` and checks
  that upstream advertises exactly the raw GGUF ID. It returns the stable alias
  `prism-ml/Ternary-Bonsai-2-27B-PQ2_0` and a `DECLARED` byte pin.
- `POST /v1/chat/completions` requires the same key. It accepts only text
  system/user/assistant messages, the exact alias, `stream:false`,
  `max_tokens` 1–1024, temperature 0–2, optional integer seed, and optional
  `response_format:{"type":"json_object"}`. Duplicate JSON keys, nonfinite
  values, tools, unknown fields, duplicate `Content-Length`, transfer encoding,
  oversize bodies, and wrong model names are rejected. Unknown client headers
  are never forwarded.
- One request at a time is admitted. Immediately before forwarding, `/slots`
  must report every slot idle. The gateway has no retry or fallback. A signed
  DSSE P-256 hash-chain **intent** is durable before inference; a signed outcome
  follows, including a hash of the upstream response. An unsealed outcome or
  failed chain write latches subsequent inference off. GETs do not sign.
- Upstream HTTP is plain text **only over the local SSH tunnel**. Redirects are
  not followed. The forward has a 30-second total watchdog and a 2 MiB response
  cap. Only a validated single assistant choice with the exact raw model ID,
  bounded usage, and finish reason `stop` or `content_filter` is returned; any
  ancillary `reasoning_content` is discarded.

The model SHA-256 `3907dc1658db1f78a9826bf8d5bcb8dc65db0d466388937af57f2294fae62ec1`
was measured on the VM file in a separate bounded readback. The adapter pins
that digest as **DECLARED** configuration. It does not rehash the 7.2 GB file
per request, attest VM identity independently, or grant effect authorization.

## Local startup

Use a private shell or service environment. Never put key material on a
command line, in the repository, or in logs:

```powershell
$env:SZL_LITELLM_KEY = <existing secret from a protected secret source>
$env:SZL_COSIGN_PRIVATE_PEM = <persistent P-256 PEM from a protected secret source>
$env:SZL_VM_GATEWAY_RECEIPTS_DIR = <existing protected directory outside this repo>
python -B ops/vm-model-gateway/gateway.py
```

The signer and receipts directory are mandatory. The gateway uses the repo's
`szl_dsse.sign_payload` and `verify_envelope` implementation. Its local audit
signer has `REPO_DECLARED` trust; these receipts are **not** native A11oy
production acceptance or an independent witness. The startup verifies all
existing envelopes and their chain before listening. Keep the receipt directory
private and back it up as an evidence asset. Do not configure the upstream to
the VM's public port 8080.

Run the isolated fixture suite without a live model call:

```powershell
python -B -m unittest discover -s ops/vm-model-gateway -p 'test_*.py' -v
```

The tests use a loopback fake upstream and a generated fixture P-256 key. They
do not start a new GPU workload. Deployment, TLS, upstream access control,
held-out quality evaluation, and A11oy's own acceptance gates remain separate.
