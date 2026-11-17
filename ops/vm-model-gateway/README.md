<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Local VM model gateway

This is an isolated A11oy **proposal** adapter for the already running Massed Compute
`llama-server`. It binds loopback port 4000 by default, or a separately reviewed free gateway port,
and reaches only the verified SSH
loopback tunnel (default `127.0.0.1:19483`). It is not a production route, an A11oy
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

For direct local startup, `SZL_VM_GATEWAY_TUNNEL_PORT` can select an existing
private loopback SSH forward (default 19483). The independent
`SZL_VM_GATEWAY_PORT` selects the gateway's listener (default 4000; e.g.
4001 only when independently measured free). Both selections are strict
decimal ASCII in 1024-65535, distinct, and bound exclusively to loopback.
The tunnel cannot adopt gateway default port 4000 or upstream port 8080;
the gateway cannot adopt tunnel default 19483 or port 8080. No remote
target or host override is possible. The direct mode does not supervise,
adopt, or terminate a foreign listener.

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

`windows-bootstrap.py` launches the pinned supervisor in a fresh process without
opening a console. One bootstrap invocation permits **one initial start and at
most three retries**, with **60 seconds after completed cleanup** before each
retry. The budget never resets after a healthy interval. A clean supervisor exit
still requires cleanup and does not retry. Pin, path, logging, launch, or cleanup
failures stop the bootstrap instead of bypassing a check.

Every attempt starts inside a fresh unnamed Windows Job using
`CreateProcessW` with `PROC_THREAD_ATTRIBUTE_JOB_LIST`. The Job is assigned before
the supervisor's initial thread runs; there is no spawn-then-assign fallback.
The bootstrap retains the sole noninheritable Job handle with kill-on-close and
no breakaway. The unchanged supervisor's own Job nests beneath it, so its SSH and
gateway children are also covered during their inner assignment interval.

Cleanup terminates only this owned Job, waits retained process handles, and
requires empty Job membership before closing it. The bootstrap tracks native
member identities during the attempt. The lifetime Job process count must match
the retained identity census; a missed or late process makes cleanup unproven
and prevents another attempt. This includes a very short-lived child missed
entirely by the census, so not every early startup failure is recoverable.
Free ports, a dead supervisor PID, or an empty
active-process count alone are not accepted as a complete cleanup barrier.

The supervisor signs its intent before starting SSH or the gateway and signs
the startup result or failure. Each fresh supervisor process that reaches signing
creates a separate operation chain with a fresh timestamp and initial
`previous_sha256: null`.
Bootstrap JSONL lifecycle records are explicitly **UNSIGNED**, with no execution
authority; they are not a global signed chain. Every attempt has exclusive new
stdout/stderr files. The bootstrap reads only its pinned supervisor source and
writes diagnostic logs; it never opens bearer or signer files. An occupied
local port still refuses supervisor startup. Recovery never replays inference.

