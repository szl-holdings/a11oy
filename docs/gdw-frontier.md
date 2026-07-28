# Governed Delta Workspace operational harness

GDW binds an authenticated FastAPI control surface to deny-by-default routing,
the canonical file-backed Colang policy, SQLite WAL state, idempotency keys,
atomic local receipts, structured theorem inputs, load tooling, and an offline
evidence dashboard.

## Truth boundary

> GDW Frontier Push Pack is a MODELED instrumentation and verification extension for the Governed Delta Workspace. It provides load testing, operator validation, hybrid scheduling research hooks, KDA-vs-MLA memory benchmarking, and Lean-oriented proof export. It does not claim frontier benchmark superiority, proprietary activation access, or production-scale guarantees beyond the measured harness outputs.

The successor implementation is real code on a draft branch. It is not merged,
deployed, or production-verified. Protected `main` continues to expose the
Wave-26/Wave-28 consolidation hold until this successor receives independent
review and a protected merge. The protected deployment path now provisions a
fresh `/data/a11oy/gdw/v2` generation, installs only a digest-bound principal
registry in the Space secret store, exercises an authenticated state
transition, drains its two effects, and requires a clean integrity result.
Each benchmark remains `UNMEASURED` until its own output is captured. Exporting
a theorem input is not a proof; Lean results are reported separately. The
control API chooses a route but does not claim that a model kernel ran.

`GDW_PROOF_EXPORT_MODE=outbox` is the only accepted production mode. Each
accepted transition commits state, request, an explicitly `UNSIGNED_ATOMIC`
local receipt, and deterministic receipt/proof outbox records in one SQLite
transaction. A token-fenced leased drain writes immutable, owner-scoped,
generation- and content-bound JSON artifacts after commit. The canonical intent,
request response, receipt ledger, full payload digest, and effect key are checked
again before export. This is durable local atomicity plus retry-safe projection,
not cross-system two-phase commit.

The admin-only drain route is invoked by exact-source promotion and by the
bounded scheduled `gdw-drain.yml` workflow. Its bearer value remains a GitHub
Actions secret; only the SHA-256-bound registry is installed as a Hugging Face
Space secret. Every scheduled result is secret-free.

## Runtime

Set `GDW_PRINCIPALS_JSON`, `GDW_DB_PATH`, `GDW_PROOF_DIR`,
`GDW_RECEIPT_PROJECTION_DIR`, and `GDW_SQLITE_JOURNAL`, then start `serve:app`.
The canonical Hugging Face promotion uses a fresh `/data/a11oy/gdw/v2`
generation and `GDW_SQLITE_JOURNAL=DELETE`; WAL remains the local-filesystem
default and is not asserted portable across the mounted network volume.
`GDW_PRINCIPALS_JSON` is an object keyed by canonical principal ID. Each value
contains a lowercase SHA-256 bearer-token digest and a non-empty subset of the
`user` and `admin` roles. Plaintext bearer tokens are not stored in the registry.
Every write requires `Authorization: Bearer ...` and a unique `X-Request-Id`.
Reusing an id with identical content replays the prior response; changing the
content returns HTTP 409.

Requests and sessions have persisted owners. Cross-owner read, replay, and
mutation attempts return HTTP 403. Admin role is required for benchmark metadata,
metrics, and integrity. These finite controls are configurable within hard caps:

- `GDW_OWNER_MAX_REQUESTS` and `GDW_GLOBAL_MAX_REQUESTS`;
- `GDW_OWNER_MAX_SESSIONS` and `GDW_GLOBAL_MAX_SESSIONS`;
- `GDW_OWNER_MAX_ARTIFACTS` and `GDW_GLOBAL_MAX_ARTIFACTS`;
- `GDW_RETENTION_SECONDS` and `GDW_MAX_EFFECT_ATTEMPTS`.

Expired requests are reclaimed only after every effect is exported. Expired
session state is reclaimed. Invalid configuration, a policy byte-lock mismatch,
an unsupported policy flow, legacy pending proof rows, ledger divergence, dead
effects, or artifact tampering closes the semantic gate before request-body
parsing. Health then reports `UNAVAILABLE` and writes remain disabled.

The policy evaluator is in the same process as the writer, which is reported as
`writer_is_judge=true`; the exact Colang source bytes and supported flow names
are locked by `policy/colang/gdw_enforcement_contract.json`. This is a
fail-closed deterministic control, not an independent governance authority.

Routes:

- `GET /api/a11oy/v1/gdw/healthz`
- `GET /api/a11oy/v1/gdw/bench/meta`
- `GET /api/a11oy/v1/gdw/metrics`
- `GET /api/a11oy/v1/gdw/integrity`
- `POST /api/a11oy/v1/gdw/drain` (admin only)
- `GET /api/a11oy/v1/gdw/sessions/{session_id}`
- `POST /api/a11oy/v1/gdw/step`

## Research lineage

- Kimi Linear technical report: https://yzhang.site/assets/pubs/techreport/2025/kda.pdf
- Gated DeltaNet paper and code: https://arxiv.org/abs/2412.06464
- Laguna technical report: https://arxiv.org/abs/2605.27605
- TorchLean: https://github.com/lean-dojo/TorchLean

These references motivate measurable routes and proof-compatible boundaries.
They are not evidence that this implementation achieves the cited model results.
