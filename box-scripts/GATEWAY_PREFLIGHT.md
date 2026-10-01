<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Read-only gateway preflight

`gateway_preflight.py` compares one explicit consumer alias, one exact Ollama
backend tag and a separately retained digest with the configured gateway and
observed catalogs. It never starts a service, generates text, changes DNS,
downloads a model, updates configuration, signs evidence or authorizes activation.
This is a local operations tool in the tools layer, not a new application route.

## Run

Requires Python 3.11 or 3.12 and PyYAML 6.0.3. The accompanying hash-pinned
requirements file covers Windows x64 and Linux x64 CPython wheels.

```powershell
py -3.12 -m pip install --require-hashes --only-binary=:all: -r box-scripts/gateway-preflight-requirements.txt
py -3.12 box-scripts/gateway_preflight.py `
  --config C:\path\to\staged-gateway.yaml `
  --model EXACT_CONSUMER_ALIAS `
  --backend-model EXACT_BACKEND_TAG `
  --backend-digest EXPECTED_64_CHARACTER_LOWERCASE_SHA256 `
  --gateway-origin http://127.0.0.1:14000 `
  --ollama-url http://127.0.0.1:11434 `
  --public-gateway https://gateway.a-11-oy.com `
  --probe
```

The capitalized arguments above are placeholders, not executable model choices.
Do not copy the candidate catalog's digest into the expected field and call that
independent provenance. The digest binds a previously selected artifact; it does
not establish training provenance, model quality or suitability.

Use a staging port that is **not** referenced by any tunnel. Confirm the listener
is loopback-only independently; a successful request to loopback does not prove
the process is not also listening on other interfaces. This tool intentionally
does not start a gateway for you, and cannot establish listener binding itself.

Only `http://127.0.0.1:PORT` and `http://[::1]:PORT` are allowed for local origins.
`localhost`, wildcard addresses, userinfo, queries and fragments are rejected.
The consumer base and intended public endpoint require HTTPS. Neither receives
the gateway credential. Requests disable environment proxies and redirects.

The key must already be available in the named process environment (default
`LITELLM_MASTER_KEY`) and referenced in the gateway file as:

```yaml
general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
```

Inline keys, absent keys and malformed keys fail the check; their values are not
printed or copied. Do not place keys on command lines or in this repository.
The supported static profile is exactly one `model_list` entry with `model_name`
and `litellm_params` (`model`, `api_base`), plus `general_settings.master_key`.
Other fields, router/module settings, injected environment configuration,
additional aliases and database overlays are not accepted. More complex
configurations need their own explicit validation, not a permissive fallback here.

## What the result means

Without `--probe`, this is a configuration-only check: network checks remain
`NOT_TESTED`, overall status is `BLOCKED`, and exit code is 2. With `--probe`, at
most five GETs are made: local Ollama catalog, the consumer health route, and the
local gateway catalog without a credential, with a random invalid credential,
and with the configured environment credential (when usable).

Exit 0 / `LOCAL_PREFLIGHT_PASS` requires every comparison to pass. In particular,
both negative catalog requests must return 401 or 403 and the authenticated
catalog must list the exact alias. HTTP 200 HTML, redirects, timeouts, malformed
JSON, duplicate names and model/digest mismatches cannot become a local pass.
The consumer must itself report the exact alias, intended public endpoint and
OpenAI-compatible API style. An unreachable public consumer can therefore keep
this check blocked even if the staged local gateway works.

Exit 2 / `BLOCKED` is the normal result for missing evidence. Output contains
fixed check names, booleans, status codes and fixed error codes, not response
bodies, raw configuration, exception messages, model text or key values.

Every result keeps `production_ready=false` and `activation_authorized=false`.
Even a local pass does **not** prove public Access enforcement, tunnel selection,
listener binding, authentication on every route, successful inference, restart
persistence, model qualification or deployment authority. The process serving
the port is not cryptographically bound to the file inspected, and a catalog
does not prove which weights an inference would execute. Catalog denial tests
must not be represented as proof of authentication on chat or administrative
routes. The observation is unsigned and is not a replayable admission token.

Configuration and response bodies are limited to 64 KiB. YAML aliases/anchors,
duplicate keys and unsafe tags are rejected. Each network operation has a socket
timeout (0.1–10 seconds) and the body read has a checked deadline. This is not a
hard whole-program wall-clock limit: DNS resolution, OS scheduling and a read
already in progress can exceed the nominal per-operation interval. No retries.

## Deployment closure is separate

1. Pin the intended model and ensure consumer alias, gateway alias, backend tag
   and retained artifact digest agree. Do not silently substitute an installed model.
2. Stage the origin on loopback with an environment-backed key. Check catalog
   rejection and accepted requests, then explicitly test inference and its
   negative-auth paths. Preserve bounded request/response evidence separately.
3. Verify host firewall/listener restrictions, exact tunnel selection, and Access
   coverage for every public hostname. Never tunnel bare Ollama.
4. Activate only the intended supervised origin/connector; verify actual consumer
   inference and restart recovery. Retain source, provider and runtime evidence
   separately. The preflight does not execute any of these activation steps.

The older restart/heal scripts are not prerequisites and are not invoked here.
Restarting all matching tasks or rewriting DNS cannot repair a missing model or
absent origin. Preserve user-modified configuration until its replacement is
reviewed; this tool opens it read-only.

## Tests and references

```powershell
py -3.12 -m unittest discover -s box-scripts -p test_gateway_preflight.py -v
```

Tests use synthetic fixtures and actual loopback HTTP servers, never production
credentials or external inference. CI runs the same suite on Linux and Windows.
The configuration field locations follow [LiteLLM's config reference](https://docs.litellm.ai/docs/proxy/configs).
The catalog contract follows [Ollama's list-models API](https://docs.ollama.com/api/tags).
