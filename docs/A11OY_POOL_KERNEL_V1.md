# A11oy Pool Kernel v1

## Decision

The A11oy pool is a deterministic control-plane kernel, not a foundation model.
It admits, qualifies, routes, retries, and records inference performed by other
models. A learned router may later propose a ranking, but it may never override
identity, policy, license, quarantine, or receipt gates.

The public products remain separate:

- `a11oy.net` is the orchestration and evidence-qualified pool control plane.
- `a-11-oy.com` is the Holographic/Brain flagship experience.
- Killinchu is the defense-facing product surface.

No domain should silently canonicalize into another product.

## Monotone lifecycle

```text
DECLARED -> CONFIGURED -> REACHABLE -> DISCOVERED -> QUALIFIED -> SERVING
```

Only `QUALIFIED` and `SERVING` may emit `ready=true`. Promotion requires current
reachability and a fresh, bounded, cryptographically verified inference receipt
that binds the exact model digest. A configured endpoint or successful TCP probe
is never sufficient.

The verifier requires a dedicated pool-attester public key plus its independent
SHA-256 pin (`A11OY_POOL_RECEIPT_PUBLIC_KEY_PEM` and
`A11OY_POOL_RECEIPT_PUBLIC_KEY_SHA256`). The estate-wide receipt key is not a
pool-qualification authority. If either pool trust-root value is absent or does
not match, every receipt remains ineligible.

Safety is an orthogonal overlay:

```text
HEALTHY | DEGRADED | CIRCUIT_OPEN | QUARANTINED
```

An `UNKNOWN` hard fact is ineligible. An unknown soft metric receives no routing
utility; it is never replaced with a fabricated average, zero cost, or "free"
label.

## Receipt basis

A route receipt should bind hashes and identifiers, not raw sensitive content:

- source commit and deployed artifact/build digest;
- policy and formula-registry digests;
- request and response commitments;
- candidate snapshot plus explicit exclusions;
- measured routing inputs and the selected candidate;
- attempts, failover decisions, and exact served model digest;
- bounded latency/token/resource telemetry.

The current Python/Hugging Face route is a projection over the existing fabric
probe. It is not evidence that the separate TypeScript/Replit control plane has
been deployed.

## Formula use

Formal results constrain the kernel; they do not make the router itself a proof
or a model:

- replay determinism binds identical evidence to identical decisions;
- absorbing deny prevents a failed hard gate from being averaged away;
- non-interference keeps excluded candidates from changing the winner;
- tamper evidence and monotone audit rules protect the receipt chain;
- fallback rules constrain retries and terminal failure;
- calibrated bounds may inform ranking only after measured calibration.

Lambda/F23 remains advisory Conjecture 1 and is not an admission gate or routing
optimizer.

## Open reference lineage

These projects are design references, not copied product identity:

- Envoy AI Gateway: <https://github.com/envoyproxy/ai-gateway>
- Kubernetes Gateway API Inference Extension: <https://github.com/kubernetes-sigs/gateway-api-inference-extension>
- vLLM: <https://github.com/vllm-project/vllm>
- SGLang: <https://github.com/sgl-project/sglang>
- RouteLLM: <https://github.com/lm-sys/RouteLLM>
- Open Policy Agent: <https://github.com/open-policy-agent/opa>
- in-toto Attestation Framework: <https://github.com/in-toto/attestation>

The A11oy contribution is the evidence-qualified lifecycle, fail-closed formula
constraints, exact served-identity receipts, and honest separation between
declared capability and measured service.

## Repository authority map

- `a11oy`: public flagship API/UI and this Python/HF projection.
- `szl-router`: sole OpenAI-compatible routing authority.
- `szl-mesh`: discovery and fleet substrate.
- `governed-receipt-spec`: canonical receipt schema and verifier.
- `szl-energy-attest`: canonical energy-accounting kernel.
- `szl-telemetry`: read-only public telemetry observations.
- `szl-forge`: model training and artifact qualification lifecycle.
- `immune`: security guardrail service.
- `killinchu`: separate defense product.

Machine Innovate/Replit source should be recovered into an SZL-owned control-
plane repository before it is treated as aligned with this map.

## Promotion evidence

The system is not "fully operational" until the deployed control plane provides
all of the following from the same build:

1. immutable source/build/deploy attestation;
2. replayable database migrations;
3. authenticated, bounded real inference through at least one qualified node;
4. exact served-model identity and signed route receipt;
5. circuit-breaker/failover and negative-path regression evidence;
6. responsive/accessibility checks for every control-plane tab;
7. post-deploy readback showing source/deployment alignment.
