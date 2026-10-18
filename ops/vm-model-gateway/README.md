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

## Native Windows supervisor

`windows-bootstrap.py` captures startup errors without opening a console and
runs `windows-supervisor.py` from the same directory. The supervisor starts only
the pinned SSH forward and proposal gateway. It signs an intent before starting
either process, signs the startup result or failure, and places both children in
a Windows job with kill-on-close. An occupied local port refuses startup. A child
exit ends the supervisor; any scheduler retry restarts transport only and never
replays an inference request. Job assignment follows child creation; abrupt
supervisor termination in that startup interval is not qualified here.
Source for this host service belongs to the
`services` and `provenance` layers; these scripts are not copied into the HF image.

### Installation requirements

1. Use a native Windows Python environment with the gateway's existing
   `cryptography` dependency and OpenSSH at the path declared in the supervisor.
   Put the runtime under `%LOCALAPPDATA%\SZL\VmModelRuntime` outside the repository
   and sync folders. Restrict the directory and inherited child ACLs to the
   designated Windows user and `SYSTEM`; verify the resulting ACLs before storing
   credentials. Keep `logs`, `operations`, and `receipts` as private subdirectories.
2. Copy `windows-bootstrap.py` and `windows-supervisor.py` there. Populate `source/`
   with exactly the following source files from A11oy commit
   `548ae61181d55ca72d9d7151c16e97b382277dae`, preserving their relative paths:
   `ops/vm-model-gateway/gateway.py`, `szl_dsse.py`, and `szl_content_address.py`.
   Check their bytes against all three SHA-256 pins in `EXPECTED`. The supervisor
   verifies these copied bytes on each start. Its revision field is **DECLARED**;
   checking three files does not attest the entire checkout, Python environment,
   VM, or running image.
3. Place the reviewed host-specific OpenSSH configuration at `ssh-config`. It must
   define `szl-massed-qualification`, require host-key checking, identify only the
   authorized VM and protected SSH key, and permit the explicit loopback forward.
   The SHA-256 in the supervisor is installation-specific, not a reusable trust
   anchor. A different host configuration requires an independently reviewed pin
   update and a new source/installation receipt before starting. Never replace
   this check with a runtime calculation that trusts whatever file is present.
4. Provision the existing gateway bearer into `gateway-bearer.key` and the
   persistent P-256 audit signer into `gateway-audit-p256.pem` using a private
   credential channel. Do not place their values in command-line arguments, task
   XML, logs, Git, or this README. A DPAPI-protected transfer protects that transfer;
   these runtime files are plaintext protected by Windows ACLs. Their presence
   does not establish credential authority or production acceptance.
5. Register an explicitly authorized user-scoped Task Scheduler task with an
   **AtLogon** trigger for that user, an absolute native `pythonw.exe` action using
   `-I -B` and the absolute `windows-bootstrap.py` path, the private runtime working
   directory, and **IgnoreNew** for overlapping instances. Configure a bounded
   failure retry (for example, three retries one minute apart); retain the task
   XML and read back its principal, trigger, action, and retry settings. This
   logon task does not establish operation before user sign-in. The existing
   Cloudflare tunnel remains a separately owned service.

### Installation acceptance evidence

The source package and the Linux fixture suite do not establish native Windows
recovery. Native autorestart qualification remains **BLOCKED** until the operator
records a controlled owned-child exit, the supervisor's cleanup, the scheduled
task retry, and fresh matching local/public gateway instance IDs. Preserve failure
evidence, new PIDs, task readback, and verified chained DSSE intent/outcome receipts.
Inspect upstream slots for idle state before any controlled transport restart.
Logout/reboot recovery is **UNKNOWN** until separately exercised. A saved
`current-processes.json` is historical state and always requires a fresh probe.

Even after transport restart succeeds, this remains dependent on the Windows
host, its user logon, SSH reachability, and the separate Cloudflare connector.
Held-out model quality, independent authority pins, governed A11oy execution,
durable application state, and production acceptance require their own evidence.
