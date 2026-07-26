# Why TEE attestation first, and when zkML belongs

Status: **MODELED decision record**
Last reviewed: 2026-07-25

This document records an engineering choice, not a claim that a11oy currently has a
verified confidential-compute deployment. The checked-in runtime has no fresh
hardware quote, trusted-verifier result, or locally reproduced performance benchmark.
Those capabilities remain **ROADMAP** until a real node produces reviewable evidence.

## Decision

Use verified TEE attestation for frequent governed inference and reserve zero-knowledge
ML proofs for settlement-critical or externally disputed computations.

The choice is workload-specific:

| Requirement | Verified TEE | zkML |
|---|---|---|
| Protect model and input during execution | Hardware-isolated execution plus attestation | Possible when the circuit and witness design preserve the required secrets |
| Prove a specific computation to a party that does not trust the operator | Trusts the hardware, manufacturer root, verifier, and reference measurements | Cryptographic proof of the encoded computation |
| Support changing model graphs and general runtimes | Usually lower integration friction | Circuit compilation, supported operators, quantization, and proving resources must be qualified |
| Frequent low-latency inference | Candidate, subject to measured deployment overhead | Not selected until local proving latency and cost meet the release budget |
| Settlement or public dispute resolution | Useful operational evidence | Preferred when independent computation correctness is the controlling requirement |

## Evidence behind the decision

- AWS Nitro attestation documents are CBOR-encoded, COSE-signed, include PCR
  measurements and an optional nonce, and require certificate-chain and signature
  validation by the relying party. Debug-mode PCRs are zero and are not acceptable
  evidence. See the [AWS attestation specification](https://docs.aws.amazon.com/enclaves/latest/user/verify-root.html)
  and [cryptographic attestation guide](https://docs.aws.amazon.com/enclaves/latest/user/set-up-attestation.html).
- NVIDIA describes CPU/GPU attestation as a precondition for releasing secrets to a
  confidential workload and documents supported confidential-compute GPU
  prerequisites. See [NVIDIA confidential-container attestation](https://docs.nvidia.com/datacenter/cloud-native/confidential-containers/1.0.0/attestation.html)
  and the [NVIDIA Attestation SDK requirements](https://docs.nvidia.com/attestation/attestation-client-tools-sdk/latest/gpu_and_switch_attestation.html).
- zkLLM reports a proof-generation time below 15 minutes for a 13-billion-parameter
  model in its evaluated configuration. This is a paper result, not an a11oy
  measurement. See [zkLLM](https://arxiv.org/abs/2404.16109).
- Newer work continues to reduce proving costs but does not remove the need for
  workload-specific qualification. ZKTorch reports up to a 6x proving-time speedup
  over a general-purpose framework, while NANOZK evaluates compact transformer
  configurations and reports 24 ms verification for its layer proofs. These are
  author-reported results, not locally reproduced measurements. See
  [ZKTorch](https://arxiv.org/abs/2507.07031) and
  [NANOZK](https://arxiv.org/abs/2603.18046).
- EZKL supports ONNX-to-zkSNARK workflows and explicitly notes that circuit
  quantization can make outputs differ from the source framework. See the
  [EZKL project documentation](https://github.com/zkonduit/ezkl).

## a11oy release policy

### Frequent governed inference

The public GET remains unsigned and cannot invoke external verification. An
authorized state-changing caller may release a high-consequence inference only
when the receipt contains:

1. `schema = szl.tee-attestation/v2`;
2. a raw-quote digest bound to the request nonce and workload;
3. a recognized hardware type;
4. `verified = true`;
5. a named trusted verifier and `verified_at` timestamp;
6. `evidence_tier = MEASURED_VERIFIED`; and
7. a matching allowlisted reference measurement.

A readable report without chain verification is only **SAMPLE**. Missing,
expired, debug-mode, malformed, replayed, or unverified evidence is a hard block for
high-consequence release. Intel TDX verification additionally requires a
request-bound TD Quote obtained through Intel `libtdx-attest`, which sends the
hardware TDREPORT to the same-host Quote Generation Service and returns the
Quoting Enclave-signed Quote. A local TDREPORT or configfs-TSM report is never
relabeled or submitted as remotely verifiable evidence. Verifier timestamps
strictly after the relying party's current time remain unverified. AWS Nitro's
all-zero debug PCR0 is rejected before allowlist matching, so operator
configuration cannot promote debug-mode evidence.

### Settlement-critical inference

Add a zkML proof when the cost of trusting the hardware/operator boundary is higher
than the proving cost, such as:

- a disputed allocation or payment;
- a regulator- or customer-verifiable model execution;
- a public challenge where the verifier cannot rely on the deployment operator; or
- a compact, stable model whose circuit has been independently reviewed.

TEE and zkML may be composed: the TEE protects a general workload during routine
operation, and a zkML proof settles selected claims.

## Promotion gates

No zkML or verified-TEE production claim is allowed until the relevant row has a
fresh evidence artifact:

| Gate | Required evidence | Current label |
|---|---|---|
| Real TEE node | Raw quote digest, verifier result, reference measurements, nonce/freshness check | ROADMAP |
| TEE overhead | Baseline and confidential-mode runs on the same pinned workload and hardware | ROADMAP |
| zkML compatibility | Pinned model/operator inventory, circuit build, quantization delta | ROADMAP |
| zkML performance | Prover/verifier time, memory, proof size, hardware, versions, and raw logs | ROADMAP |
| Independent review | Reviewer identity and approval outside the author account | ROADMAP |

The decision is revisited when those artifacts exist. Until then, repository tests
prove only the fail-closed software contract.
