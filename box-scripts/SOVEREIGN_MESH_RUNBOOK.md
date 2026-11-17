<!--
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 - Doctrine v11
-->

# Sovereign compute and meter verification runbook

Use this runbook from the repository root on the Windows host that owns the
selected installation. It covers native Ollama, the authenticated GPU meter,
and the gateway profile selected for that installation. Source configuration,
local process health, admitted inference, and measured energy are separate
observations; record each with its source revision and observation time.

The commands below inspect existing services unless a section explicitly points
to an installation procedure. They do not establish current production readiness,
authorize a model workload, or activate a public endpoint.

## 1. Identify the intended service before changing anything

| Component | Existing contract | What a successful read establishes |
|---|---|---|
| Native Ollama | Existing local server, commonly `127.0.0.1:11434`; `GET /api/version` | Process/version response; model identity and GPU execution remain unverified. |
| Authenticated meter | `127.0.0.1:9471` by default; `GET /` and `GET /metrics` require per-client HMAC | An authorized exporter response; energy qualification still requires its measurement evidence. |
| Massed proposal gateway | `127.0.0.1:4000`; `GET /health` returns `status: "local_gateway"` | Local proposal-gateway liveness and an instance identifier. It does not probe the model or mint a receipt. |
| Staged Ollama/LiteLLM gateway | An explicitly selected, unused loopback port and an exact consumer/backend model mapping | Only the checks described in [gateway preflight](GATEWAY_PREFLIGHT.md). |

Port 4000 is not evidence that LiteLLM is installed. An existing Massed proposal
gateway and a staged Ollama/LiteLLM gateway are different profiles; preserve the
owned listener and its supervisor. Do not install one over the other or redirect
an existing tunnel to a staging service.

These bounded reads do not generate text or read credentials:

~~~powershell
git rev-parse HEAD
git status --short
nvidia-smi --query-gpu=name,driver_version,power.draw,power.limit --format=csv,noheader,nounits
Get-NetTCPConnection -State Listen |
  Where-Object { $_.LocalPort -in 11434,9471,4000 } |
  Select-Object LocalAddress,LocalPort,OwningProcess
curl.exe --silent --show-error --max-time 3 --fail http://127.0.0.1:11434/api/version
curl.exe --silent --show-error --max-time 3 --fail http://127.0.0.1:4000/health
~~~

A refused connection identifies an unavailable local service. HTTP 200 with HTML,
an unexpected schema, or another service's response is not a successful contract
check. A loopback request does not prove the listener is loopback-only; inspect
`LocalAddress` as well. Hardware names and driver versions do not establish
ownership, a running model, or an inference receipt. An `N/A` power field stays
unavailable, never zero.

Ollama stays native for these Windows profiles. Keep its access within the
installation's reviewed loopback/private-network boundary; never expose bare
Ollama through public ingress. A 403 is not a reason to set wildcard
`OLLAMA_ORIGINS` or `OLLAMA_HOST`. Diagnose the selected origin, hostname,
authentication and existing network policy before proposing a configuration
change.

## 2. Follow the matching gateway profile

### Existing Massed proposal gateway

Use [the VM model gateway runbook](../ops/vm-model-gateway/README.md) for its
source pins, transport configuration, protected receipt directory, P-256 audit
signer and native Windows supervisor. The gateway has one exact model alias and
a bounded proposal API; it is not an Ollama load balancer.

The health response is public local process metadata. The authenticated model
catalog and inference path are separate contracts. Keep authentication material
in the existing protected runtime; do not put it in command arguments, logs,
task XML or this repository. Follow the runbook's existing-launcher mapping
when maintaining an installed supervisor rather than replacing its task action.

The gateway's local signed intent/outcome chain uses `REPO_DECLARED` trust.
It does not confer canonical A11oy execution authority, model qualification,
independent ownership proof or production acceptance.

### Staged Ollama/LiteLLM gateway

Use [GATEWAY_PREFLIGHT.md](GATEWAY_PREFLIGHT.md) and its pinned dependency file.
Select the intended consumer alias, exact Ollama backend tag and independently
retained artifact digest before staging. Do not assume a historical model tag
is installed or copy the candidate catalog's digest into the expected field.

The preflight supports a narrow static profile with one model entry. It does not
validate the older multi-node load-balancing configuration as an equivalent
profile. A wider gateway configuration needs its own reviewed validation.

The following is a template for an **already staged**, loopback-only gateway.
Replace every capitalized placeholder with the retained installation values.
Port 14000 is an example staging port: independently confirm it is unused and
not selected by a tunnel before a separate installation operation uses it.

