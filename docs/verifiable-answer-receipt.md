# SZL Verifiable Answer Receipt (v1)

An open, minimal format for a **third-party-verifiable answer**: a single signed object that
binds, in one place, *the question asked → the sources retrieved → the answer given → the
honesty checks that passed*, so anyone can verify the whole governed-inference chain **offline,
without trusting the producer**.

This is the composition the 2025–2026 governed-inference literature identifies as the
highest-leverage move: pairing **provenance-bound serving** with a **signed inference receipt**,
plus grounding (citation) and abstention (refusal-to-fabricate) as first-class, checkable
fields. It draws on the shape of the IETF *Enforcement Attestation Receipts* draft and Sigstore
model-transparency, but reduces them to a single, honest, self-describing JSON object.

> **A valid signature proves INTEGRITY, not TRUTH.** It proves the chain was assembled by the
> key holder and is unaltered since. It does **not** prove the answer is correct, true, or
> non-hallucinated. That distinction is stated inside every receipt and is the core honesty
> discipline of this format.

## Why this is missing

Production AI answers today are unverifiable after the fact. You cannot, as an outside party,
check what model actually answered, what it retrieved, whether its claims were source-bound, or
whether it would have refused an unanswerable question — let alone prove none of it was altered.
Trust is asserted ("we tested it"), never demonstrated. This format makes the whole chain a
portable artifact you can verify yourself.

## The object

```jsonc
{
  "schema": "szl.brain.verifiable-answer-receipt/v1",
  "bound": {
    "schema": "szl.brain.signed-inference-receipt/v1",
    "model_id": "<served model id, immutable repo@revision>",
    "request_sha256": "<sha256(question)>",
    "sources_count": 3,
    "sources_sha256": "<sha256(ordered sources joined by \\n)>",
    "per_source_sha256": [{ "sha256": "..." }],   // membership of each source is checkable
    "output_sha256": "<sha256(canonical composed verdict)>"
  },
  "content_sha256": "<sha256(canonical bound object)>",
  "signature_algorithm": "ecdsa-p256-sha256",
  "signature_b64": "<base64 ECDSA-P256 signature over the canonical bound object>",
  "signed": true,
  "key_source": "persistent:env:… | ephemeral | unavailable",
  "public_key_pem": "-----BEGIN PUBLIC KEY-----…",
  "proves": "integrity + key continuity only",
  "does_not_prove": "that the output is correct, true, or source-supported"
}
```

The **composed verdict** that the receipt binds (as its signed `output`) carries the honesty
readings the receipt attests to the integrity of:

```jsonc
{
  "question": "...",
  "assurance_level": "VERIFIABLE-GROUNDED | VERIFIABLE-PARTIAL | VERIFIABLE-WEAK | UNVERIFIABLE-NO-MODEL",
  "components": {
    "served_model":  { "label": "MEASURED|UNAVAILABLE", "verdict": "SERVING-EXPECTED|PROVENANCE-MISMATCH|UNAVAILABLE", "provenance_matches_expected": true },
    "citation":      { "label": "MODELED", "verdict": "FULLY-CITED|PARTIALLY-CITED|UNCITED-DOMINANT|NO-CITABLE-CLAIMS", "citation_coverage": 1.0 },
    "refusal_eval":  { "label": "MEASURED|UNAVAILABLE", "verdict": "REFUSAL-HONEST|PARTIAL-REFUSAL|FABRICATION-DETECTED|UNAVAILABLE", "refusal_rate": 0.97 }
  },
  "weakest_link": "<the component that limits the verdict — always named>"
}
```

## Assurance derivation (deterministic, never above what components earned)

| served model | citation | refusal eval | assurance_level |
| --- | --- | --- | --- |
| UNAVAILABLE | any | any | `UNVERIFIABLE-NO-MODEL` |
| MEASURED | UNCITED-DOMINANT **or** eval FABRICATION-DETECTED | — | `VERIFIABLE-WEAK` |
| MEASURED | FULLY-CITED | REFUSAL-HONEST | `VERIFIABLE-GROUNDED` |
| MEASURED | anything else | anything else | `VERIFIABLE-PARTIAL` |

`assurance_level` is a **MODELED** composition — a transparent function of honest component
readings, never a proof of correctness. The **weakest link is always named** so the verdict is
never opaque.

## How to verify a receipt (offline, no trust in the producer)

1. Recompute the canonical `bound` object (sorted keys, compact separators) and `sha256` it;
   confirm it equals `content_sha256`.
2. ECDSA-P256-SHA256-verify `signature_b64` against `public_key_pem` over the canonical bytes.
3. Optionally confirm any source you hold was in the corpus by checking its `sha256` against
   `per_source_sha256`.
4. Read `assurance_level` and `weakest_link` — remembering a valid signature is **integrity, not
   truth**.

A PASS means: this exact `(question, sources, answer, honesty-readings)` tuple was receipted by
the holder of `public_key_pem` and has not been altered. Nothing more, nothing less.

## Honesty invariants (non-negotiable)

- `assurance_level` is never reported above what the components earned.
- No live model → `UNVERIFIABLE-NO-MODEL`; a live answer cannot be verified without one.
- No component is fabricated: an `UNAVAILABLE` reading stays `UNAVAILABLE`.
- `key_source` is reported honestly: a container-ephemeral key is labeled as such (`UNSIGNED-LOCAL`
  in intent), never dressed up as a persistent identity.
- A signature proves integrity, not truth — stated in every receipt.

## Reference implementation

- Composition + signing: `szl_brainverdict.py` (`sign_verdict`, `compose`)
- Signature + verification: `szl_brainreceipt.py` (`sign_receipt`, `verify_receipt`)
- Components: `szl_brainserve.py` (provenance), `szl_braincite.py` (citation), `szl_braineval.py` (refusal)
- Live endpoint: `POST /api/a11oy/v1/brain/verdict/sign` (body `{ "q": "...", "k": 6 }`)

Licensed Apache-2.0. Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>.
