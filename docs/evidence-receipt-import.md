<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Offline evidence receipt import

`szl_evidence_receipts.py` belongs to the **provenance** layer. It converts bounded local JSON receipt bytes into sanitized observations for the existing Canonical Evidence Graph. It never fetches a URL, loads provider credentials, signs, or authorizes execution.

## Claim boundary

The importer checks that the supplied SHA-256 equals the exact receipt bytes. This establishes byte agreement with a caller-supplied digest, not authenticity. The caller supplies the artifact URL, observation time, and whether the artifact is a training or evaluation receipt. The importer validates their format but does not independently verify their assertions.

Every imported edge remains `OBSERVED`, has `execution_authorized=false`, and reports `signature_status=UNVERIFIED` and `claims_verified=false`. A receipt that reports `verdict=VERIFIED` produces only `reported_verdict=VERIFIED`; it does not upgrade the edge. Source revision is deliberately null, runtime identity is empty, and parents are empty. Import does not establish DAG lineage, cryptographic verification, energy measurement, current readiness, or model promotion.

Only these reported metadata fields can be retained:

- Schema, reported receipt kind, and bounded verdict/status labels.
- Safe model, base, and adapter identifiers.
- The immutable artifact URL, observation timestamp, byte digest, and explicit observer classification.

Prompts, outputs, result arrays, arbitrary metadata, signature bytes, credentials, and private fields are omitted. Secret-like identifier prefixes and unsafe free text are rejected from the metadata allowlist. This is minimization, not a general-purpose secret detector; input receipts and immutable references must still be appropriate for publication.

## Contract

```python
from szl_evidence_receipts import import_receipt, build_bundle, decode_bundle

edge = import_receipt(
    raw_bytes,
    expected_sha256=expected_sha256,
    artifact_uri=immutable_hf_url,
    kind="evaluation",
    observed_at="2026-11-16T22:57:52Z",
)
bundle = build_bundle([edge])
```

The accepted URLs are HTTPS Hugging Face model or dataset `resolve/<40-hex-commit>/...` URLs. Userinfo, ports, query parameters, fragments, percent escapes, path traversal, mutable branch names, and arbitrary hosts are rejected. URLs are recorded but never fetched.

Receipt and bundle input is capped at 1 MiB; bundles contain at most 128 edges. JSON rejects duplicate keys, nonfinite numbers (including exponent overflow), invalid UTF-8, and nesting beyond 32 levels. Hash checking occurs before receipt parsing. Observation timestamps must include a timezone and are normalized to UTC.

The bundle schema is `szl.evidence-bundle/v1`, with `signature_status=UNSIGNED`. `digest_sha256` hashes canonical UTF-8 JSON of exactly `{schema, signature_status, edges}`, excluding the digest field itself. Edges are deduplicated and sorted by receipt ID. Decoding checks the bundle digest, edge IDs, strict observation profile, and bounds. A rehashed bundle cannot smuggle extra fields or authority claims through this profile; anyone can still recompute an unsigned digest, so it is not authentication.

## Offline CLI

Create a manifest alongside a local copy of the receipt:

```json
{
  "schema": "szl.evidence-import-manifest/v1",
  "receipts": [
    {
      "path": "x402-v2-diff-eval.json",
      "expected_sha256": "191f3f6b15394561dd584c69ad789b9d4d9de174c6f8d488ee5dd1892d889f46",
      "artifact_uri": "https://huggingface.co/datasets/SZLHOLDINGS/frontier-54-runs/resolve/d8496a48f8316f1fdeecbf73fc09f2e0db992ec6/mesh/evals/x402-frontier-v2-diff-eval-20261116T114256Z.json",
      "kind": "evaluation",
      "observed_at": "2026-11-16T22:57:52.783174+00:00"
    }
  ]
}
```

```bash
python scripts/import_evidence_receipts.py --manifest receipt-manifest.json --output evidence_graph_receipts.json
python -m pytest -q tests/test_evidence_receipts.py
```

The CLI validates every receipt before creating output, checks the bundle again, writes a temporary file beside the output, flushes it, and atomically replaces the destination. Failed validation preserves any previous bundle. It will not overwrite an input receipt or manifest, or resolve an explicit network path. The summary contains only state, edge count, digest, and false execution authority; failure output omits raw input and local paths.

This CLI writes an explicitly unsigned derived artifact. The normal governed publication workflow remains responsible for publishing reviewed files. A read-only route may load a reviewed bundle once at registration and expose it as observation evidence; reads must not import, mutate, sign, fetch, or promote it.


## Reviewed release catalog

The adjacent `evidence_graph_receipts.json` release artifact currently contains two public observations. Both immutable URLs were read back successfully and their exact byte digests matched before inclusion:

| Artifact | Immutable repository revision | Receipt SHA-256 |
| --- | --- | --- |
| x402 v1 training result | `841209a08de087400b56c288d090d6df58f8b06d` | `ff11fd7996d15df46e7944b728dd150b45a64271735aa0e8a622a41f06787a5e` |
| x402 v2 differential evaluation | `d8496a48f8316f1fdeecbf73fc09f2e0db992ec6` | `191f3f6b15394561dd584c69ad789b9d4d9de174c6f8d488ee5dd1892d889f46` |

The v1 training receipt was assembled from Hub artifacts after a worker exited with an already-complete result. Its completing boot and wall time were not reconstructed, and its energy was not measured. Including its exact bytes is an observation of that historical receipt, not verification of the training execution. The differential evaluation remains an artifact with reported results, not production qualification or a model promotion. Private v5 receipt data is excluded.

The default graph and query routes load this fixed catalog once at registration. Missing or invalid catalog data is exposed as unavailable; historical receipts cannot establish a missing runtime identity. To add observations, rebuild and review the release artifact through the governed source workflow. GET requests never refresh it.
