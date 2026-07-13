# Ayllu as the council around SZL-Forge

Ayllu is explicitly bound to `SZL-Forge-1.5B` as a governed runtime council.
The eleven names are task roles and system-prompt contracts sharing A11oy's routed
model backend. They are not eleven separately trained models.

Every turn binds four independent facts:

1. persona and intended Forge profile;
2. the actual routed model observed for that turn;
3. the allowlisted proposal surfaces and Yupaq compute operations;
4. a binding digest included in the ask or council receipt.

The state remains `ROUTER_INTEGRATED_FORGE_PROFILE_NOT_PINNED`. A configuration
name is not proof that Forge weights loaded. Promotion to a pinned state requires a
model-load receipt binding the base revision, adapter SHA-256, served identity, and
reload evaluation.

## Authority boundary

The model may propose. It may not execute an external action, approve its own
proposal, sign evidence, or certify its own correctness. The current Ayllu loop has
zero effectors and `tool_dispatch=false`.

Ask and council responses are returned only to the caller and are not
automatically copied into the public lounge. Stateful Yupaq job and receipt routes
require a bearer whose SHA-256 is configured in the approved secret store; the
raw bearer is never stored in release metadata.

Yupaq can draft only operations listed by the computation plane. A human or an
independent authorized controller must submit the typed request to the compute API;
the compute plane validates the schema and preserves the engine's own honesty state.

## Public surfaces

- `GET /api/a11oy/v1/ayllu/model-binding`
- `GET /api/a11oy/v1/ayllu/roster`
- `POST /api/a11oy/v1/ayllu/ask`
- `GET /api/a11oy/v1/ayllu/council/manifest`
- `POST /api/a11oy/v1/ayllu/council`
- `GET /api/a11oy/v1/compute/capabilities`

Canonical release metadata lives in `model_release/szl-ayllu-binding.json`.
