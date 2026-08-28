# Spaces Health Operations

## Scope

`GET /api/a11oy/v1/spaces/health` is an evidence endpoint, not a deployment
controller. It performs public, read-only probes and never changes Hugging Face,
DNS, or Cloudflare state.

## Inventory contract

The application registry is defined once in `szl_spaces_surface.SPACES` and is
consumed by both the health surface and redirect-only compatibility surface.
Every fresh health cycle compares that canonical set with the public Hugging
Face Spaces API set.

- `inventory.state=LIVE`: the two regular-Space sets are exactly equal.
- `inventory.state=DEGRADED`: the API responded, but `missing` or `unexpected`
  entries exist.
- `inventory.state=UNAVAILABLE`: current set equality could not be measured.

The organization `README` Space is a special profile surface and is not counted
as an application Space. `governed-agent-bench` is part of the canonical regular
Space set.

## Dependency probes

Exact API contracts use at most two attempts with a two-second per-attempt
deadline. A contract mismatch or non-retryable client response fails closed. Two
consecutive failed health cycles open that dependency's in-process circuit for
30 seconds. While open, the endpoint returns `probe_state=CIRCUIT_OPEN`,
`state=UNAVAILABLE`, and a measured `retry_after_s`; it does not claim recovery.

Circuit state is process-local protection against repeated failing outbound
calls. It is not durable availability evidence and resets on process restart.

## Custom domain state

The `a-11-oy.com` row reports the Hugging Face provider state from
`runtime.domains`. `PENDING` remains `DEGRADED` even if another edge currently
routes the apex successfully. Product surfaces keep **PENDING/UNAVAILABLE**;
do not stamp LIVE.

This repository does not change DNS. Keep the Cloudflare orange-cloud
(proxied) apex. Stephen may later add the Hugging Face verification TXT
(`_huggingface.a-11-oy.com`) **without** dropping that proxy. Do not grey-cloud
(DNS-only) to make Hugging Face report READY. Public 200 on the proxied apex
beats a green HF domain row. `www.a-11-oy.com` is NXDOMAIN (UNAVAILABLE);
DNS is Stephen, not this app. Completing the pending Hugging Face binding is an
external operator action (`docs/runbook.md` INC-05).

## Proxy header boundary

The ASGI security boundary removes app-originated internal topology headers,
including `X-Proxied-Host`, `X-Proxied-Replica`, and `X-Proxied-Path`, while
retaining public correlation IDs. Hugging Face or Cloudflare can append headers
after the ASGI response leaves the application; those headers must be removed by
an authorized edge response-header transform and verified against the public
URL.

## Operator checks

1. Confirm `inventory.missing=[]` and `inventory.unexpected=[]`.
2. Inspect every non-`LIVE` contract's `probe_state`, `attempts`, and circuit
   state before retrying manually.
3. Confirm `custom_domain.provider_stage=READY` before treating the provider
   binding as live.
4. Check public response headers at both the Hugging Face origin and Cloudflare
   apex; application tests cannot prove edge-added headers are absent.
5. Preserve `DEGRADED`, `UNAVAILABLE`, and `CACHED` labels in incident and
   investor evidence.