The native process primitives follow Microsoft's
[creation-time Job assignment](https://devblogs.microsoft.com/oldnewthing/20230209-00/?p=107812),
[process attribute contract](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute),
and [nested Job semantics](https://learn.microsoft.com/en-us/windows/win32/procthread/nested-jobs).
Windows 10 or newer is required.
The supervisor reads `transport-config.json` in its private runtime
directory **before opening either credential file**. A missing file retains
the legacy tunnel 19483 and gateway 4000. The original two-field v1
configuration is still valid. To choose two separately owned, free
localhost listeners the complete nonsecret file is:

```json
{"schema":"szl.vm-model-transport/v1","local_tunnel_port":19484,"local_gateway_port":4001}
```

Only these three field names are accepted. The third field is optional,
and cannot set the host, SSH target, remote port, credential source or
execution authority. Duplicate/unknown keys, symlinks, malformed or
oversize input, noninteger/privileged ports, reserved ports and listener
collisions refuse startup without adopting or terminating any owner.
The selected SSH forward, gateway bind, health check and signed supervisor
intent all use the same reviewed configuration. The file persists across
bounded user-scoped bootstrap retries. Native Task Scheduler retry
**must remain disabled** to avoid multiplying the bootstrap budget.

The supervisor emits a measured `four-file-sha256:` identity derived
from exactly the four reviewed copied-source SHA-256 pins, not a fake
GitHub commit SHA. The installer must *separately* bind those bytes to
the protected, reviewed GitHub revision and keep production admission
blocked until independent release-quality and model evidence exists.

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
   with the four source files from the independently reviewed and merged
   gateway-port source revision, preserving their relative paths:
   `ops/vm-model-gateway/gateway.py`, `ops/vm-model-gateway/runtime_config.py`,
   `szl_dsse.py`, and `szl_content_address.py`.
   Check their bytes against all four SHA-256 pins in `EXPECTED`. The supervisor
   verifies these copied bytes on each start. Its revision field is **DECLARED**;
   checking four files does not attest the entire checkout, Python environment,
   VM, or running image.

   The exact same reviewed bootstrap bytes support two explicit filename
   layouts: `windows-bootstrap.py` selects sibling `windows-supervisor.py`;
   `bootstrap.py` selects sibling `supervisor.py`. Preserve the existing task
   action and install under its existing filename. Do not transform the source
   bytes or select a target through an environment variable. Other launcher
   names, a missing sibling, or a symlink refuse startup. Before every attempt
   the bootstrap requires supervisor SHA-256
   `00498aa240634d6398c96046d6f8011f16cfe3b69e45e9b533b7e690fea690f7`.
   Record both installed filenames and hashes in the installation receipt.
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
   directory, and **IgnoreNew** for overlapping instances. Native Task Scheduler
   failure retry must be disabled: the optional `RestartOnFailure` XML element
   must be **absent**. Do not emit `Count=0`, which is invalid when that element
   is present. The bootstrap owns the entire four-attempt budget; leaving three
   native retries enabled could multiply it to sixteen supervisor starts.
   Retain and read back the task XML, including the absent native retry element.
   Preserve the existing principal, trigger, action, overlap policy, and engine
   setting during migration. This logon task does not establish operation before
   user sign-in. The existing Cloudflare tunnel remains separately owned.

### Selecting a separate owned tunnel

This source package does not change the installed service. Deploy only the
reviewed source and retain an installation receipt for the exact release used.

1. Read back current listener ownership, the scheduled task action, and the
   approved SSH target. A successful raw `/health` is transport evidence only.
   Preserve unrelated listeners and the current public route.
2. Stage the reviewed bootstrap and supervisor plus the four copied source
   files described above. Compare the source bytes with the hard-coded
   `EXPECTED` manifest and keep the reviewed SSH configuration pin unchanged.
   Never calculate new trust pins from arbitrary installed files.
3. Confirm the proposed tunnel and gateway listener ports are free, then place the complete
   `transport-config.json` in the private runtime directory. For the separate
   port example use 19484 only if it is free. Retain the existing directory ACLs,
   credential files, receipt chain, and task trigger/action.
4. Start the existing task. Freshly inspect its owned child PIDs, loopback binds,
   `current-processes.json`, and chained supervisor intent/outcome. The selected
   `upstream` in the state and receipt must agree. The old external tunnel
   must retain its own PID and listener. A conflict must stop startup without
   reading credentials or taking over the existing listener.
5. Check both GET /health and unauthenticated GET /v1/models (401)
   at the **selected gateway listener**, not Ollama port 4000 or
   a public raw-engine response.
   Use an already credentialed operator client for the bounded authenticated
   model-identity check and any separately authorized inference smoke test;
   record only statuses, model identity, instance ID, and receipt references.
   Do not print credential or signer material. If no such client is available,
   authenticated acceptance remains unverified.
6. Qualify the owned-child cleanup and bounded bootstrap retry using the
   acceptance procedure below. Compare local/public instance IDs only after a
   separately reviewed edge route points at this gateway. An unchanged public
   raw-engine route cannot establish gateway acceptance.

No inference is replayed by a supervisor retry. A nondefault local port does not
validate the remote engine's model bytes, add execution authority, or lift the
existing `production_acceptance: BLOCKED` status.

### Bootstrap migration and rollback

Treat the reviewed bootstrap replacement and removal of native
`RestartOnFailure` as one installation unit. Stage and hash the exact source,
retain the prior bootstrap and task XML, then quiesce only the owned task and
verify its retained process handles have exited. Replace only the bootstrap
bytes and remove the optional native retry element while the task is stopped.
Read back both before starting. The supervisor and four copied runtime files
remain byte-for-byte unchanged. If either installation step fails, restore
both the prior bootstrap and prior task XML before starting. Never leave the
new four-attempt bootstrap paired with the previous native retry policy.

### Installation acceptance evidence

The portable fixture suite does not establish native recovery. The Windows
tests additionally use credential-free child/grandchild canaries to verify
creation-time Job ownership and cleanup, including a nested Job and a retained
grandchild process handle. They do not launch the real gateway or read its keys.

Native gateway recovery remains **BLOCKED** until the operator records a
controlled owned-child exit, the old supervisor and owned descendants completing
cleanup, the same bootstrap waiting at least 60 seconds, and a fresh supervisor,
SSH, gateway, and local gateway instance ID. Preserve bootstrap records, retained
handle wait results, new PIDs, task readback, and independently verified supervisor
DSSE operation chains. Compare a public instance ID only after a separately
reviewed edge route actually points at this gateway.

Inspect upstream slots for idle state before any controlled transport restart.
After four failed attempts, the bootstrap exits failed; another invocation
requires an explicit operator start or the configured logon trigger. A bootstrap
crash, logout, reboot, or extended outage is not an unlimited-recovery promise.
Logout/reboot recovery is **UNKNOWN** until separately exercised. A saved
`current-processes.json` is historical state and always requires a fresh probe.

Even after transport restart succeeds, this remains dependent on the Windows
host, its user logon, SSH reachability, and the separate Cloudflare connector.
Held-out model quality, independent authority pins, governed A11oy execution,
durable application state, and production acceptance require their own evidence.
