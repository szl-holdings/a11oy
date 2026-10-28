<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# MCP advertised inventory observations

The shared brain's `canonical.mcp_tools` is nullable. A number is the length
of an actual tools manifest observed in this process for the requested Space
within the last 30 seconds. It counts advertised entries; it does not assert
that a tool can execute, has credentials, or has passed an inference test.

The sibling `mcp_inventory` object identifies the observed manifest's relative
path, timestamp, age, scope and availability reason. Before an observation,
the count and source are null with `MCP_MANIFEST_NOT_OBSERVED`. A successfully
observed empty inventory is zero. Expired or invalid-clock observations have
a null count. Observations for one Space are never reused for another Space.

A11oy records its existing `/api/a11oy/v1/mcp/tools` response after assembling
the manifest. Health, gates and brain summaries read this observation without
making an additional network request. The manifest response shape is unchanged.
Its existing sibling discovery and timeout behavior are unchanged.

Killinchu receives the identical shared brain code. Its brain reports no
observation until its own manifest producer explicitly records one; this
change does not add a discovery request or claim that Killinchu has no tools.
Consumers of `canonical.mcp_tools` must render null as unknown, not zero.

This metadata does not change operational-readiness gates, signing, durable
storage, model routing, deployment authority, or authorization.
