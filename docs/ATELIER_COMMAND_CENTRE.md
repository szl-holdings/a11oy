<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->
# Atelier command centre

This is an additive Python product entry point, not a second publisher or a new
model owner. Source is `szl-holdings/a11oy`; artifact namespace is `SZLHOLDINGS`;
product is `https://a-11-oy.com`; proof is `https://a11oy.net`.

Release order remains protected GitHub source, canonical Hugging Face publication,
then product/proof verification. `hf-sync.yml` is the sole automatic writer to
`SZLHOLDINGS/a11oy`. New routers and their local assets are included by the existing
Dockerfile `COPY routers/` source projection. No DNS, hardware tier, separate model,
dataset, kernel, or read-only `szl-atelier` Space is changed by this integration.

## What is implemented

`/command-centre` and `/a11oy/atelier` provide Work, Operate, Verify, Artifacts and Study.
Existing consoles, model walk, Frontier, fleet, governance and receipt verifier
remain independently available. The shared navigation points to the consolidated
entry point; a link does not grant an action capability.

The response owner sets `Cache-Control: no-store, no-transform`, the existing
product contract that prevents legacy navigation/widget middleware from appending
duplicate UI. This is not a request-header opt-out or an authorization bypass;
API and action guards are unchanged. Full-product regression checks require the
served page body to be byte-identical to its owning source asset.

The manifest and public HF inventory projection are GET/HEAD-only. Inventory counts
come from timestamped `a11oy.net/estate/hf-current.json`, never guessed; stale,
malformed and unavailable snapshots retain explicit states. A public inventory may
include the organization profile Space card and is not a private-estate census or
model qualification result. A source revision reported by the running process
still requires comparison with protected main and byte-attested publication.

Study serves a bounded retained intake at `/api/a11oy/v1/command-centre/study`:
17 deduplicated exact HF revisions from four five-entry popularity/provider
cohorts, with three bounded pinned source-family reviews. No weights were
downloaded, untrusted code executed, or model inference/benchmark performed.
Card-declared licensing, implementation licensing and version-specific weight
licensing remain separate evidence. The pinned protocol proposes independently
authored calibration/held-out tasks and measured selective risk, coverage, latency,
cost and energy; it has no results yet. A model is not admitted by ranking.

Grok is an identified external provider; Jev is the existing TypeSafe System One
typed advisory contract. Muse's user-selected product/model binding remains
unresolved: the current Meta personal agent is a documentation-study candidate,
not a silently selected dependency or an implementation-code audit.

The retained Jev intake reproduces a defect at its declared older baseline:
missing, null or non-finite inverted hazard answers could look maximally safe.
The accompanying source repair validates measurements before inversion, keeps
invalid/missing evidence at zero, and preserves valid hazard inversion. Offline
regressions cover this and bounded/sanitized HTTP behavior (132 targeted cases).
This is software evidence, not independent calibration or live TypeSafe inference.
The standalone payload has a bounded stdlib socket timeout and refuses redirects;
it does not claim the canonical provider transport's whole-call deadline or DNS pinning.

`POST /api/a11oy/v1/atelier/turn` is a separate authenticated single-turn Python
contract. It uses the stable-principal credential registry, existing deterministic
doctrine calculation without preview persistence, a cloud sensitivity floor, and
exact policy allow before egress. A verified canonical DSSE decision receipt must
be persisted before one bounded request to the fixed xAI Responses endpoint.
Its verified signed outcome must be persisted before a completed answer is returned.

