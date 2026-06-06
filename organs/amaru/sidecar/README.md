# Amaru — Andean Ouroboros brain runtime

Python 7-chakra kernels behind a single FastAPI app.

## Chakras (root → crown)

| Order | Name | Module |
| ----- | ---- | ------ |
| 1 | root | `amaru.chakras.root` |
| 2 | sacral | `amaru.chakras.sacral` |
| 3 | solar | `amaru.chakras.solar` |
| 4 | heart | `amaru.chakras.heart` |
| 5 | throat | `amaru.chakras.throat` |
| 6 | third_eye | `amaru.chakras.third_eye` |
| 7 | crown | `amaru.chakras.crown` |

Each chakra has:

- `kernel.py` — the executable kernel (port of upstream Amaru; when the upstream
  Python is not vendored locally, the kernel raises
  `NotImplementedError("upstream kernel not vendored")` which the runtime
  surfaces verbatim — never silently faked).
- `LEADER.md` — leader doctrine and the canonical minimization-proof hash.
- `proof.json` — the minimization-proof receipt (proof_id + sha256).
- `result.json` — the canonical last result.
- `rejected.md` — rejected alternatives.

## Surface

- `POST /chakra/{name}/evaluate` — run that chakra's kernel against an input
  envelope. Returns chakra output + minimization-proof receipt id.
- `GET  /chakra/{name}/leader` — `LEADER.md` content + the canonical proof hash.
- `POST /scheduler/tick` — run `amaru_scheduler` one step over the configured
  `chakana_wiring`.
- `GET  /healthz` — liveness.
- `GET  /tripwires` — `huklla-10` tripwire status.

Every chakra evaluation publishes a receipt to topic `amaru.chakra` on the
yawar-bus (Prism Bus HTTP surface). Every scheduler tick publishes to
`amaru.scheduler`. Both are replayable from the bus history endpoint.

## Running locally

The api-server artifact exposes a service entry `amaru` (autoStart=false).
Start it from the workflow panel when you want the runtime up.

```bash
PORT=6810 pnpm run amaru:dev      # workspace shortcut, or:
PORT=6810 python -m uvicorn amaru.app:app --host 0.0.0.0 --port 6810
```

## Doctrine note

This service is `doctrine-scanner-exempt` per task #5176. The upstream chakra
kernels live in the published Amaru bundle; this runtime is a thin local
process + receipt chain that wraps them.
