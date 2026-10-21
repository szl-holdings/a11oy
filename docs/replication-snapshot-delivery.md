<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Explicit snapshot-confirmed replication

DECLARED source candidate: the four `khipu_lmdb` package modules are exported
from the immutable Platform PR 957 candidate recorded per entry in
`vendor.manifest.json`. That candidate is not yet a protected merged release.
The paired adapter reuses the sole source and mirror LMDB handles opened by
`szl_unay_routes.register`; it never opens a second live environment.

Replication defaults to disabled. Local `KHIPU_HTTPS_PEERS_JSON` is a JSON array
of exact peer objects: `direction` (`inbound` or `outbound`), `peer_id`, HTTPS
`endpoint`, `source_organ`, `source_ns`, and `credential_env`. Each credential
reference names an environment variable; no credential value belongs in this
document, source, request body, or manifest. A configured inbound endpoint's
path must equal `/api/<namespace>/v2/khipu/replicate/batch/<peer_id>`.
Endpoint, source identity, peer identity and credential reference form the
immutable transport binding. Configuration is captured at registration.
Runtime identity and target authorization remain separate requirements.

The operator-authorized POST
`/api/<namespace>/v2/khipu/replicate/dispatch/<peer_id>` sends at most one batch.
It accepts no caller-selected URL or credentials. Before HTTPS, the managed
state owner must confirm fresh writer authority and publish/read back an
immutable snapshot containing the exact pending batch bytes. The transport
checks that same batch ID before connecting. After an exact receiver ACK,
the sender must confirm its acknowledged cursor in another snapshot before
returning success. An uncertain send or checkpoint returns BLOCKED.

The receiver's dedicated bearer is checked before streaming the bounded body
or touching storage. The batch receipts, origin index and inbound cursor commit
atomically, then an immutable snapshot must contain the exact cursor, batch ID
and all corresponding origin records before the receiver sends ACK. A retry
can acknowledge only the exact last accepted batch or the next contiguous
batch. There is no automatic dispatch loop, inference, training, or effect
execution. Per-direction/per-peer locks allow bidirectional sends without
holding a receiver lock across the remote HTTPS wait.

A11oy uses its managed StateStore for both snapshot barriers and writer
fencing. The entire worker operation remains in flight through snapshot and
network waits, so handover cannot silently discard an active operation.
Killinchu currently has no equivalent qualified managed owner: these endpoints
remain BLOCKED before LMDB writes even if peer configuration is supplied.
Source installation alone does not establish a durable target or authorize
production replication.

MEASURED tests cover local managed LMDB capture, immutable download/readback,
exact pending/ACK predicates, restart restoration, failed checkpoint refusal,
operator and dedicated-peer authorization ordering, bounded request streaming,
and simultaneous bidirectional dispatch. A separate integrated consumer test
uses real TLS and a receiver subprocess with the actual adapter, operator gate,
StateStore middleware and snapshot owner. It kills the receiver after its
confirmed snapshot but before the HTTP ACK, restores both stores into fresh
local directories, replays identical batch bytes, and checks independent
sender/receiver snapshot readbacks. The sender reopens in the parent test
process; only the receiver undergoes an OS process crash. Provider CAS and
object storage in this test are explicitly SIMULATED fixtures.

The integrated VM command ran the eight managed snapshot tests and the real
TLS composition test: **9 passed in 2.62 seconds**, exit 0, in
`/home/Ubuntu/szl-verification/replication-consumer-20261021-0fd7c78e139a`.
The transfer archive SHA-256 was
`129c321391bac221eacf77a3b6c4be2af1d6cc16c5067178ebe8d73a3382bbf2`.
A distinct task venv used an exact hash-locked limited dependency closure;
no shared environment, production process, configured peer, or service changed.
Platform's separate native VM suite covers transport corruption, TLS failure,
transaction interruption, sender/receiver process restart and replay.
Neither test environment certifies the hosted
services, whose credentials, preservation, exact deployed source and live
replication remain separate release gates.

Commands: `python -B -m pytest -q -p no:cacheprovider tests/test_khipu_delivery_routes.py tests/test_replication_shared_payload.py`;
A11oy additionally runs `tests/test_replication_snapshot_delivery.py`,
`tests/test_replication_snapshot_https.py`, and the
existing StateStore regression suites. Exact observed results belong in the
PR proof packet. Protected merge, publication and production activation are
BLOCKED pending those independent gates.
