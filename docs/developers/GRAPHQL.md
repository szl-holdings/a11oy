<!-- SPDX-License-Identifier: Apache-2.0 -->
# GraphQL — the unified SZL surface

The **SZL GraphQL Gateway** gives you one typed endpoint over all five flagships
(a11oy, amaru, sentra, rosie, killinchu). Every query and mutation is signed into
a Khipu receipt chain — so the GraphQL surface is itself an auditable log.
Doctrine v11 · Apache-2.0.

> **⚠️ STATUS: ROADMAP — NOT YET DEPLOYED.** The gateway source exists in
> [`szl-holdings/graphql-gateway`](https://github.com/szl-holdings/graphql-gateway) (Strawberry +
> FastAPI), but **no public Space is live yet** — the URLs below currently return `404`. Do **not**
> demo these as live endpoints. Until the Space ships, query the flagships directly via their REST
> surfaces in [API_REFERENCE.md](./API_REFERENCE.md). This page documents the *planned* unified schema.

- Planned endpoint (not live): `https://szlholdings-graphql-gateway.hf.space/graphql`
- Planned explorer (not live): `https://szlholdings-graphql-gateway.hf.space/graphiql`
- Planned SDL (not live): `https://szlholdings-graphql-gateway.hf.space/graphql/sdl`

Built with **Strawberry** (code-first) + **FastAPI**, **Apollo Federation v2**
ready — each flagship can publish its own subgraph and the gateway composes them.

---

## Schema (excerpt)

```graphql
type Flagship { id: ID!, name: String!, healthz: HealthStatus!, doctrine: Doctrine!, wireD: WireDStatus!, signedReceipts: [Receipt!]! }
type Receipt { hash: String!, prevHash: String, payload: JSON!, signature: String!, signedAt: DateTime!, organ: String! }
type Doctrine { version: String!, declarations: Int!, axioms: Int!, sorries: Int!, lockedAt: String! }
type Formula { id: String!, name: String!, statement: String!, leanProved: Boolean!, sorryTagged: Boolean! }
type Mesh { flagships: [Flagship!]!, totalReceipts: Int!, chainIntegrity: Boolean!, slos: [SLO!]! }

type Query {
  mesh: Mesh!
  flagship(id: ID!): Flagship
  receipt(hash: String!): Receipt
  formulas: [Formula!]!
  formula(id: String!): Formula
  recall(query: String!, organ: String): [RecallResult!]!
}
type Mutation {
  sign(payload: JSON!, organ: String!): Receipt!
  dispatchCommand(organ: String!, command: String!, payload: JSON!): Receipt!
}
```

## Example queries

Mesh overview:

```graphql
query Mesh {
  mesh {
    totalReceipts
    chainIntegrity
    flagships { id name healthz { ok } doctrine { version declarations sorries } }
    slos { flagship objective current }
  }
}
```

A single flagship + its signed receipts:

```graphql
query Amaru {
  flagship(id: "amaru") {
    name
    wireD { enabled keyid }
    signedReceipts { hash signedAt organ }
  }
}
```

Sign a payload (returns a Khipu receipt):

```graphql
mutation Sign {
  sign(payload: { action: "demo", note: "hello mesh" }, organ: "rosie") {
    hash prevHash signature signedAt organ
  }
}
```

## Apollo Client snippet

```ts
import { ApolloClient, InMemoryCache, gql } from "@apollo/client";

const client = new ApolloClient({
  uri: "https://szlholdings-graphql-gateway.hf.space/graphql",
  cache: new InMemoryCache(),
});

const { data } = await client.query({
  query: gql`
    query Mesh {
      mesh {
        chainIntegrity
        flagships { id name doctrine { version } }
      }
    }
  `,
});
console.log(data.mesh.flagships);
```

`curl` will work too once the gateway is deployed (it returns `404` today — roadmap):

```bash
# ROADMAP — endpoint not live yet (404). Shown for the planned schema.
curl -s https://szlholdings-graphql-gateway.hf.space/graphql \
  -H 'content-type: application/json' \
  -d '{"query":"{ mesh { totalReceipts chainIntegrity } }"}'
```

## MCP vs GraphQL — when to use which

| | **Hatun-MCP** | **GraphQL Gateway** |
|---|---|---|
| Best for | LLM agents / tool-calling clients (Claude, Cursor) | apps, dashboards, scripts, typed clients |
| Protocol | MCP Streamable HTTP + SSE (`2025-03-26`) | GraphQL over HTTP |
| Shape | governed tools, tool-call semantics | typed schema, query exactly the fields you need |
| Discovery | `/api/a11oy/v1/mcp/tools` | introspection / `/graphql/sdl` / `/graphiql` |
| Governance | Yuyay-13 gate + Khipu receipts (DSSE-signed) | Khipu receipt signed on every query/mutation |
| Federation | n/a | Apollo Federation v2 (per-flagship subgraphs) |
| Endpoint | `/api/a11oy/v1/mcp/*` (live REST) | `…/graphql` (roadmap) |
| Live today? | ✅ REST surface live (`/api/a11oy/v1/mcp/tools`) | ❌ not yet deployed (404) |

Rule of thumb: **agents → MCP, software → GraphQL.** Today only the MCP REST surface is live;
the GraphQL gateway is roadmap. Both are designed to write to the same Khipu audit chain.

See also: [MCP_INTEGRATION.md](./MCP_INTEGRATION.md), [API_REFERENCE.md](./API_REFERENCE.md).

---

Doctrine v11 — LOCKED, verbatim: **749 / 14 / 163** · locked_at `c7c0ba17`.

Signed: Yachay `<yachay@szlholdings.dev>`
Co-Authored-By: Perplexity Computer Agent
