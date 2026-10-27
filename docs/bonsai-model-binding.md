<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# External Bonsai model binding

The catalog declares the exact public model ID and gateway slug
`prism-ml/Ternary-Bonsai-2-27B-PQ2_0`. This is an external Prism ML GGUF
artifact, derived upstream from Qwen/Qwen3.8-27B. Created using Bonsai by
Prism ML; built from Qwen by Alibaba Cloud. Its Apache-2.0 license and
attribution are recorded in the immutable upstream [LICENSE](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf/blob/b072e1d3b35a0a630cece372c2127528e0994386/LICENSE)
and [NOTICE](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf/blob/b072e1d3b35a0a630cece372c2127528e0994386/NOTICE.txt).

The source declaration binds repository `prism-ml/Ternary-Bonsai-2-27B-gguf`,
revision `b072e1d3b35a0a630cece372c2127528e0994386`, file
`Ternary-Bonsai-2-27B-PQ2_0.gguf`, size 7,206,168,928 bytes, and SHA-256
`3907dc1658db1f78a9826bf8d5bcb8dc65db0d466388937af57f2294fae62ec1`.
The catalog's evidence class is DECLARED. An operator must measure the deployed
bytes against this binding before admitting a gateway. The base model's identity
does not establish GGUF equivalence; conversion equivalence and evaluation
remain UNKNOWN. This entry does not change a signed SZL model SKU or authorize
tool execution from model output.

The existing VM server reports a local filename as its model identity. The
authenticated gateway must accept only the declared public alias and explicitly
map it to `./models/bonsai2-gguf/27B/Ternary-Bonsai-2-27B-PQ2_0.gguf`. It must
verify that exact upstream response identity before returning the public alias.
Missing or different model identity must fail; an asserted digest in a response
does not repair an identity mismatch. This mapping cannot establish the running
weight bytes by itself.

A11oy uses `A11OY_BRAIN_URL` for the final HTTPS `/v1` endpoint and its dedicated
`A11OY_MODEL_API_KEY` secret. The strict client retains HTTPS port 443, exact
model selection, usage and request budgets, and redirect denial. It does not
accept the Windows loopback SSH URL. A gateway reached through the existing
Windows Cloudflare tunnel depends on that computer, its SSH process, the tunnel,
and the VM; stopping any of these makes inference UNAVAILABLE.

Set the server-side `A11OY_MODEL_ID=prism-ml/Ternary-Bonsai-2-27B-PQ2_0`
to make this model the default for ordinary frontend requests that omit an
explicit model. The default must match an existing open-weight catalog entry;
unknown, empty, whitespace-altered, or endpoint-incompatible values fail before
dispatch. A configured local model retains its existing precedence. Explicit
execution-budget callers retain their own selected model and limits.

Both default and explicit Bonsai selections use the existing strict transport:
one request, the requested output-token budget, and a 30-second elapsed bound.
Requests include `stream: false`. Identity, usage, completion, HTTPS and redirect
checks remain mandatory. Failures do not retry or select another model. This
bounds the client request; remote provider internals remain UNKNOWN. A shared
engine installation without the strict client companion refuses this path.
The backend label reports the configured alias and the one-request policy,
without claiming that the endpoint is reachable.

The alias is admitted only with a configured custom HTTPS endpoint, in both
strict and legacy explicit-model dispatch. Selecting it while the official HF
Router or plain HTTP is configured fails before a request. It is absent from
the automatic HF provider retry roster. Its presence in the source catalog
does not mean that a custom gateway is configured or reachable.

Source inclusion, a reachable endpoint, inference, evaluation and production
acceptance are distinct evidence. Live qualification and the independently
approved production execution suite must be recorded for the actual deployed
source, runtime and boot before making an operational claim.
