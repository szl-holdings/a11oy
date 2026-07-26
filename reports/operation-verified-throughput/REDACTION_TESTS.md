<!--
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-->

# Telemetry redaction tests

Primary status: **MEASURED**

Generated: `2026-07-26T08:09:12.347408Z`

Status vocabulary: **DEPLOYED**, **IMPLEMENTED NOT DEPLOYED**, **PREPARED IN A PR**, **PROVED**, **MEASURED**, **MODELED**, **FAILED**, **BLOCKED**, **AWAITING AUTHORIZATION**, **DOWNGRADED**, and **RETIRED** are distinct and are not interchangeable.

Adversarial tests cover nested tool arguments, authorization headers, API keys, inline passwords, and disallowed correlation keys. Sensitive values are replaced before export with a bounded redaction marker and digest fingerprint; inline credentials are scrubbed. Model span construction accepts no prompt, completion, message, system prompt, tool schema, tool result, or retrieval-document body.

Production collector redaction, trace-backend access, and retention are still **BLOCKED**.
