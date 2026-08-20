# ORO — Obligation-Ranked Orbits

ORO is the A11oy control plane for cyclic agent graphs. Its normal stopping
mechanism is structural: every loop-closing barrier that returns `CONTINUE`
must carry a strictly smaller four-component rank. A recursion limit remains an
outer defect backstop, not the convergence mechanism.

## Implemented boundary

- strict rank: unresolved obligations, evidence deficits, integer budget units,
  and turn allowance;
- finite multiset fan-out where the parent consumes a turn and children cannot
  mint obligations, evidence deficit, budget, or turns;
- a data-only Codex selecting local predicates by stable identity, semantic
  version, source digest, implementation digest, schema, and golden vectors;
- barrier membership, generation, absolute TTL, response-size, duplicate,
  semantic-cycle, invariant, and rank-decrease checks;
- six separately bounded roles: Scout, Architect, Builder, Verifier, Sentinel,
  and Integrator;
- strict SQLite evidence for plans, runs, arrivals, barriers, allocations,
  invariant results, semantic hashes, negative results, comparisons, approvals,
  DSSE receipts, and intent/completion/refusal certificates;
- Ed25519 DSSE signing from an owner-only mounted key file;
- production fail-closed when durable storage, the managed signer, or managed
  write authorization is absent;
- zero-CDN dashboards at `/oro` and `/oro/v5`;
- plan, orbit, barrier, negative-result, approval, certificate, health, readiness,
  contract, role, and count APIs under `/api/a11oy/v1/oro`;
- a standalone FastAPI/Uvicorn service and a `mount_oro` integration function for
  the canonical A11oy server.

There is deliberately no release, direct-main, merge, or production-deploy
endpoint. ORO can nominate or refuse work; protected delivery remains a separate
authority.

## Local source verification

```bash
python3 -m pip install --require-hashes -r .github/requirements/ci-core.txt
python3 -m compileall -q oro tests/test_oro_operational_v3.py
python3 -m pytest -q tests/test_oro_operational_v3.py
```

Run a real loopback process with an explicitly test-only ephemeral signer:

```bash
export SZL_ORO_ENV=development
export SZL_ORO_DB_PATH=/tmp/a11oy-oro.sqlite
export SZL_ORO_ALLOW_EPHEMERAL_SIGNER=1
export SZL_ORO_ALLOW_DEVELOPMENT_AUTH=1
python3 -m uvicorn oro.api:create_app --factory --host 127.0.0.1 --port 8877
```

Then probe:

```bash
curl --fail http://127.0.0.1:8877/api/a11oy/v1/oro/healthz
curl --fail http://127.0.0.1:8877/api/a11oy/v1/oro/readyz
curl --fail http://127.0.0.1:8877/api/a11oy/v1/oro/contract
curl --fail http://127.0.0.1:8877/oro
```

The ephemeral signer and development bearer authority are rejected as
production authority by configuration: both opt-ins are considered only when
`SZL_ORO_ENV` is `development` or `test`. Unknown environment values fail
closed rather than silently selecting development behavior.

## Production signer and persistence

Generate an Ed25519 key outside the repository and make it owner-readable only:

```bash
umask 077
openssl genpkey -algorithm ED25519 -out /secure/path/oro-ed25519.pem
chmod 600 /secure/path/oro-ed25519.pem
```

The application accepts the private key only through
`SZL_ORO_SIGNING_KEY_PATH`; raw private-key environment values are not supported.
It exposes only the configured key ID and SHA-256 public-key fingerprint.

A production process requires:

```text
SZL_ORO_ENV=production
SZL_ORO_DB_PATH=/absolute/persistent/path/oro.sqlite
SZL_ORO_SIGNING_KEY_PATH=/absolute/secret-mount/oro-ed25519.pem
SZL_ORO_SIGNING_KEY_ID=<governed-key-id>
SZL_ORO_API_TOKEN_PATH=/absolute/secret-mount/oro-api-token
SZL_ORO_API_TOKEN_ID=<governed-operator-id>
```

The database path must be absolute and on disk. The signer and bearer-token files
must be regular and inaccessible to group/other, and the signer must be Ed25519.
Missing or invalid controls leave `healthz` observable but make `readyz` and
every governed write fail closed. Token values are never returned or logged.

`deploy/oro/compose.yaml` wires a named persistent volume, read-only signer and
bearer-token secret mounts, a read-only root filesystem, dropped Linux
capabilities, no-new-privileges, and a readiness health check. Local Docker
Compose does not remap ownership or mode for file-backed secrets, so both host
secret files must already be owned by numeric UID `10001` and inaccessible to
group/other; otherwise readiness fails closed.

## HTTP contract

Read-only:

```text
GET  /oro
GET  /oro/v5
GET  /api/a11oy/v1/oro/healthz
GET  /api/a11oy/v1/oro/readyz
GET  /api/a11oy/v1/oro/contract
GET  /api/a11oy/v1/oro/roles
GET  /api/a11oy/v1/oro/counts
GET  /api/a11oy/v1/oro/plans
GET  /api/a11oy/v1/oro/plans/{plan_id}
GET  /api/a11oy/v1/oro/orbits
GET  /api/a11oy/v1/oro/orbits/{orbit_id}
GET  /api/a11oy/v1/oro/orbits/{orbit_id}/barriers
GET  /api/a11oy/v1/oro/barriers/{barrier_id}
GET  /api/a11oy/v1/oro/negative-results
GET  /api/a11oy/v1/oro/orbits/{orbit_id}/certificates
```

Governed writes:

```text
POST /api/a11oy/v1/oro/plans
POST /api/a11oy/v1/oro/plans/{plan_id}/execute
POST /api/a11oy/v1/oro/barriers/{barrier_id}/approvals
```

Bodies are UTF-8 JSON objects, closed against duplicate fields, and bounded to
256 KiB before parsing. Every write requires a valid Bearer header. Approval
identity is derived from the authenticated token ID and cannot be supplied in
the request body.

## Truth boundary

Before protected merge and exact-revision live readback:

```text
runtime_enforced: NOT_MEASURED
well_founded_termination: MODELED
machine_checked_termination: NOT_PROVED
global_action_optimality: NOT_CLAIMED
general_causal_identification: NOT_CLAIMED
```

The planned Lean witnesses can establish facts about the reviewed rank and
authority model. They do not prove worker correctness, network liveness,
predicate correctness, unrestricted action enumeration, or global optimality.
