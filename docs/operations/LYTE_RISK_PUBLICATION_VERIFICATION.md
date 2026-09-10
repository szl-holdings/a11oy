# Lyte Forecast Loom: independent runtime risk verification

## Scope

This change adds a pure Python, read-only verification module and regression tests,
then includes them in the existing read-only Lyte contract workflow. It does not
modify either publisher, change source pins, deploy a Space, add a writer, enable
Granite, or change authentication, formulas, second-brain policy or execution authority.

Producer source: `szl-holdings/lyte-services` PR23, normal protected merge
`c48324d0e80e8227f5c0abd60ea5388b07d2bfb4`.
https://github.com/szl-holdings/lyte-services/pull/23

Parent metrics recovery: A11oy PR2083, normal protected merge
`58058a78e187b6c7731bb4a7c426fffe4397d895`.
https://github.com/szl-holdings/a11oy/pull/2083

The parent repair's Lyte pin is `9af99c9fa92fe4bd2f5f3f7e61f4521eb692d2a7`,
which predates producer PR23. Source admission and live deployment are separate.

## Observed pre-rollout gap

At 2026-09-10T03:55:23Z, anonymous HF CPU readback observed:

- Lyte HF repository/runtime: `13ec4f8a4db71885bc2e6eef3a960976607474c9`, RUNNING.
- Actual source/runtime: `7cd4305014ee638f773d6e128f345ad6a545be58`, version4.0.0.
- Readiness HTTP200 and ready=true; source bindings agreed.
- `/api/lyte/v2/metrics`: HTTP404.
- Forecast POST with `risk` returned HTTP200 but omitted `risk_window`.
- Granite returned explicit HTTP503: not admitted in this deployment.

Readback: https://huggingface.co/jobs/SZLHOLDINGS/6aa22a2421047bf1b03716de

This demonstrates why a running Space or an HTTP200 forecast is not sufficient
proof that the new risk feature was published. It is a dated observation, not a
claim about subsequent runtime state. SAMPLE remains SAMPLE; SQLite/process-scoped
persistence is not relabeled production durability.

## Independent Python contract

`scripts/lyte_forecast_risk_live_contract.py` receives an injected JSON transport.
Its eight bounded requests exercise strict above/below rules, deterministic repeat,
changed policy, invalid input, unknown authority properties, and unchanged persisted
receipt count. Requests only calculate advisory forecasts and read receipt counts.
No credentials, model downloads, authenticated ingest or provider writes are requested.

The checker independently reconstructs the canonical three-quantile fixture's raw
and processed request digests, forecast-output digest, complete forecast-receipt digest,
threshold policy, conservative marginal breach bounds, alert steps and report digest.
Self-rehashed claims still fail when their mathematics or policy bindings disagree.
It does not import the producer's implementation to derive expected risk bounds.

The report preserves calibration NOT_ESTABLISHED, production admission false, and
execution authority NONE. Conditional quantile bounds are not calibrated incident
probabilities. No temporal independence, causal intervention effect, or model quality
is inferred from a passing contract check. This checker is intentionally narrow to
its own bounded baseline fixtures, not a general forecasting benchmark.

## Validation and rollout boundary

Local isolated suite: 28 passed, zero failures. These use explicit normative fixtures
and transport doubles. They are not real-app integration or deployed-runtime proof.
The existing Lyte CI retains every prior test and adds the new file to its triggers,
compilation, and test command. CI result and clean exact-source integration evidence
must be read from the PR/job outputs when available, not presumed here.

An attempted edit to existing publisher files was blocked by the execution platform's
safety check. That blocked edit was not applied or retried through another route.
This verification-only change must not be represented as a completed source repin or
as wiring the new checker into the production publisher. No alternate HF writer or
privileged workflow was created to bypass the block.

GitHub remains source authority. Any future authorized publication must retain the
canonical publisher, exact-source/default-branch guard, original metrics and runtime
checks, and truthful downstream product/proof status. This PR alone establishes none
of those deployment outcomes. It provides additional verification evidence without
claiming to resolve the blocked publication mutation.

## Local command

```sh
python -m pytest tests/test_lyte_forecast_risk_live_contract.py -q
```
