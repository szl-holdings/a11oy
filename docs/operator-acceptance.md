<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->
# Operator observations and offline verification

The operator runner captures bounded HTTP observations from the canonical A11oy
origin. The offline verifier checks the captured source identity, nonce, bytes,
time window and route semantics. Evidence stays **REPORTED**, unsigned and
ineligible for publication. A complete five-contract execution qualification
remains **BLOCKED**.

## Requirements

- Python 3.10 or later and curl 8.4 or later on PATH. No Python package install
  or model download is needed. The regression suite uses pytest.
- A new output directory outside the checkout, with an existing parent.
- The exact expected deployed GitHub revision, read independently from the
  canonical publication receipt. The runner compares the runtime's reported
  identity with this revision before and after requests. This comparison does
  not authenticate an image, HF commit, runtime boot or publisher.

No API key, signing key, browser login or paid model service is used. The
explicit execution flag admits exactly the three fixed cases below; it cannot
admit evaluation, agent-loop execution, arbitrary payloads or another origin.

| Case | Request and observable effect | Verification scope |
| --- | --- | --- |
| Policy decision | One `noop`, explicit test axes `[0.97]`, fresh nonce | An allow decision and one matching new in-memory feed entry, including its correlation hash. No action execution or DSSE signature is asserted. |
| Operator answer | Fixed question about the locked eight formulas | Exact cited identifiers, grounded response and recomputed unsigned receipt payload digest. The answer is local platform data; no model inference occurs. |
| Compliance lookup | `framework: NIST` | Bounded retrieval of the declared compliance response. Historical bundled data is not a fresh audit or certification. |
| Evaluation | **NOT ATTEMPTED** | **BLOCKED** pending an admitted model, native receipt verification and bounded execution adapter. MODELED evaluation cannot substitute. |
| Agent loop | **NOT ATTEMPTED** | **BLOCKED** pending native receipt admission and enforced internal model-call, retry and fallback budgets. `max_retries: 0` alone does not bound internal calls. |

## Run

From the repository root, first perform GET-only preflight:

```powershell
$sourceRevision = Read-Host 'Exact deployed 40-character GitHub revision'
python -B tools/operator_acceptance_run.py --expected-source $sourceRevision --out C:\a11oy-evidence\preflight-001
```

Then explicitly admit one no-op decision and two static lookups using a **new**
directory. The policy decision creates one in-memory audit-feed entry.

```powershell
python -B tools/operator_acceptance_run.py --expected-source $sourceRevision --out C:\a11oy-evidence\operator-001 --execute-observational-cases
```

Both commands return **2** while full acceptance remains blocked. This is
intentional: recording three scoped observations is not five-contract success.
An invalid invocation or failure before a capture can be retained returns **1**.

Each run writes:

- `journal.jsonl`: hash-linked, fsynced intent before dispatch and outcome
  observations. It is unsigned. File fsync does not establish crash durability
  of the directory entry on every filesystem.
- `observation.json`: five cases, captured JSON response objects, before/after
  reported build identity and policy feed readback.
- `verification.json`: semantic results and explicit remaining blocks.
- `receipt.json`: local artifact hashes, nonce, source and the unsigned boundary.

Retain the run's printed source, nonce and observation SHA-256 in a separate
review record. A local hash list is not an independently admitted authority.

## Verify without network access

Supply expectations from that separate record, not by trusting fields inside
the artifact under review:

```powershell
$expectedNonce = Read-Host 'Nonce retained from the reviewed run'
$expectedHash = Read-Host 'Observation SHA-256 retained from the reviewed run'
python -B tools/operator_acceptance_verify.py C:\a11oy-evidence\operator-001\observation.json --expected-source $sourceRevision --expected-nonce $expectedNonce --expected-sha256 $expectedHash
```

The verifier rejects changed bytes, unknown fields, duplicate JSON keys,
non-finite values, foreign origins, mismatched revisions/nonces, missing or
reordered cases, repeated policy IDs, stale/future observations, unsupported
model execution and observations after an ambiguous effect. The observation
window is 15 minutes; older captures remain historical records and cannot be
re-admitted as fresh evidence. Reverification never sends a request.

Exit **2** means a structurally valid partial capture still has blocked required
contracts. Exit **1** means verification failed. Neither result clears release
readiness. Unsigned JSON and a matching unkeyed digest establish consistency
with retained expectations, not who produced the evidence.

## Failure and recovery

The transport uses a fixed HTTPS origin, fresh curl processes, HTTP/1.1, no
redirect following, no retries, no proxy/config inheritance, a 30-second network
deadline and bounded response bodies. HTTP/1.1 avoids the HTTP/2 refused-stream
retry path. No credentials are read or sent. Responses never become executable
commands, paths or follow-up URLs.

After dispatch, an invalid response, source mismatch or failed readback leaves
the effect **UNKNOWN** and stops subsequent POSTs. A successful HTTP status alone
does not pass a case. Existing output directories are refused; there is no
resume or retry command. If interrupted after `post_intent`, preserve the
journal, treat that request's occurrence as **UNKNOWN**, and inspect the feed
using the retained nonce before considering a separately authorized new run.
Never delete the failed capture to make a rerun look like the first attempt.

## Release integration boundary

The passive readiness observer, its five required `NOT_PROBED` rows, compact
publisher and canonical relock gates are unchanged. This capture is not the
DSSE execution-observation bundle proposed in PR #2844. The missing bridge must
independently admit authority/runtime keys, bind source/HF revision/boot/nonce,
consume authorization durably, enforce native execution budgets, validate the
native receipts and retain request-specific readback. Only then may a separate
composite consumer combine passive and genuine execution coverage.

The existing networkless `tools/readiness-harness/effect_acceptance.py` remains a
**SIMULATED** rehearsal. Its modeled eval and agent-loop refusal cannot close
live execution coverage.
