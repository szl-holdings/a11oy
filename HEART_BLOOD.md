# HEART + BLOOD — the receipt heartbeat (`szl_heart_blood.py`)

Formalizes the agentic-GPU "heartbeat": every GPU / energy action emits a **HEART**
receipt on a σ-algebra receipt bus, and **BLOOD** signs + carries it as a hash-linked
DSSE-Merkle envelope. This makes the energy provenance chain (PR #331) the literal
heartbeat of the anatomy shell — every beat is a verifiable receipt.

- Module: `szl_heart_blood.py` (disjoint, additive — WRAPS #331, never rewrites it).
- Endpoint: `GET /api/a11oy/v1/heart/pulse` → latest beats + a `verify()` result.
- Self-test: `python3 szl_heart_blood.py` → prints `"ok": true`. No network, no server.

## Proven backing (lutar-lean round9, kernel)

| Organ | Proven formula (round9) | What this module implements |
|---|---|---|
| HEART | **HeartReceiptSigma** | The receipt bus is a **σ-algebra** over the sample space Ω of GPU/energy events: contains ∅ and Ω, closed under complement and (finite) union, hence under intersection (de Morgan). Each beat is a measurable singleton event; composing beats by ∪/∩/complement stays in the algebra. |
| BLOOD | **BloodDSSEMerkle** | A **DSSE** envelope (payload, payloadType, signatures over **PAE**) per beat, hash-linked into a **Merkle chain** (`prev_beat_hash == prior.beat_hash`). A flipped byte breaks the PAE → digest/signature/link mismatch → `verify()` fails. |

### σ-algebra closure (HEART)
For the finite sample space Ω = {beat ids}, the σ-algebra is the powerset of Ω. The bus
demonstrates the axioms in `SigmaReceiptBus.closure_report`:
1. ∅ ∈ 𝓕 and Ω ∈ 𝓕,
2. closed under complement: Aᶜ = Ω \ A,
3. closed under finite union: ⋃ᵢ Aᵢ (and the union of all beat-sets equals Ω),
4. closed under intersection via de Morgan: `(A ∪ B)ᶜ == Aᶜ ∩ Bᶜ`.

### DSSE PAE (BLOOD)
Pre-Authentication Encoding (DSSEv1), byte-identical to the repo's `szl_dsse.pae`:

```
PAE(type, body) = "DSSEv1" SP LEN(type) SP type SP LEN(body) SP body
beat_hash       = sha256( PAE(payloadType, canonical_json(payload)) )
```

## Live HEART / BLOOD endpoints this mirrors (read-only, real)

- **HEART**: amaru `/api/amaru/receipts` + sentra `/api/sentra/khipu/ledger`
- **BLOOD**: sentra `/api/sentra/khipu/sign`

## Signing doctrine — SAMPLE placeholder, NO real key

- **NO real signing key is committed.** Signing is a documented **PLACEHOLDER**:
  `HMAC-SHA256` over the DSSE PAE, keyed by a clearly-labeled SAMPLE string
  (`keyid = "SAMPLE-LOCAL-DIGEST-NO-COSIGN-KEY"`). Every spot a real cosign / Cardano
  cosign key would go is marked `SAMPLE` with a comment.
- The result is **TAMPER-EVIDENT** (a flipped byte breaks verification) — it is **NOT**
  claimed to be cryptographically "signed" / "measured" / "notarized". Label stays
  SAMPLE / tamper-evident. A real BLOOD signer replaces the SAMPLE branch with cosign /
  Cardano ECDSA over the **same** PAE bytes.
- **joules / energy figures are SAMPLE/ESTIMATE** until metered. **open-weight** only.
  **Λ stays Conjecture 1.** Pure stdlib (`hashlib`, `hmac`, `json`); no network.

## Self-test (`_selftest()`) proves

1. several beats emitted from real provenance receipts (#331);
2. the σ-algebra bus composition holds (∅ + Ω present, closed under complement +
   union, union of beats = Ω, de Morgan);
3. BLOOD signs the beat chain (SAMPLE placeholder digest) and `verify()` is valid;
4. tampering one beat (or one signature byte) → `verify()` FAILS (the tamper is caught).

`"ok": true` only when all pass.

## Dependency

Builds on **#328** (`szl_energy_budget.py`) and **#331** (`szl_energy_provenance.py`).
This branch is based on the default branch (`main`); the provenance chain is not yet
merged there, so the module imports `szl_energy_provenance.EnergyProvenanceChain`
**defensively** (try/except) to source real beats when #331 is present, and carries a
byte-shaped local fallback so it self-tests standalone — no network, no #331 required.
The `serve.py` registration is likewise try/except-guarded: if `szl_energy_provenance`
or `szl_heart_blood` is absent, the service logs and boots unaffected.
