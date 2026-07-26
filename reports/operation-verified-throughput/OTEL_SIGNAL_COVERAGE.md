<!--
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-->

# OpenTelemetry signal coverage

Primary status: **IMPLEMENTED NOT DEPLOYED**

Generated: `2026-07-26T08:09:12.347408Z`

Status vocabulary: **DEPLOYED**, **IMPLEMENTED NOT DEPLOYED**, **PREPARED IN A PR**, **PROVED**, **MEASURED**, **MODELED**, **FAILED**, **BLOCKED**, **AWAITING AUTHORIZATION**, **DOWNGRADED**, and **RETIRED** are distinct and are not interchangeable.

| Signal | Contract | Status |
| --- | --- | --- |
| Model call attributes | operation, provider, model, input/output tokens, safe options | MEASURED in unit tests |
| SZL correlation | run, agent, request, policy, formal/artifact digest, model, runtime, benchmark, environment | IMPLEMENTED NOT DEPLOYED |
| Content capture | off by default | MEASURED |
| Policy and receipt failures | forced 100 percent sampling | MEASURED |
| Build/deploy/admission traces | contract only | PREPARED IN A PR |
| Collector, mTLS, buffering, retention, RBAC | no environment | BLOCKED |
| Dashboards and alerts on real telemetry | no backend | BLOCKED |

The schema target is `https://opentelemetry.io/schemas/1.42.0` from the dedicated GenAI conventions line. Observability authorizes nothing.
