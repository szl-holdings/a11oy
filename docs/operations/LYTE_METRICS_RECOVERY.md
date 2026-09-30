# Lyte metrics verification and application-owned recovery

Layer: supply-chain, in the existing source-owned Lyte publisher and live
verifier. Runtime source is the normal protected merge of lyte-services PR 22:
`9af99c9fa92fe4bd2f5f3f7e61f4521eb692d2a7`. Its complete source CI passed
137 tests and all 17 applicable jobs in run 34433289098. The PR-only live probe
was intentionally skipped and is not deployment evidence.

## Reproduce before patching

The downloaded historical aggregate artifact 10133081896 has ZIP SHA-256
`bf83c7109b91f3636b0af85ce44809f5bac972751cf9b7de8a6f044bd8274281`.
Its combined service completed successfully; only Lyte attestation failed.
The combined service has no Prometheus GET metrics route and is not changed
by this repair. Earlier descriptions of a combined metrics failure were not
supported by the downloaded artifact and must not be used as its diagnosis.

Fresh bounded diagnostics independently downloaded exact Lyte source, matched
its Git blobs, and rendered the existing metrics registry successfully in a
clean Python environment, including warm histograms. Public observations also
returned valid metrics. No application numeric-label defect was reproduced;
this repair does not pretend one was established or fixed.

The demonstrated coverage gap was narrower: the deeper live verifier never
read metrics, although the Dockerfile controller required a public metrics
smoke. Consequently a deeper-verifier PASS did not independently establish
metrics availability. Historical failed observations remain failed evidence.

## Application-owned route

Lyte PR 22 adds `/api/lyte/v2/metrics` as a second decorator on the existing
real-registry handler. Local `/metrics` remains compatible. This makes the
public application route explicit and avoids depending on generic hosting
infrastructure paths. It is not a claim that every hosting provider reserves
`/metrics`, and it does not bypass authentication or supply infrastructure
credentials to anonymous probes.

Both canonical smoke and the deeper verifier now use that application-owned
alias. Both return or inspect actual registry data; no empty response, canned
health message, or synthetic gauge substitutes for the exporter. Real app tests
cover exact build identity, local/public parity, populated histogram labels,
failed-database health reporting, cache/security headers, and non-mutation.

## Permanent verification

The same canonical verifier checks metrics after readiness and after its
advisory workload. Both observations require HTTP 200, exactly one gauge
sample/declaration for lyte_build_info with the expected revision/version,
and exactly one lyte_db_pool_healthy gauge equal to 1. Quoted labels must be
exact. Duplicates, wrong source, missing metadata, comments-only output, invalid
numeric values, timestamps, unhealthy database, HTML, transport failures,
oversized output, and exporter failure after the workload cannot establish PASS.

This is a bounded critical-gauge contract, not a full Prometheus parser or
validation of every series. Unrelated metric families are not rewritten or
discarded. Evidence retains the actual route, status, byte count and content
hash, not arbitrary error details or raw metric bodies.

All previous forecast/identity/authority checks, the byte-pinned Dockerfile
controller, source-tip guards, existing-Space guard and single canonical
writer remain. No workflow trigger, allocation, DNS, secret, model default,
combined service, or execution authority changes. Updated source-pin regression
expectations track the separately tested and merged producer revision.

## Completion criteria

After exact-head consumer tests and normal protected merge, inspect the
existing hf-sync run's terminal aggregate receipt, not only its deployment
job. Verify the exact new Lyte source and HF runtime, both public metrics
observations, forecast digests, and product-source projection. Record observed
success only after actual probes finish. Candidate test completion and future
deployment are not asserted by this implementation note.

Production Granite remains disabled and execution authority NONE. Public
SAMPLE data is not production telemetry; durability, calibration and SLO
qualification remain separate obligations. No approval or status is invented.
