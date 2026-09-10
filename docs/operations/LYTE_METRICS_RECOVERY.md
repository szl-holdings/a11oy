# Lyte metrics verification and supported recovery

Layer: supply-chain, in the existing source-owned Lyte live verifier. No runtime
module, Space writer, model provider, secret, hardware, or authorization change.

## Reproduce before patching

The historical aggregate publication for A11oy bda66daa67aaa2c7bd9a94bb43537f22bc6c89d7
was not a terminal estate success. Its Lyte metrics failure must not be hidden
by a successful forecast-only check. Read the actual failing job/receipt and
then recapture the current app; a previous failure is not a current diagnosis.

Fresh bounded diagnostic job 6aa21e655527934177ebf0ad independently downloaded
Lyte source 7cd4305014ee638f773d6e128f345ad6a545be58, verified the metrics/app/
project Git blobs, and installed the actual pinned dependencies in Python 3.12.
Its public Lyte metrics response was HTTP 200 with 1,126 bytes and exact build
revision/version labels. The clean-environment app also rendered successfully
before and after readiness. The collector inspection found string identity
labels and the same metrics object shared by telemetry and Runtime.

Therefore this change does NOT claim to have repaired an application-side
numeric-label defect. No such defect was reproduced in the current exact
source. It closes a demonstrated verification gap: the deeper verifier did
not read metrics at all, although the independent Dockerfile controller did.
The diagnostic also observed an unregistered /metrics on the combined vertical
service; that is a different application, not evidence of a Lyte exporter fault.
No unrelated source or contract is rewritten to force one service's shape on
another.

## Permanent contract

The same canonical Lyte verifier now checks metrics twice: after actual
readiness, and after its advisory workload. Both observations require HTTP 200,
exactly one gauge declaration/sample for lyte_build_info with the expected
revision/version, and exactly one lyte_db_pool_healthy gauge sample equal to 1.
Labels must be quoted and exact; duplicates, wrong source, missing metadata,
comments-only output, invalid numeric values, timestamps, unhealthy database,
HTML, failures, and oversized bodies cannot establish success.

This is a bounded critical-gauge contract, explicitly not a full Prometheus
parser or verification of every series. Unrelated metric families are not
rewritten or discarded. Observations retain status, byte count, and content
hash, not arbitrary error details or raw metrics bodies.

The existing /metrics smoke path, pinned deployment controller, source guards,
all prior forecast/identity/authority checks, and canonical single writer remain
unchanged. New negative controls run inside the existing Lyte contract test
file and therefore the existing CI job; no additional workflow is required.

## Recovery sequence

After exact-head tests and normal protected merge, use the existing hf-sync
publication from current protected source. Read its terminal aggregate receipt,
not merely the core deployment job or an older source run. Independently verify
both metrics observations, forecast digests, source identity and live Space
revision, then record the result. Failed evidence remains historical evidence.

Production Granite admission is still false. Public SAMPLE data is not promoted
to production telemetry; persistence, calibration, and SLO qualification remain
separate obligations. No approval, status, or receipt is manufactured here.
