# Exporter request authentication â€” installation contract

This source change belongs to the energy service layer. It protects telemetry reads;
it does not authorize a tunnel, configure a running service, install keys, or qualify
energy for billing. The exporter remains stopped until an owner installs and verifies
its configuration. Key trust and deployed configuration are UNKNOWN here.

The exporter defaults to `127.0.0.1:9471`. Every GET of `/` or `/metrics` requires a
per-client HMAC, including loopback requests behind a reverse proxy. The existing
loopback/tailnet source restriction remains an additional denial boundary. Forwarded
headers, a tailnet-range IP, and Cloudflare Access headers never replace the MAC.
Other targets, query aliases, duplicate security/authentication headers, and request
bodies are rejected before telemetry, local reading files, or peer collection is read.
There is no unauthenticated telemetry or CORS wildcard.

Install the canonical exporter and `szl_meter_access.py` together. A standalone copy
needs the helper beside it; the repository layout loads the root helper automatically.
The helper already ships in the product Dockerfile. All existing `open_meter_get`
callers, the energy/live HTTPX reader, and peer aggregation use this protocol. Missing
client configuration denies network access; the caller reports unavailable readings.
Existing Cloudflare Access credentials remain optional extra headers scoped to the
exact HTTPS `meter2.a-11-oy.com` host. No redirect carries either kind of capability.

The owner must separately provision independent private 32-byte keys per client.
Never commit them or paste them in logs. No key values or production key-generation
command are supplied in this source change. These variables describe the format:

- Server `SZL_METER_HMAC_AUDIENCE`: exact canonical origin, for example
  `https://meter2.a-11-oy.com`. No trailing slash or path. This audience distinguishes
  meter services even behind a loopback reverse proxy. The actual request `Host` must
  match this audience; the proxy must preserve that host. Forwarded-host headers do
  not replace it. A mismatched proxy host fails closed.
- Server `SZL_METER_HMAC_CLIENT_KEYS`: JSON object mapping each allowed client ID to
  its private lower-case 64-hex-character key. One to sixteen clients; duplicate IDs,
  reused keys, malformed keys, and missing configuration deny startup.
- Client `SZL_METER_HMAC_TARGETS`: JSON object keyed by the exact origin, with each
  value containing exactly `client_id` and `key_hex`. Unknown targets deny locally.
  HTTP is permitted only for an exact loopback IP; remote meters and peers require
  HTTPS with normal certificate validation. There is no plain-HTTP tailnet fallback.
- Optional server `OMEN_EXPORTER_BIND`: an explicit address already inside the
  existing loopback/tailnet restriction. Wildcard and ordinary LAN binds deny.
  This variable does not start a listener or change a firewall by itself.

Each request uses `X-SZL-Meter-Client`, `X-SZL-Meter-Time`, `X-SZL-Meter-Nonce`, and
`X-SZL-Meter-Signature`. The MAC is HMAC-SHA256 over the following ASCII fields joined
with one LF and no trailing LF: protocol `szl-meter-hmac-v1`, method, exact raw target,
server audience, client ID, decimal epoch nanoseconds, and 128-bit lower-case hex nonce.
The client sends the signature, never the key. This is request authentication, not a
governance signature or a receipt minted on a GET.

Server/client clocks must be synchronized. Future timestamps, requests predating this
server process, and requests older than 30 seconds deny. A bounded atomic cache accepts
each client/nonce once; it denies at capacity instead of evicting live entries. Clock
rollback denies. Restart rejects prior-process requests even though the replay cache
is in memory. Sustained valid-client traffic can exhaust the cache until expiry and is
denied; it cannot convert capacity pressure into a telemetry authorization bypass.

The integrated exporter now uses the measurement checks merged in PR #2665.
Observed power and UUID come from nvidia-smi; MEASURED joules require fresh,
monotone NVML total-energy-counter deltas for the same device and continuity
interval. Power integration is separately labeled MODELED. Authentication does
not establish per-job attribution or qualify energy for billing.

Synthetic tests use ephemeral in-memory keys and controlled telemetry. Their results
qualify source authentication behavior; live key provisioning, tunnel policy, runtime
activation, real meter measurements, and independent replay remain NOT RUN/UNKNOWN.

## Windows owner installation

`install_meter_windows.ps1 -SourceRevision <full-commit-sha>` requires a clean,
committed checkout matching that revision. It copies the exporter and client helper,
records their SHA-256 hashes, and creates distinct canonical and local-healthcheck
client keys only when no private configuration already exists. Keys are encrypted
with Windows DPAPI for the current user under `%LOCALAPPDATA%\SZL\Meter`, outside
the repository, with directory access restricted to that user and SYSTEM. Existing
configuration is preserved; this command does not rotate established keys.

The installed `program\run_meter_windows.ps1` verifies the recorded file hashes,
decrypts configuration into its process environment, and runs only the authenticated
`127.0.0.1:9471` exporter. It does not activate a tunnel or change DNS. Run it as the
same Windows user that performed installation; a SYSTEM task cannot decrypt that
user's DPAPI data. The canonical client's matching target configuration must be
provisioned separately through the hosting provider's secret mechanism. Do not
print decrypted configuration, put keys in command arguments, or commit it.
