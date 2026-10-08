# Energy evidence contract migration

This note describes the fail-closed energy contract introduced by the energy
evidence change. It is a source/API migration note, not a claim that the public
meter, Hugging Face Space, or product domain has deployed these bytes.

## Two different energy questions

An NVML total-energy counter delta can measure energy used by a **GPU device
window**. It does not, by itself, prove that one inference job had exclusive use
of that GPU. A sampled-power integral (`power_w * elapsed_s`) is a model, not a
direct NVML energy-counter measurement. No device-level reading may be promoted
to billable per-job joules without a separately verified attribution contract.

| Surface | Qualified value | When evidence is absent |
| --- | --- | --- |
| Exporter `joules` | Cumulative direct NVML counter deltas, same GPU UUID and continuous counter epoch | `null`; `estimated_joules` remains MODELED only when a valid power sample exists |
| `/api/a11oy/v1/energy/live` and `/energy/mesh` | Fresh complete per-GPU counter provenance, not an exporter aggregate | `joules: null`, label `UNAVAILABLE` |
| `/api/a11oy/v1/energy/sci` | `energy_joules` is a cumulative device reading | Per-call `carbon_gco2eq` and SCI score remain `null`; any cumulative operational-carbon estimate has its own MODELED field |
| `/api/a11oy/v1/energy/operator/status` | Job energy only with verified exclusive attribution | `joules_measured_label: UNAVAILABLE`; numeric zero is not a zero-energy claim |
| JouleCharge ledger | A preserved job receipt, not payment authority | New job entries are nonbillable and make no Stripe charge |

Consumers must check the value **and** its label/scope. Do not infer MEASURED
from an HTTP 200 response, a reachable exporter, a non-null watt reading, a
positive cumulative counter, or a historical `joules_measured_total` field.
The public pages now show `— / UNAVAILABLE` when attribution is unverified and
clear a prior displayed number if the source later becomes unavailable.

Older operator state may contain energy totals recorded under a weaker contract.
The migration preserves those source bytes in a legacy snapshot/backup with
`UNKNOWN` status; it does not relabel them as a new measurement. Existing ledger
receipts and prior charge responses remain historical `REPORTED` records, not
proof of current settlement. Clients seeking cleared revenue need an independent
payment-provider readback before displaying it as such.

For a qualified device reading the exporter needs `nvidia-smi` for observed
power, `nvidia-ml-py` and hardware support for NVML total-energy counters. It
must observe the same GPU UUID across fresh polls with a monotone counter and
must disclose the counter epoch. Unsupported APIs, resets, missing devices,
stale samples, partial fleets, and non-finite values fail closed to `null`.
These prerequisites do not establish job exclusivity.

The additive `Energy evidence and attribution contracts` CI job runs synthetic
and local contract tests, including replay/idempotency and public-page downgrade
behavior. Passing it establishes source behavior only. Publication still uses the
canonical protected-main Hugging Face workflow and needs separate source-bound
deployment, runtime, and meter readbacks.
