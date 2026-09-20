# A11oy Anatomy Ledger

Operational provenance dashboard for the A11oy governed mesh.

Taxonomy home: **supply-chain / provenance**. This package does not replace
NVIDIA hardware, Palantir Foundry, or Apollo fleet control.

## Guarantees

- Imports genuine in-toto Statement v1 and SLSA provenance documents.
- Evaluates evidence with locked OPA/Rego when the pinned binary is present.
- Falls back to a Python twin with identical ALLOW / REVIEW / BLOCK semantics.
- Distinguishes `ALLOW`, `REVIEW`, and `BLOCK`.
- Builds a deterministic SHA-256 hash chain across normalized records.
- Never treats a DSSE envelope as cryptographically verified merely because it exists.
- Never stamps ALLOW when OPA is absent; the twin result is demoted to REVIEW.
- Exports the complete ledger as JSON.
- Serves a dashboard, `/healthz`, `/api/ledger`, `/api/prove`, `/api/authorize`, `/api/evaluate`, and `/api/bind`.
- Attests release artifacts in GitHub Actions on the default branch.

The hash chain is tamper-evident, not a digital signature. Cryptographic trust
must come from Sigstore, GitHub artifact attestation verification, or another
explicit verifier.

## Run

```bash
make -C anatomy-ledger verify
make -C anatomy-ledger serve
curl -fsS http://127.0.0.1:8787/healthz
curl -fsS http://127.0.0.1:8787/api/ledger | python3 -m json.tool
```

Open `http://127.0.0.1:8787`. The dashboard also loads `public/data/ledger.json`
when the API is not running.

## Add evidence

Place real evidence under `anatomy-ledger/evidence/`. Recognized names:

- `*.intoto.json`
- `*.intoto.jsonl`
- `*attestation*.json`
- `*provenance*.json`

```bash
make -C anatomy-ledger ledger
```

No demonstration attestations are installed. An empty evidence directory
produces an honest empty ledger.

## Verify a release

```bash
python3 anatomy-ledger/tools/verify_release.py \
  dist/anatomy-ledger.tar.gz \
  --repo szl-holdings/a11oy
```

Verification failure exits non-zero. Do not convert a failed verification into
REVIEW or ALLOW.

## Intent authorization

Cedar materials are under `policy/cedar/`. Python twin:

```bash
python3 anatomy-ledger/tools/authorize_intent.py < anatomy-ledger/policy/cedar/example-request.json
```

Cedar decides whether an identity may attempt an action. Rego audits the
artifact and supply-chain evidence associated with execution.
