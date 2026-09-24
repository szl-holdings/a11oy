<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->
# A11oy Anatomy Ledger

A local provenance dashboard, bounded JSON inspection API, and A11oy route integration.
Taxonomy home: **provenance / supply-chain / governance**.

The HTTP service evaluates evidence and intent. It does not run commands, deploy
artifacts, authorize an authenticated operator, or sign receipts. Every bind response
has `executable: false`. A policy result is an advisory assessment of supplied data.

## Run on Windows or Linux

From the repository root (use `python3` on Linux):

```powershell
python anatomy-ledger/server.py --host 127.0.0.1 --port 8787
```

Open `http://127.0.0.1:8787/`. No Node installation or external CDN is needed.
The dashboard reads the live local API and displays an error if it is unavailable;
it never silently substitutes cached proof. Empty evidence remains empty.

A11oy's canonical `serve.py` registers the same service at `/anatomy-ledger/`, with
JSON endpoints under `/api/a11oy/v1/anatomy-ledger/`. The Dockerfile includes the
registrar and its package. Production availability still requires the normal
protected merge, canonical publisher, and fresh deployed-route readback.

| Standalone endpoint | Purpose |
| --- | --- |
| `GET /healthz` | Local service identity and evaluation-only status |
| `GET /api/ledger` | Snapshot with independently recomputed chain consistency |
| `GET /api/prove` | Synthetic software regression cases, explicitly labelled |
| `POST /api/authorize` | Strictly typed advisory intent inspection |
| `POST /api/evaluate` | Structural evidence inspection; caller flags are untrusted |
| `POST /api/bind` | Intent/evidence composition; never execution authority |

POST accepts a JSON object (`Content-Type: application/json`) with a 256 KiB limit.
No API accepts a local artifact path or invokes a verification subprocess on behalf
of an unauthenticated caller. Reads and inspection requests do not write state.

## Build and inspect evidence

Recognized evidence files use `*.intoto.json`, `*.intoto.jsonl`,
`*attestation*.json`, or `*provenance*.json`. The default evidence directory is
`anatomy-ledger/evidence`. Repository-wide discovery is not trusted evidence admission.

```powershell
python anatomy-ledger/tools/install_opa.py --output work/tools/opa.exe
python anatomy-ledger/tools/install_cedar.py --output work/tools/cedar.exe
python anatomy-ledger/tools/build_ledger.py --root . --opa work/tools/opa.exe
python anatomy-ledger/tools/verify.py --opa work/tools/opa.exe --cedar work/tools/cedar.exe
python anatomy-ledger/tools/package_release.py
```

The installer verifies the pinned OPA checksum before execution. On Linux use an
output path such as `work/tools/opa`. The verification command fails when OPA is
missing. Ordinary API inspection remains available as a labelled structural advisory.

Untrusted JSON fields such as `verification.verified`, verifier names, signature
counts, or DSSE envelope presence never establish cryptographic verification. Only
a fresh verifier invocation on the actual artifact may create in-process proof.
The verifier constrains repository, workflow identity, source ref, and optionally
an exact source revision; it binds the extracted statement to the artifact bytes.
Persisted verifier output is an audit report, not a reusable authority token.

The SHA-256 snapshot chain checks record order and internal consistency. It is not
an append-only database, a signature, an external checkpoint, or evidence of who
created the input. An attacker can rewrite both records and hashes. The dashboard
labels stored metadata separately from fresh cryptographic proof.

## Cedar and execution boundary

`policy/cedar/` contains a real Cedar policy, both schema formats, entities, and
requests. The Python evaluator validates typed input and applies default deny. Its
responses identify it as an advisory implementation. CLI schema validation and
cross-engine vectors are separate checks; they do not authenticate API callers.
Missing identity attributes, wrong boolean/integer types, invalid tenant or purpose,
untrusted privileged requests, and malformed digests cannot earn a permit.

Production enforcement must obtain identity and approvals from trusted server-side
sources and clear A11oy's existing governance gateway. This package does not create
that execution path and does not replace existing chain-of-title policy authority.

## Packaging and provenance

`package_release.py` emits a deterministic archive plus SHA-256 and an internal
file manifest. Local packages are **UNSIGNED**. PR CI has read-only permissions.
Only a successful push to `main` can enter the separate GitHub attestation job.
Manual runs and PR runs cannot mint this release attestation.

Artifact attestations establish source/build provenance; they do not prove that an
artifact is safe or production-ready. See the [GitHub documentation](https://docs.github.com/en/actions/concepts/security/artifact-attestations)
and [GitHub CLI verifier contract](https://cli.github.com/manual/gh_attestation_verify).

Cedar syntax and semantics follow the [Cedar policy reference](https://docs.cedarpolicy.com/policies/syntax-policy.html).
SLSA and in-toto documents are recognized evidence formats, not proof by themselves.
