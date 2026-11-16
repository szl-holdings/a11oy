<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Isolated build-environment health fan-out

## Scope and release boundary

`a11oy_build_env_fanout.py` belongs to services/observability. It supplies the
root GET contract required by `szl-build-env`, before the SPA fallback. It does
not execute agents, invoke models, mutate a service, sign receipts, grant
execution authority, choose image digests, or configure a provider.

Native SDK/exporter packaging is tracked separately in A11oy PR #3509.
Its dependency repair must be admitted before claiming an export-capable successor image.

The route is **disabled by default**. This source change does not activate it
on the public product or make the existing five-service image set operational.
The historical immutable images remain unchanged. Downstream source owners must
supply their own trace-aware runtime successors, and the existing signed-image,
source-identity, and independent Jaeger gates must still pass.

## Admission and fixed reads

The only admitted request is:

```text
GET /route?fanout=sentra,amaru,killinchu,rosie
traceparent: 00-<nonzero trace id>-<nonzero parent id>-01
```

The lowercase names are immutable infrastructure coordinates, not product names.
Duplicate headers, extra query parameters, alternate targets, reordered targets,
unsampled/invalid trace context, and non-GET methods do not issue peer requests.
The exact query contract deliberately matches the acceptance harness.

Admission requires process configuration `A11OY_BUILD_ENV_FANOUT=1` and
`OTEL_SERVICE_NAME=a11oy`, the already-installed native VSP middleware with an
admitted OTLP exporter, and a same-trace child server context on the request.
A propagation-only fallback cannot qualify this route. For an eventual isolated
cluster deployment, the existing VSP policy also requires the collector DNS name
in `A11OY_OTEL_ALLOWED_HOSTS`; configuring an endpoint alone is insufficient.
No variable or private credential is changed by these source files.

Exactly four fixed internal health URLs are read: the policy, provenance,
counter-UAS, and operator services under the `szl.svc` namespace, all port 8080.
The counter-UAS path is `/api/killinchu/healthz`; the other paths are `/healthz`.
There is no request-selected URL, hostname, namespace, path, body, or method.

Two fan-outs may be active per process; each uses one four-connection HTTP pool.
The deadline is three seconds overall and two seconds per HTTP operation. There
are no retries. Peer JSON is streamed with a 16 KiB bound; redirects, non-200
status, compressed or non-JSON content, duplicate keys, non-finite JSON, and
missing/mismatched peer trace context fail closed. The global deadline cancels
outstanding tasks and capacity is released afterward.

Direct credential-free `httpx.Request` objects avoid inheriting the pool's cookie
jar. Authorization, cookies, baggage, tracestate, forwarded-host and caller bodies
are never forwarded. Proxy environment and redirects are disabled. Only health
read results affect the response; peer bodies and exception text are not returned.

## Acknowledgement is not collector proof

Only four successful, bounded peer reads return the exact
`szl.build-env.fanout-ack/v1` acknowledgement required by the existing harness.
The body names the original injected traceparent and fixed fan-out order. The
response is non-cacheable and explicitly marks collector delivery `unverified`
and execution authority `none`. No signing happens on this GET.

The separate `szl-build-env/verify/validate_jaeger_trace.py` validator must still
observe a fresh connected trace containing all five real service identities.
Health JSON and traceparent echo alone cannot establish that result.

## Tests

Boundary tests use fixture responses and assert refusal before network access,
credential isolation, strict input/output bounds, deadlines, cancellation,
saturation, and recovery. The native integration test starts four fixture HTTP
servers and a real OTLP/gRPC receiver on loopback. It uses the unchanged native
VSP middleware and actual HTTP/OTLP transports, then verifies five real exported
spans share the injected trace and the correct parent graph. Fixture servers
are not the estate's downstream applications or published images.

The dedicated contents-read CI workflow installs a hash-locked CPython 3.12 /
Linux x86_64 test dependency closure. It deploys nothing and requests no secrets.
Artifacts are explicitly fixture-only, not production-readiness receipts.

```sh
python -m pip install --require-hashes -r .github/requirements/ci-build-env-fanout.txt
python -B -m pytest -q -p no:cacheprovider \
  tests/test_build_env_fanout.py tests/test_build_env_fanout_otlp.py
```

## Primary contracts

- Existing fan-out acknowledgement and independent trace verifier:
  https://github.com/szl-holdings/szl-build-env/tree/b89a7a374d5cba886711e3478be8095ab80a96be/verify
- W3C propagation in OpenTelemetry:
  https://opentelemetry.io/docs/languages/python/propagation/
- Native VSP implementation: `vsp_otel/middleware.py` (unchanged by this work).