~~~powershell
python -B box-scripts/gateway_preflight.py `
  --config "PATH_TO_EXISTING_PROTECTED_STAGING_CONFIG" `
  --model "EXACT_CONSUMER_ALIAS" `
  --backend-model "EXACT_OLLAMA_TAG" `
  --backend-digest "RETAINED_64_CHARACTER_LOWERCASE_SHA256" `
  --gateway-origin http://127.0.0.1:14000 `
  --ollama-url http://127.0.0.1:11434 `
  --public-gateway "EXACT_INTENDED_HTTPS_GATEWAY_ORIGIN" `
  --consumer-base https://a-11-oy.com `
  --timeout 3 `
  --probe
~~~

The existing key must be supplied through the protected environment named in
the preflight contract, never an inline key. With `--probe`, the tool performs
at most five GETs; it does not infer, start a service, download weights, sign a
receipt or activate ingress. Exit 0 / `LOCAL_PREFLIGHT_PASS` still reports
`production_ready=false` and `activation_authorized=false`. Preserve a blocked
result for any alias, digest, authentication or consumer mismatch.

## 3. Install and verify the authenticated meter separately

The authoritative installation and protocol contract is
[METER_REQUEST_AUTH.md](METER_REQUEST_AUTH.md). Use the canonical
[exporter](omen_joule_exporter.py) and [request helper](../szl_meter_access.py)
together.

For a separately authorized Windows installation,
[install_meter_windows.ps1](install_meter_windows.ps1) requires a clean committed
checkout and an exact `-SourceRevision`. It preserves existing private
configuration, records installed source hashes, and does not start a listener or
tunnel. The installed [run_meter_windows.ps1](run_meter_windows.ps1) verifies those
hashes and runs the authenticated loopback exporter as the same Windows user
that owns its DPAPI configuration. A SYSTEM task cannot substitute for that
user's DPAPI identity. Do not use the legacy bulk restart scripts as prerequisites.

| Configuration name | Role |
|---|---|
| `SZL_METER_HMAC_AUDIENCE` | Server's exact canonical origin; the request Host must match it. |
| `SZL_METER_HMAC_CLIENT_KEYS` | Server's independent per-client private keys. |
| `SZL_METER_HMAC_TARGETS` | Client configuration keyed by exact meter origin; the source-owned version selector may select a versioned name. |
| `OMEN_EXPORTER_BIND` / `OMEN_EXPORTER_PORT` | Restricted listener configuration; the Windows launcher uses loopback port 9471. |
| `OMEN_ENGINE_NAME` | Meter engine identity; reconcile it with the intended consumer/node label. |
| `SZL_GLM_METER` | Meter selected by the live energy reader. |
| `A11OY_JOULE_METER_URL` / `A11OY_JOULE_METER_URLS` | Meter source configuration used by the energy operator. |

Do not print or copy private values during verification. Public remote meters
require HTTPS, exact audience/client configuration, and the applicable ingress
policy. Plain-HTTP tailnet fallback and redirects do not carry a meter capability.
The reverse proxy must preserve the canonical Host; substituting a loopback Host
does not satisfy an HTTPS audience.

An anonymous request is a **denial check**, not a telemetry read:

~~~powershell
curl.exe --silent --show-error --max-time 3 --output NUL --write-out "%{http_code}\n" http://127.0.0.1:9471/
~~~

The current exporter denies unauthenticated telemetry. A 401/403 records denial;
a timeout records unavailability. Neither proves that an enrolled client can
read telemetry. An anonymous 200 requires investigation.

For an **already enrolled meter2 client** in its protected environment, this
bounded authenticated read checks the response shape without printing headers,
keys, GPU identifiers or telemetry bodies:

~~~powershell
@'
import json
from szl_meter_access import open_meter_get

with open_meter_get("https://meter2.a-11-oy.com/", timeout=3.0) as response:
    status = response.status
    body = response.read(65537)
if status != 200 or len(body) > 65536:
    raise RuntimeError("meter response is unavailable or exceeds the read limit")
document = json.loads(body)
if not isinstance(document, dict) or not isinstance(document.get("engines"), list):
    raise RuntimeError("meter response does not match the exporter shape")
print({"http_status": status, "exporter_json": True, "energy_qualified": False})
'@ | python -B -
~~~

This requires the installed audience and exact-origin client configuration to
agree; it does not provision them. Retain separate local/public authenticated
readback, anonymous denial, replay denial and old-key rejection evidence using
the protocol contract. A successful response shape does not qualify its energy.

The [HF enrollment helper](enroll_meter_hf.py) remains a proposal with a real
apply-path refusal documented in the authentication runbook. Do not bypass that
refusal or treat synthetic enrollment tests as a live key transfer.

## 4. Reconcile the actual canonical consumer

Check the deployed source and consumer, not just the intended hostname. Current
[registry resolution](../szl_llm_registry.py) uses this endpoint precedence:

1. `A11OY_BRAIN_URL`
2. `A11OY_MODEL_BASE_URL`
3. `A11OY_SOVEREIGN_GATEWAY_URL`
4. `SZL_LOCAL_LLM_URL`
5. A guarded localhost default when none is explicitly configured.

The fallback default is not operator intent or a production GPU binding.
`SZL_LOCAL_LLM_MODEL` requests an exact served tag; an explicit missing tag must
remain blocked. A gateway profile must agree with the consumer's API style,
exact alias, backend tag and retained artifact identity. Do not silently point
a sovereign consumer at a proposal gateway or substitute another installed model.

The registry's bearer configuration uses `A11OY_SOVEREIGN_GATEWAY_KEY` with
`SZL_LOCAL_LLM_KEY` fallback. That bearer, ingress Access policy and meter HMAC
serve different boundaries; one does not replace the others.

Read the public canonical diagnostics without generating a model workload:

~~~powershell
curl.exe --silent --show-error --max-time 15 --fail https://a-11-oy.com/api/a11oy/v1/llm/sovereign/health
curl.exe --silent --show-error --max-time 15 --fail https://a-11-oy.com/api/a11oy/v1/energy/operator/status
curl.exe --silent --show-error --max-time 15 --fail https://a-11-oy.com/api/a11oy/v1/energy/live
~~~

The sovereign health route reports metadata reachability and exact-tag
availability. Its anonymous response deliberately withholds private model/origin
data and retains `gpu_verified=false`, `weights_verified=false`,
`ownership_proof="UNAVAILABLE"` and `operational=false`. A reachable node is labeled
`UNKNOWN`; an unreachable one is `UNAVAILABLE`. Historical durable inference
receipts do not prove the current endpoint, weights or GPU.

Keep those boundaries when interpreting a green local health check or a
successful model catalog. Admitted inference needs the selected execution path,
its authorization, actual outcome and bound retained evidence. This read-only
sequence does not run that workload.

## 5. Qualify energy without upgrading its scope

The [exporter](omen_joule_exporter.py), [energy live reader](../szl_energy_live.py)
and [operator](../szl_energy_operator.py) require fresh, monotone direct NVML
total-energy-counter deltas for the same GPU identity and continuity interval.
Unsupported counters, stale samples, missing devices or counter decreases leave
measured joules unavailable. Sampled-power integration stays `MODELED`.

The operator distinguishes a measured bounded GPU-host window from energy
attributable exclusively to a job. Its job energy stays `SAMPLE` and nonbillable
without separately proven exclusive attribution. An environment assertion of
exclusivity cannot supply that proof.

The [legacy Ollama energy probe](ollama_energy_probe.py) generates real inference
and writes a local observation file. It is not a passive prerequisite for
hardware, process or authenticated-meter checks. Its labels and any `models[]`
entry must pass the current consumer's evidence checks; launching a loop or
seeing that field does not establish qualified energy.

Before any separate inference qualification, select the exact model and workload,
retain authorization, bound the run, bracket it with compatible meter samples,
and preserve the outcome and measurement scope. Do not start the continuous
energy operator merely to make a readiness tile change.

## Troubleshooting by boundary

| Observation | Next check |
|---|---|
| Port 4000 is occupied | Identify the existing gateway profile and supervisor. Keep staging on a separately selected unused loopback port. |
| Ollama answers version but model is absent | Reconcile the explicit alias/tag and independently retained artifact identity; do not select the first installed model. |
| Meter anonymous request returns 403 | Expected denial can coexist with a working meter. Verify the enrolled client, canonical Host/audience, clock and replay policy separately. |
| Public gateway or meter returns 403 | Distinguish edge policy from origin authentication. Inspect the authorized route and identity; do not widen binds or origins. |
| Local gateway health succeeds but canonical consumer is blocked | Check endpoint precedence, API style, exact model mapping, ingress and retained execution evidence. |
| Counter API works but measured joules are unavailable | Check freshness, same-device continuity, direct counter provenance and the consumer's requested scope. |
| `models[]` is missing or stale | Preserve the empty/unavailable observation; it is not permission to start an inference loop. |
| A service fails after restart | Verify the installed source, launcher identity and that service's documented supervisor. Do not restart unrelated tasks or rewrite DNS. |

Record unresolved boundaries explicitly. None of these diagnostic reads grants
release authority or upgrades Λ-uniqueness beyond Conjecture 1.
