# @szl-holdings/a11oy-mesh-router

Substrate-side typed HTTP router from a11oy to its sibling organs.

a11oy is the skeleton/substrate. It routes:

- **reasoning / memory** to **amaru** (the brain) — `GET /state`, `GET /receipts`, `POST /chakra/{name}/evaluate`
- **policy / threat verdicts** to **sentra** (the immune organ) — `POST /v1/verdict`
- **operator I/O** to **rosie** (the operator console) — `POST /v1/events`

## Why this exists

The cross-repo mining audit found that two anatomy wires were declared but had
no runtime client in a11oy:

- a11oy → amaru memory query (the brain ↔ skeleton path was one-directional)
- a11oy → sentra delegation (nothing called the immune organ at runtime)

This package is the substrate-side client for those calls. Strategy: wire over
HTTP using each producer's existing server (instillation strategy C).

## Honest wiring state

- **amaru** exposes the FastAPI sidecar routes called here (verified in the
  cross-repo server index): `GET /state`, `GET /receipts`,
  `POST /chakra/{name}/evaluate`.
- **sentra** does **not** yet expose an inbound verdict HTTP server. The
  contract path is `POST /v1/verdict`. Until sentra ships that route,
  `requestSentraVerdict` **fails closed** (returns `deny`) on any transport
  error, so a missing immune organ never silently allows an action.
- **rosie** event sink is the agreed contract path; rosie wires its inbound
  surface separately.

## Usage

```ts
import { meshConfigFromEnv, queryAmaruState, requestSentraVerdict } from "@szl-holdings/a11oy-mesh-router";

const cfg = meshConfigFromEnv(); // reads A11OY_AMARU_URL / A11OY_SENTRA_URL / A11OY_ROSIE_URL

const state = await queryAmaruState(cfg);          // GET amaru /state
const verdict = await requestSentraVerdict(cfg, {  // POST sentra /v1/verdict (fail closed)
  actionId: "act-123",
  kind: "egress",
  payload: { bytes: 4096 },
});
```

## Test

```
npm test   # node --experimental-strip-types src/index.test.ts
```

The tests boot a real loopback `node:http` server on an ephemeral port and
exercise every function over real TCP — no transport mock.

## License

Apache-2.0 © 2026 SZL Holdings (Stephen P. Lutar Jr., ORCID 0009-0001-0110-4173)
