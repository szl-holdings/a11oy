<!--
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-->

# Governed GenAI observability

Status: instrumentation contract **IMPLEMENTED NOT DEPLOYED**; redaction and mandatory sampling **MEASURED** in tests; collector, dashboards, alerts, retention, and access control **BLOCKED** without an environment.

The contract follows the dedicated OpenTelemetry GenAI semantic conventions. Model operations record `gen_ai.operation.name`, `gen_ai.provider.name`, `gen_ai.request.model`, token usage, and safe request settings. SZL correlation fields connect run, agent, action request, policy version and decision, formal and deployed artifact digests, model revision, serving runtime, benchmark run, and deployment environment.

Prompt, completion, system prompt, tool schema, raw tool argument, tool result, and retrieval document content are off by default. Recursive redaction replaces values for secret-bearing keys before export. Policy rejections, invalid authorization receipts, production deployment events, provenance or admission failures, security alerts, benchmarks, and incident traces are sampled at 100%.

Telemetry authorizes nothing. Export is active only when an operator supplies an endpoint accepted by the existing private-endpoint policy.