The model defaults to `grok-4.7`; `grok-4.6` is the explicit rollback. A caller
override takes precedence over `SZL_GROK_MODEL`, legacy `A11OY_ATELIER_MODEL`, then
the default. Unknown choices are denied before provider work. Low, medium, high
and xhigh reasoning controls are preserved. `store: false` disables xAI's
stateful Responses history for this single-turn route, not its separate API audit
retention. [xAI says](https://docs.x.ai/developers/faq/security) API requests and
responses are retained for 30 days by default unless team-wide Zero Data Retention
is enabled; Atelier has not verified that team setting or the
`x-zero-data-retention` response header. Tools, redirects and private-network
routing are not enabled. Provider timeout is bounded to the existing transport's
maximum and no request is automatically retried.

This interface follows the official [Grok 4.7 developer contract](https://docs.x.ai/developers/grok-4-7).
Grok remains xAI's external inference provider. Only final assistant text is used;
Atelier does not display, persist or replay encrypted provider reasoning or
summaries.
Provider output never authorizes tools or production actions.

## No-provider-key local lane and current open-weight intake

`GET /api/a11oy/v1/atelier/local/health` and
`POST /api/a11oy/v1/atelier/local/turn` are a separate, explicitly labelled
`NO_KEY_LOCAL` lane. They do not use the xAI key or claim to run Grok. The local
turn still requires an `atelier:write` bearer, the same deterministic doctrine
and exact policy allow, a persistent signer, and a durable, verified decision
and outcome chain. It sends at most one bounded request to an operator-configured
literal loopback Ollama endpoint, with redirects forbidden. No answer is released
before a completed signed outcome persists. It does not accept an arbitrary URL,
model, or xAI reasoning-effort setting from the caller. Local output is advisory
and cannot authorize tools or production actions. Health reports configuration,
not a successful inference. The public Hugging Face Space cannot reach a
workstation's `127.0.0.1`; do not expose Ollama to the internet to bridge that
gap.

The signed decision binds the expected local Ollama tag digest. After policy
allow and before the one inference POST, the route reads `/api/tags` from the
same literal loopback host with a bounded, no-redirect GET; a mismatch or
unavailable read gets a signed unavailable outcome and no inference POST. The
outcome labels the digest as **observed before call**, not race-free execution
byte identity. The chat request sets `truncate:false`, so an over-context prompt
is rejected rather than silently shortened while its full-text hash is signed.

The 2026-10-02 bounded public-source review favored [Qwen3.5-4B at immutable
Hub revision `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`](https://huggingface.co/Qwen/Qwen3.5-4B/tree/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a)
for an 8 GB GPU and [Qwen3.5-9B at revision
`c202236235762e1c871ad0ccb60c8ee5ba337b9a`](https://huggingface.co/Qwen/Qwen3.5-9B/tree/c202236235762e1c871ad0ccb60c8ee5ba337b9a)
for a 16 GB GPU. Their cards declare Apache-2.0-licensed open weights. The
[Ollama Q4_K_M tags](https://ollama.com/library/qwen3.5/tags) are about 3.4 GB
and 6.6 GB respectively; these are separate quantized artifacts, not proven
byte-derived from the cited Hub revisions. No quantized local benchmark or
provenance conversion was established here. The installed `qwen3:4b-instruct`
on the 8 GB laptop is the immediate no-download runtime candidate; its exact
Ollama digest is recorded at launch, not silently equated with either Hub
checkpoint. C: free-space pressure precluded a new pull at that snapshot; a
later disk reading does not by itself authorize or qualify a different model.

[GLM-4.7-Flash's 19 GB Q4_K_M tag](https://ollama.com/library/glm-4.7-flash/tags)
does not fit the local storage/VRAM envelope despite only 3B active parameters.
[MiniMax-M2.7's license](https://huggingface.co/MiniMaxAI/MiniMax-M2.7/blob/main/LICENSE)
requires prior written authorization for commercial use, so it is not a
commercial no-key default. Public cards and leaderboards are research inputs;
none qualify an SZL model or establish that our software exceeds them.

## No-provider-key public CPU demonstration

The separate `NO_PROVIDER_KEY_PUBLIC_CPU_LAB` lane uses the existing
[SZL Model Inference Lab](https://huggingface.co/spaces/SZLHOLDINGS/szl-model-inference-lab)
and its pinned Khipu 1.5B GGUF. This is **not** Grok, the workstation's Ollama
runtime, a production-quality model promotion, or anonymous public compute.
The lab's own human-facing page remains available independently. Its API is
unauthenticated and requires no xAI, Hugging Face, or other provider key, but
Atelier's proxy still requires a separate `atelier:write` operator bearer,
exact `PUBLIC` classification, doctrine/policy allow, explicit per-request
acknowledgement that the text may be disclosed to the public lab, a persistent
signer and a durable decision/outcome ledger. Do not put an actual provider
credential in the operator field or send private, regulated, personal, or
secret prompts. Known-secret patterns are rejected as defense in depth, but
classification and pattern checks are not comprehensive data-loss prevention;
the operator must review each exact prompt before submitting it.

`GET /api/a11oy/v1/atelier/cpu-lab/health` is read-only local configuration
health: it does not contact the lab, write a ledger, attest mount durability,
or verify remote identity. A locally ready status is permission to *attempt*
a turn, not proof that the lab is running or can answer.
`POST /api/a11oy/v1/atelier/cpu-lab/turn` is a distinct bounded route. The
server accepts no caller URL or model override, verifies the expected lab
identity after a signed decision, then makes at most one no-redirect HTTPS
inference call. It permits at most 1,200 input characters and 32 output tokens,
while the lab separately enforces an 800 formatted-token prompt ceiling, one
concurrent request and best-effort 45-second budget. Lab rejection, mismatch or
timeout is not retried or silently replaced with another model. Atelier signs
its **observed** decision and outcome; the lab's own execution record remains
**UNSIGNED**. Neither wrapper nor a single successful turn establishes
independent remote-execution attestation, answer accuracy, sustained capacity,
privacy outside this source, or an SLA.

The hosted Space needs `A11OY_ATELIER_CREDENTIALS_JSON` to activate this lane.
The manual enrollment helper below is the scoped way to install that digest-only
registry after exact-main publication and an idle sole writer. The CPU lane
needs no `A11OY_ATELIER_XAI_API_KEY`; the Grok lane still does. A configured
credential or HTTP 200 health response is not functional inference proof:
verify a completed, signed live CPU turn separately. The browser talks only
to same-origin Atelier routes, never directly to the lab, so policy and receipt
checks are not bypassed by the command centre.

## Runtime configuration

Configure through the canonical runtime controller and its secret store, never a
committed key or a chat message:

- `A11OY_ATELIER_CREDENTIALS_JSON`: strict version-one credential registry; active
  credential with stable owner, namespace, key identity and `atelier:write` scope.
- `A11OY_ATELIER_NAMESPACE`: canonical namespace, default `a11oy`.
- `A11OY_ATELIER_XAI_API_KEY`: server-side provider credential; `XAI_API_KEY` is a
  compatibility fallback. This is not the operator credential used by the browser.
- `A11OY_ATELIER_LEDGER_PATH`: explicit absolute path on the verified persistent
  runtime volume. The canonical controller binds
  `/data/a11oy/atelier/turn-receipts-v1.jsonl`; no implicit temporary ledger is
  admitted for a turn.
- `A11OY_ATELIER_REQUIRED_MOUNT`: `/data` in production. The route refuses a
  ledger path outside that attached mount before any provider request.
- Existing shared persistent signer configuration: canonical runtime signing key
  loader and production persistent-signing requirement remain authoritative.
- Optional model variables above. A model list or configured key is not proof of
  available provider credit or successful inference.
- Local-only `A11OY_COMMAND_CENTRE_PREVIEW=1` labels a source preview where uvicorn
  startup is disabled. It is not production readiness and is never a publisher setting.

For the Windows no-provider-key local lane, use the bounded launcher rather than
configuring a cloud provider key. It checks an already installed exact Ollama tag
and its observed digest, then serves a minimal FastAPI app at
`http://127.0.0.1:19090/a11oy/atelier`. It never downloads a model, writes a
Space secret, exposes a LAN listener, or starts the full product's background
services. A current-user DPAPI vault holds the local operator bearer and a
persistent P-256 signer; the running process loads only a digest-only credential
registry and writes signed metadata receipts to LocalAppData. Use the optional
digest argument to pin the installed quantized artifact after reading its
current local digest. The launcher does not harden an independently managed
Ollama daemon: verify its host binding and CORS policy separately.

```powershell
py -3 -B scripts/run_local_atelier.py --serve --expected-model-digest <64-character-local-Ollama-digest>
# In another terminal, when you are ready to paste into the local page:
py -3 -B scripts/run_local_atelier.py --copy-operator-token
```

The explicit copy action puts the bearer on the Windows clipboard transiently;
paste it into the **local** operator field and clear the clipboard afterward.
Never put it in a URL, chat, issue, commit, or browser storage. The local server
and receipt chain are a workstation preview, not evidence of public Space or
domain deployment. A signed completed local turn is still not model-quality
qualification or proof of factual correctness.

The browser holds the operator credential only in page memory and provides a
Forget control. It does not retain it in browser storage or put it in a URL. The
provider key is never requested by the browser. Configuration health is read-only,
always `inference_verified:false`, and cannot create a ledger or mint a signature.
Its ledger flag checks the required mount when configured; a receipt write and
restart recovery are still required to demonstrate durability.

### Manual operator enrollment

`scripts/enroll_hf_atelier_operator.py` is a Windows-only, manually invoked
services-layer helper for one **new** Atelier credential. It is not part of
`hf-sync.yml`, does not publish source, and does not install an xAI provider key.
Run it only from a clean protected-main checkout after exact-main publication.
Its read-only plan checks current GitHub main, a successful latest `hf-sync.yml`
run at that SHA, and the canonical Space revision and secret-name metadata.
It uses a one-row, `total_count`-checked workflow-run query for the exact
protected-main SHA, plus separate status-filtered queries for `queued`,
`in_progress`, `requested`, `waiting`, `pending`, and `action_required`. This
avoids an unrelated completed-run backlog hiding an older live writer. These
multiple reads are not atomic; a passing snapshot is not a global lock or an
exact-HF-byte attestation. It refuses a
registry visible in either precheck because the Hub does not reveal its secret
value for a safe merge or rotation. Hub secret writes have no compare-and-set:
a concurrent actor can create or replace the same name after the last precheck,
so this helper cannot guarantee that it never overwrites a concurrent write.

```powershell
py -3 -B scripts/enroll_hf_atelier_operator.py plan
py -3 -B scripts/enroll_hf_atelier_operator.py apply --expected-main-sha <plan-protected_main_sha> --expected-space-sha <plan-space_sha> --key-id atelier-operator-YYYYMMDD
```

`apply` rechecks both revisions and the writer before and after local vault
creation. It generates a fresh 48-byte random bearer, puts the raw value only
in a current-Windows-user DPAPI vault under `%LOCALAPPDATA%\SZL Holdings\A11oy`,
and installs only its SHA-256 digest in a strict version-one
`A11OY_ATELIER_CREDENTIALS_JSON` Space secret. It never prints the bearer. The
vault uses exclusive creation and is preserved if a provider call has an
ambiguous outcome; do not retry by deleting or overwriting it. After waiting
for Hub metadata to settle, inspect the secret name. If it remains absent,
take a fresh `plan` snapshot and explicitly use `resume` with the same key ID
and newly observed SHAs. `resume` decrypts the same DPAPI vault, rechecks the
idle writer and secret-name absence twice, and resubmits the same digest-only
registry; it never generates a new bearer or proceeds while a registry is
visible in its prechecks. A concurrent external writer remains a race without
a Hub CAS, so this is a manual recovery path, not an automatic retry.

```powershell
py -3 -B scripts/enroll_hf_atelier_operator.py resume --expected-main-sha <fresh-plan-protected_main_sha> --expected-space-sha <fresh-plan-space_sha> --key-id atelier-operator-YYYYMMDD
```

A reported
`SECRET_NAME_PRESENT_DIGEST_UNVERIFIED` is secret-name readback, not a tested
browser login or successful model call. Rotation of an existing secret is a
separate governed operation.

For a deliberate browser handoff, the local operator may run:

```powershell
py -3 -B scripts/enroll_hf_atelier_operator.py copy --key-id atelier-operator-YYYYMMDD --acknowledge-clipboard-risk
```

`copy` first checks current protected-main publication, idle publisher, Space
revision, absence of a variable collision, and presence of the registry secret
name. It checks them again after decrypting the vault and refuses to copy on a
revision change or vanished name. This prevents a held or failed install with
no visible remote secret from silently becoming a browser handoff. A secret
name cannot prove that its hidden value contains this vault's digest, that it
has not been concurrently replaced, or that login will succeed; the command
reports `NAME_PRESENT_DIGEST_UNVERIFIED` and does not claim readiness.

After those checks, `copy` places the bearer on the Windows clipboard without
writing it to stdout, arguments, a URL or the repository.
Paste it into the command centre's in-memory operator field, then replace the
clipboard contents with nonsecret text and use Forget when finished. Clipboard
history, sync and manager software may still retain a copy; disable or account
for them before using `copy`. DPAPI protects the bearer at rest against other
Windows users, not against compromise of the current account or process memory.
Do not paste the bearer in chat, issues, logs or scripts. A real authenticated
governed turn and signed receipt still require separately installed provider
authority and live verification.

## Bounds and honest status

Source and local verification are not publication or provider proof. On the last
local Grok Build canary recorded in the platform proof packet, requested 4.7 was
refused with HTTP 402 for exhausted usage balance. The canonical Python runtime
was also observed without an xAI credential. No live successful answer is claimed.

Python continuity is `SINGLE_TURN_NO_SERVER_TEXT_HISTORY`. The encrypted TypeScript
Turn Capsule remains in the separately released platform source. Metadata-only
receipt storage is not an encrypted conversation database. Its rotating retained
chain and concurrency guard are scoped to one process; distributed coordination,
automatic paid-request replay and archival retention are not claimed.

Plaintext prompts, answers, bearer credentials, provider keys and provider reasoning
are excluded from this receipt ledger. Prompt/answer hashes remain content-derived
integrity metadata, not anonymization or a privacy guarantee. Retention rotation
evicts old segments and does not establish archival completeness. Energy is
UNAVAILABLE unless a serving engine's measured exporter delta exists.

Close inference only after a real authenticated governed turn, canonical signature
verification and persistent outcome receipt. Close deployment only after the
publisher attests the exact merged source and HF bytes, followed by live probes of
the product and proof surfaces. Neither navigation, HTTP 200, a model ranking nor
a RUNNING Space closes those gates.
