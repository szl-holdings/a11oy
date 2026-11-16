# Proof-Carrying Trace IR

Schema: szl.trace-ir/v1

This additive contract records the identity of a governed model, tool, or MCP
operation without giving telemetry any authority. It is designed to bridge the
SZL receipt chain with OpenTelemetry-compatible GenAI spans.

Each event carries:

- trace and span identity, including an optional parent span;
- operation, actor, and terminal status;
- input, result, model, and adapter SHA-256 identities;
- dataset revision and the sorted invariant set used for admission;
- measured energy fields when available;
- redacted attributes and an explicit authorization effect of NONE;
- a deterministic event hash over the canonical event body.

The companion gated_minimum decision is the release rule. It holds on an empty
score set, non-finite values, any score below the threshold, or any critical
failure. A strong mean cannot hide a failed invariant.

The first production integration point is the existing receipt/agent loop:

1. emit STARTED when a tool or model span is admitted;
2. emit SUCCEEDED, FAILED, ABSTAINED, BLOCKED, or CANCELLED at terminal state;
3. bind the event hash and invariant set into the existing Khipu receipt;
4. publish only redacted OTel aliases to the telemetry exporter;
5. use gated_minimum for release/evaluation promotion, never for action
   authorization.

This module is intentionally authority-neutral. Existing deny-by-default,
signature, and Lambda-cone gates remain the authority boundary.

## Task-shape routing

The advisory router in vsp_otel/task_shape.py implements a measured topology
rule. It chooses PARALLEL_EVIDENCE only for independent work with shallow
dependencies and a bounded tool count. Proof, receipt, release, and human
approval work is always CENTRAL_SEQUENTIAL. The result carries an explicit
authorization effect of NONE and must be followed by the normal policy and
receipt gates.
