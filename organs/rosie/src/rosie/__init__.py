# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""rosie — real MCP console + multi-agent orchestrator.

Doctrine v11 LOCKED 749/14/163 @ c7c0ba17 · Λ = Conjecture 1.

Modules:
  mcp_server     real MCP stdio JSON-RPC server over Rosie's 12-tool catalog
  orchestrator   LangGraph-style StateGraph: Amaru -> Sentra -> Killinchu -> A11oy
  tool_router    routes MCP calls to organ adapters; BFT n>=3f+1 quorum on critical paths
  observability  real OTLP/gRPC span exporter (W3C traceparent propagation)
"""

DOCTRINE = "v11 LOCKED 749/14/163"
KERNEL_COMMIT = "c7c0ba17"
LAMBDA_STATUS = "Conjecture 1 (NOT a theorem)"
SLSA = "L1 honest (L2 roadmap via Wire D — L2 attestation not yet earned)"
ORGAN_CHAIN = ["amaru", "sentra", "killinchu", "a11oy"]

__all__ = ["DOCTRINE", "KERNEL_COMMIT", "LAMBDA_STATUS", "SLSA", "ORGAN_CHAIN"]
