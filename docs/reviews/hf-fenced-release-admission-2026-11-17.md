<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings -->

# Canonical A11oy post-cutover release admission — 17 November 2026

## Incident and observed state

Protected main SHA 9b4fb0a0a56e6ca894f0c5a86a3c0d19c0883c40 had
merged CEG parent resolution and OpenLineage JobEvent projection but was
not deployed because automatic hf-sync rejected RUNNING with its historic
mandatory open_deploy_window gate.

The first-pause migration in ADR-0001 had already happened. The canonical
runtime reported szl.a11oy-storage-status/v2, FENCED, WRITER, CLEAN,
ACTIVE lease, unfenced=false, writable=true, alert=false, empty active
errors and pending publications, and seven healthy stores. Two separately
read public observations at epoch 337 confirmed lease and snapshot
freshness; these public observations alone are not private HEAD proof.

Manual dispatch 44219467635 used the documented operator window.
Its publisher and runtime-config jobs passed, and live /api/build-info
later reported source 9b4fb0a0; previously absent
/api/a11oy/v1/evidence/openlineage returned HTTP 200 JSON, and the
canonical graph exposed parent_resolution. After handover, independent
public checks found epoch 338, CLEAN/FENCED writer and seven healthy
stores. The final handoff failed correctly because another main merge
advanced protected main to 17a2c238. SUPERSEDED_BY_NEWER_MAIN does not
qualify an older release; successful publication, final certification
and latest-main convergence are distinct states.

## Change: automatic release only after proven clean cutover

Manual or paused authorization behavior is unchanged. For RUNNING
whose build-info differs from protected main, the alternative path is:

1. Existing await_hf_configuration_handover.py capture performs a
   read-only closure over private state-dataset HEAD, bucket heartbeat,
   provider identity, public storage status and Series-A identity.
   Its bounded observation is unsigned and cannot mutate provider state.
2. admit_hf_fenced_runtime.py reuses the canonical private baseline
   validator and canonical relock store validator. It checks independent
   live-source identity, a fresh ACTIVE/CLEAN private observation,
   heartbeat, FENCED public lease with matching epoch and nonregressing
   sequence, exactly seven stores, integrity and snapshot freshness,
   clean restore origins, zero active errors and no pending publication.
3. Only complete validation writes open=true to the CI runner's
   workflow output. Existing protected-main re-admission, single
   canonical publisher, source attestation and live verification
   remain mandatory. This is not an action approval, proof signature,
   model invocation or provider mutation.
4. A legacy FUSE SQLite writer, unknown source, missing private HEAD,
   unclean takeover, paused or crashed process, absent snapshot,
   stale observation, source mismatch or incomplete lease remains HOLD.
   Explicit paused/operator-window deployment remains available.

This is a release-admission update for an already completed cutover,
not a bypass of pre-cutover protections, signing, governance or policy.

## Verification and follow-through

Offline negative fixtures corrupt storage and baseline invariants and
assert that a failed admission never writes open=true. Existing exact
manual-prerequisite, supersession and handover tests still protect the
owner-gated path, fixed evidence-artifact scope and single writer. New
tests run under the Series-A pinned CI dependency set.

A merged change is not a deployed feature until canonical HF sync
completes and protected-main SHA matches deployed /api/build-info.
Separate signing, source parity, readiness and quality gates remain
fail-closed. A concurrent newer main revokes an older run's final
qualification.

Remaining separate work: relocate all other writes away from the HF
bucket FUSE mount before making /data read-only. Retire inert durable
v1 in a dedicated reviewed PR. No GC, bulk deletion, new instance or
storage reinitialization was undertaken by this change.
