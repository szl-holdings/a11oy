# Build on SZL — Provenanced AI Infrastructure

**SZL Holdings developer hub** · Doctrine v11 (LOCKED 749 declarations / 14 unique axioms / 163 tracked sorries) · License: Apache-2.0
Maintained by Yachay `<yachay@szlholdings.dev>` · Founder: Stephen Paul Lutar Jr.

> Every action signed. Every decision gated. Every receipt verifiable.

SZL Holdings builds a **formally-verified governance gate for agentic AI**. This repo is the
developer-facing entry point: quickstart, full API reference, MCP integration, and runnable examples.
Build your own "organ" on the same substrate the five flagships use.

---

## The five flagship organs

| Organ | Role | Live base URL |
|-------|------|---------------|
| **a11oy** | Λ-gate router / policy + receipt substrate; hosts the 16-tool Hatun-MCP server | `https://szlholdings-a11oy.hf.space` |
| **killinchu** | Defense vertical — counter-UAS / drone intelligence (12 superpowers) | `https://szlholdings-killinchu.hf.space` |
| **rosie** | Personal aide / operator console (16-command catalog) | `https://szlholdings-rosie.hf.space` |
| **sentra** | Cross-cutting immune system — dual-use + injection filter | `https://szlholdings-sentra.hf.space` |
| **amaru** | Memory cortex — every inference cites its source | `https://szlholdings-amaru.hf.space` |

All five return Doctrine v11 verbatim from `/healthz`: `749 declarations / 14 unique axioms / 163 tracked sorries`, locked at `c7c0ba17`. Λ uniqueness is **Conjecture 1 (NOT a theorem)** — stated honestly. SLSA **L1 (honest)**.

---

## Table of contents

| Doc | What it covers |
|-----|----------------|
| [QUICKSTART.md](./QUICKSTART.md) | 5-minute walkthrough: install client, list tools, dispatch a command, verify a receipt |
| [API_REFERENCE.md](./API_REFERENCE.md) | Every public endpoint across the five flagships |
| [MCP_INTEGRATION.md](./MCP_INTEGRATION.md) | Add the Hatun-MCP server to Claude Desktop / Cursor |
| [GRAPHQL.md](./GRAPHQL.md) | Unified GraphQL surface across the five flagships — example queries, Apollo Client, MCP-vs-GraphQL |
| [SUBSTRATE_PACKAGES.md](./SUBSTRATE_PACKAGES.md) | Monorepo `platform/packages/` — build your own organ |
| [SDK_DROP_IN.md](./SDK_DROP_IN.md) | **Agentic Mesh SDK** — wrap *any* app (Next.js/FastAPI/Express/Go/CLI) in 3 lines |
| [CONTRIBUTING.md](./CONTRIBUTING.md) | How to contribute |
| [EXAMPLES/](./EXAMPLES/) | Runnable Python + config examples |

## Examples at a glance

- [`python_quickstart.py`](./EXAMPLES/python_quickstart.py) — sign a payload, verify, build a Khipu chain
- [`mcp_claude_config.json`](./EXAMPLES/mcp_claude_config.json) — drop-in Claude Desktop config
- [`sentra_filter_example.py`](./EXAMPLES/sentra_filter_example.py) — submit a payload, get verdict + receipt
- [`rosie_command_example.py`](./EXAMPLES/rosie_command_example.py) — dispatch a personal-aide command

---

## The provenance model in one paragraph

You call a flagship endpoint. **sentra** evaluates the input deny-by-default. The decision is wrapped
in a **DSSE** (Dead Simple Signing Envelope) signed with ECDSA-P256-SHA256, and chained onto the
**Khipu Merkle DAG** — a hash-linked, summation-checked ledger that is **replay-verifiable offline.**
You can verify any receipt against the organ's public key (`/khipu/pubkey`). Deploy the whole thing
**airgapped** with UDS Zarf bundles.

---

## Related repos

- **szl-holdings/compliance-posture** — security questionnaire, DPA/MSA/NDA, SOC2/FedRAMP roadmaps
- **[szl-holdings/platform](https://github.com/szl-holdings/platform)** — substrate monorepo (`packages/`)
- **[szl-holdings/hatun-mcp](https://github.com/szl-holdings/hatun-mcp)** — the 16-tool MCP server
- **[szl-holdings/lutar-lean](https://github.com/szl-holdings/lutar-lean)** — Lean 4 / Mathlib formalization (749/14/163)
- **DOI** [10.5281/zenodo.20434308](https://doi.org/10.5281/zenodo.20434308) · **ORCID** [0009-0001-0110-4173](https://orcid.org/0009-0001-0110-4173)

*Signed Yachay `<yachay@szlholdings.dev>` · Co-Authored-By: Perplexity Computer Agent · Apache-2.0*
